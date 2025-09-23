FROM python:3.11-slim

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg curl ca-certificates git \
    && rm -rf /var/lib/apt/lists/*

# Install yt-dlp (kept fresh)
RUN pip install --no-cache-dir yt-dlp

# App dependencies
WORKDIR /app
#Copy the contents of the extractor directory into the container
COPY ./extractor /app/
# Install Python dependencies from requirements.txt
COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

#COPY app /app/app
#COPY app /app/Youtubeextraction
#Copy storage py from folder outside app
#WORKDIR /utils
#COPY utils /utils/storage


ENV HOST=0.0.0.0 PORT=8080
ENV AZURE_STORAGE_ACCOUNT=__SET_AT_DEPLOY__
ENV AZURE_BLOB_CONTAINER=__SET_AT_DEPLOY__
#ENV YTDLP_BIN=yt-dlp
#ENV FFMPEG_BIN=ffmpeg

EXPOSE 8080
#CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
CMD ["uvicorn", "app.Youtubeextraction:app", "--host", "0.0.0.0", "--port", "8080"]
