# ---------- Base ----------
#FROM python:3.11-slim
FROM cab337fa40e5acr.azurecr.io/python:3.11-slim

# ---------- System deps ----------
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg ca-certificates curl \
 && rm -rf /var/lib/apt/lists/*

# ---------- Workdir ----------
WORKDIR /workspace

# ---------- Python deps ----------
# requirements.txt is at AUDIOSUMMARIZER/extract/requirements.txt

COPY app/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
&& pip install --no-cache-dir -r requirements.txt

# ---------- App code ----------
# Copy EVERYTHING under AUDIOSUMMARIZER/extract (includes subfolders: app/ and utils/)
COPY . /workspace/extract

# Make /workspace importable so "extract.app.Youtubeextraction" & "app.utils..." work
ENV PYTHONPATH=/workspace

# Runtime env (override at deploy)
ENV HOST=0.0.0.0
ENV PORT=8080
ENV AZURE_STORAGE_ACCOUNT=__SET_AT_DEPLOY__
ENV AZURE_BLOB_CONTAINER=__SET_AT_DEPLOY__
ENV COOKIES_ACCOUNT=__SET_AT_DEPLOY__
ENV COOKIES_CONTAINER=__SET_AT_DEPLOY__
ENV COOKIES_BLOB=__SET_AT_DEPLOY__
ENV COOKIES_PATH=__SET_AT_DEPLOY__
ENV COOKIES_REFRESH_SEC=__SET_AT_DEPLOY__

EXPOSE 8080

# Your ASGI app is defined in extract/app/Youtubeextraction.py as `app = FastAPI()`
CMD ["uvicorn", "extract.app.Youtubeextraction:app", "--host", "0.0.0.0", "--port", "8080"]