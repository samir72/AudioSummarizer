import os, tempfile, subprocess, re
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, AnyUrl
from typing import Optional
from utils.storage import upload_and_sign   # To remove circular import issue

app = FastAPI()
YTDLP = os.getenv("YTDLP_BIN", "yt-dlp")
FFMPEG = os.getenv("FFMPEG_BIN", "ffmpeg")

class ExtractReq(BaseModel):
    url: AnyUrl
    format: str = "wav"        # "wav"|"mp3"
    sample_rate: int = 16000
    mono: bool = True
    transcript: bool = False   # reserved for future
    language_hint: Optional[str] = None

def is_youtube(u: str) -> bool:
    return re.search(r"(youtube\.com|youtu\.be)", u, re.I) is not None

def run(cmd: list[str]):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr[:800])
    return p.stdout

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/extract")
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
