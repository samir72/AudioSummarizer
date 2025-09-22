import os, tempfile, subprocess, re, json, shutil, time
from fastapi import FastAPI, HTTPException
from pathlib import Path
from typing import Optional, Callable, Any
import yt_dlp
from utils.storage import upload_and_sign   # To remove circular import issue

app = FastAPI()

def ensure_ffmpeg():
    """
    Verify that ffmpeg is available in PATH. 
    Raises RuntimeError with helpful guidance if missing.
    Prints ffmpeg version to logs if found.
    """
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path is None:
        raise RuntimeError(
            "FFmpeg not found in PATH.\n\n"
            "👉 For Hugging Face Spaces:\n"
            "   • If using Gradio/Streamlit template → add a `packages.txt` file at repo root with a line: ffmpeg\n"
            "   • If using Docker template → add `apt-get install -y ffmpeg` in your Dockerfile\n\n"
            "Without ffmpeg, yt-dlp cannot extract/convert audio."
        )

    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
        print("✅ ffmpeg found at:", ffmpeg_path)
        print(result.stdout.splitlines()[0])  # show first line of version info
    except Exception as e:
        raise RuntimeError(f"ffmpeg was found at {ffmpeg_path} but could not run: {e}")

class YTDLPError(RuntimeError):
    pass

def _require(bin_name: str):
    if shutil.which(bin_name) is None:
        raise YTDLPError(f"Required executable '{bin_name}' not found in PATH.")


@app.get("/health")
def health():
    return {"ok": True}

""" @app.post("/extract")
def extract(req: ExtractReq):
#    if not is_youtube(str(req.url)):
#        raise HTTPException(status_code=400, detail={"code": "INVALID_URL"})

    work = tempfile.mkdtemp()
    in_tpl = os.path.join(work, "in.%(ext)s")
    try:
        # 1) download bestaudio
        run([YTDLP, "-f", "bestaudio", "-o", in_tpl, str(req.url)])

        files = [f for f in os.listdir(work) if f.startswith("in.")]
        if not files:
            raise RuntimeError("No input after yt-dlp.")
        src = os.path.join(work, files[0])

        # 2) transcode
        out_ext = "wav" if req.format == "wav" else "mp3"
        out_path = os.path.join(work, f"audio.{out_ext}")
        ff = [os.getenv("FFMPEG_BIN", "ffmpeg"), "-y", "-i", src]
        if req.mono: ff += ["-ac", "1"]
        if req.sample_rate: ff += ["-ar", str(req.sample_rate)]
        if out_ext == "mp3": ff += ["-b:a", "96k"]
        ff += [out_path]
        run(ff)

        # 3) upload + sign (short-lived)
        signed = upload_and_sign(out_path, ttl_minutes=45)
        return {"status": "ready", "audio_url": signed}
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail={"code": "PIPELINE_FAILED", "message": str(e)})
 """
@app.post("/extract")
def extract(
    youtube_url: str,
    out_dir: Optional[str] = None,
    target_sr: int = 16000,
    target_channels: int = 1,
    quiet: bool = True,
    keep_intermediate: bool = False,
    progress_hook: Optional[Callable[[dict[str, Any]], None]] = None,
) -> str:
    """
    Download YouTube audio via yt_dlp's Python API, extract to WAV,
    and post-process with ffmpeg to 16 kHz mono. Returns path to the final WAV.

    Args
    ----
    youtube_url : str
    out_dir : Optional[str]    Directory for outputs (temp dir if None).
    target_sr : int            Sample rate for final WAV (default 16000).
    target_channels : int      Channels for final WAV (default 1 = mono).
    quiet : bool               Suppress yt-dlp logs if True.
    keep_intermediate : bool   Keep the pre-downsampled WAV if True.
    progress_hook : callable   Optional yt-dlp progress hook.

    Raises
    ------
    YTDLPError on failure.
    """
    if not youtube_url or not isinstance(youtube_url, str):
        raise ValueError("youtube_url must be a non-empty string.")

    _require("ffmpeg")  # we call ffmpeg ourselves
    # yt-dlp bundles ffmpeg via postprocessors, but we still run ffmpeg explicitly

    work_dir = Path(out_dir or tempfile.mkdtemp(prefix="ytwav_")).resolve()
    work_dir.mkdir(parents=True, exist_ok=True)

    # First stage: let yt-dlp extract WAV (whatever SR/channels)
    out_template = str(work_dir / "%(title).100B [%(id)s].%(ext)s")
    hooks = [progress_hook] if progress_hook else []

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": out_template,
        "noplaylist": True,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
                "preferredquality": "0",
            }
        ],
        "quiet": quiet,
        "no_warnings": quiet,
        "progress_hooks": hooks,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(youtube_url, download=True)
    except Exception as e:
        #raise YTDLPError(f"yt-dlp API failed: {e}") from e
        return f"yt-dlp API failed: {e}"

    # Locate the produced WAV (pre-downsampled)
    pre_wavs = list(work_dir.glob("*.wav"))
    if not pre_wavs:
        #raise YTDLPError("yt-dlp completed but no WAV was found.")
        return "yt-dlp completed but no WAV was found."
    pre_wav = max(pre_wavs, key=lambda p: p.stat().st_mtime)

    # Second stage: force 16 kHz mono via ffmpeg
    final_wav = pre_wav.with_name(pre_wav.stem + f".{target_sr}Hz.{target_channels}ch.wav")
    try:
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", str(pre_wav),
                "-ac", str(target_channels),
                "-ar", str(target_sr),
                str(final_wav),
            ],
            check=True,
            stdout=subprocess.PIPE if quiet else None,
            stderr=subprocess.PIPE if quiet else None,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        #raise YTDLPError(f"ffmpeg failed to resample: {e.stderr or e.stdout}") from e
        return f"ffmpeg failed to resample: {e.stderr or e.stdout}"

    # 3) upload + sign (short-lived)
    signed = upload_and_sign(final_wav, ttl_minutes=45)
    
    # Clean up intermediates if desired
    if not keep_intermediate:
        try:
            if pre_wav.exists() and pre_wav != final_wav:
                pre_wav.unlink()
        except Exception:
            pass
    
    return {"status": "ready", "audio_url": signed}
