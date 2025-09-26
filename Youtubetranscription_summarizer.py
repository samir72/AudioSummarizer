import os, tempfile, subprocess, json, re, time, shutil
from pathlib import Path
from typing import Optional, Callable, Any
import yt_dlp
from faster_whisper import WhisperModel
import socket


def main(url:str):
    # Get YouTube URL from user
    ensure_ffmpeg()
    url = get_video_id(url)
    #Pass the URL to download audio and convert to wav
    wav_path = download_youtube_audio_wav16k_api(url)
    #Transcribe the audio wav file 
    transcript = transcribe_faster_whisper(wav_path, model_name="base.en")
    #print(f"Transcription completed. Language: {transcript['language']}")
    #print(json.dumps(transcript, indent=2))
    #Summarize the transcript using Phi
    return transcript

def nslookup(domain):
    try:
        # Perform DNS lookup for the domain
        addresses = socket.getaddrinfo(domain, None)
        print(f"DNS lookup succesfull for {domain}:")
        return True
        # for addr in addresses:
        #     # Extract IP address from the result
        #     ip = addr[4][0]
        #     print(f"IP Address: {ip}")
    except socket.gaierror as e:
        print(f"DNS lookup failed for {domain}: {e}")
        return True # Assume true as youtube DNS will fail on huggingface
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return False

def extract_domain(url):
    # Regular expression to match the domain name
    # Matches http:// or https://, followed by the domain (e.g., audio-samples.github.io)
    pattern = r'https?://([a-zA-Z0-9.-]+)'
    match = re.search(pattern, url)
    if match:
        return match.group(1)
    else:
        return None
    
def get_video_id(url:str)->str:
    # Extract video ID from various YouTube URL formats
    m = re.search(r"(?:v=|/shorts/|/live/|/embed/)([A-Za-z0-9_-]{6,})", url)
    return m.group(1) if m else str(abs(hash(url)))

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

def download_youtube_audio_wav16k_api(
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

    # Clean up intermediates if desired
    if not keep_intermediate:
        try:
            if pre_wav.exists() and pre_wav != final_wav:
                pre_wav.unlink()
        except Exception:
            pass

    return str(final_wav)


def transcribe_faster_whisper(wav_path:str, model_name="base.en"):
    try:
        model = WhisperModel(model_name)
        segments, info = model.transcribe(wav_path, beam_size=1, vad_filter=True)
        out = []
        for s in segments:
            out.append({"start": s.start, "end": s.end, "text": s.text})
        #return {"language": info.language, "segments": out}
        return {"segments": out}
    except Exception as e:
        return f"Faster-Whisper transcription failed: {e}"

def summarize_with_phi(transcript_segments, sysprompt, userprompt, phi_client):
    # map-reduce pseudo:
    CHUNK_SEC = 600  # ~10min per chunk as a starting point
    chunks, cur, cur_t = [], [], 0.0
    for seg in transcript_segments:
        cur.append(seg); cur_t += (seg["end"]-seg["start"])
        if cur_t >= CHUNK_SEC:
            chunks.append(cur); cur, cur_t = [], 0.0
    if cur: chunks.append(cur)

    partials = []
    for idx, chunk in enumerate(chunks, 1):
        text = "\n".join(f"[{int(s['start']//60):02d}:{int(s['start']%60):02d}] {s['text']}" for s in chunk)
        prompt = f"{userprompt}\n\nTRANSCRIPT CHUNK {idx}:\n{text}\n\nReturn: bullet summary + key timestamps."
        partials.append(phi_client.summarize(sysprompt, prompt))  # your existing call

    merged_prompt = f"Merge the {len(partials)} chunk summaries into one concise summary + top 5 timestamps."
    return phi_client.summarize(sysprompt, merged_prompt + "\n\n" + "\n\n".join(partials))

if __name__ == "__main__":
    main(url=None)  # for local testing