# AudioSummarizer

## What’s New (Sep 26–28, 2025)
- **YouTube cookie refresh & expiry handling** added to avoid sign-in/download failures.  
- **DNS lookup improvements**: automatically skip DNS failures on Hugging Face Spaces to reduce false negatives.  
- **Azure Container App (ACA) integration**: bypasses YouTube blocking by offloading audio download to Azure, storing audio in Blob Storage, and feeding it into the HF pipeline.  
- **Docker / ACA enhancements**: uses Microsoft slim base image in ACR for faster builds, with trade-off that the base must be regularly refreshed.  
- **Repo restructuring**: renamed the app entry folder to `extract/` to resolve a Hugging Face build conflict.

---

## Overview
AudioSummarizer is a web app (deployed on Hugging Face Spaces) that summarizes audio from multiple sources — file upload, microphone, or URL (YouTube / direct MP3) — using the **Phi‑4‑multimodal‑instruct** LLM model on Azure for structured summarization. The app uses **faster‑whisper** for transcription and **yt-dlp** + **ffmpeg** for audio extraction, with a clean **Gradio** UI. Prompts are loaded from `metadata.json` to ensure replies include **Summary**, **Key Details**, and **Insights**.

Because Hugging Face often cannot directly fetch YouTube audio (due to network restrictions or blocking), we now route YouTube downloads through an **Azure Container App** which:

1. Fetches the YouTube audio independently.  
2. Stores the processed 16 kHz mono WAV file in **Azure Blob Storage**.  
3. Serves that file into the usual transcription/summarization pipeline in the HF app.

Thus, the HF interface remains unchanged to users, but YouTube support is restored reliably via Azure.

---

## Features
- Upload a local MP3 file, record via microphone, or enter a YouTube / MP3 URL.  
- **Azure Container App support** so YouTube content is reliably processed even if Hugging Face cannot fetch it.  
- Prompts fully customizable: you may define system and user prompts stored in `metadata.json`.  
- Transcription using **faster-whisper**, summarization through **Phi‑4‑multimodal-instruct** (Azure).  
- Clean and minimal **Gradio** UI for intuitive interaction.  
- Configuration via environment variables (`.env`) for Azure endpoint, deployment name, API key, etc.  
- YouTube audio extraction to **16 kHz mono WAV** (via yt-dlp + ffmpeg).  
- DNS‑based URL validation, with automatic skip of DNS errors in HF Spaces to reduce false rejections.

---

## Architecture / Data Flow

```
User Input (YouTube) ──▶ Hugging Face UI
   │
   └── If URL is YouTube:
         ─▶ forwarded to Azure Container App
               ├── ACA downloads YouTube audio (yt-dlp)
               └── Converts/stores WAV in Azure Blob Storage
         ─▶ HF app fetches WAV from Blob Storage
               ├── Transcribe via faster-whisper
               └── Summarize via Azure Phi‑4
               

 ┌───────────────┐ file/mic/url ┌───────────────────────────┐
 │   Gradio UI   │─────────────▶│ process_audio(...)         │
 └──────┬────────┘              └──────────┬─────────────────┘
        │ validates/reads                  │
        ▼                                  ▼
 ┌───────────────────────────┐   ┌─────────────────────────────┐
 │ summarize_input(audio,...)│──▶│ Azure Phi-4-multimodal-instr │
 └───────────────────────────┘   │ Chat Completions (text+audio)│
                                 └─────────────────────────────┘

 YouTube Path (via ACA):
 ┌───────────────┐  YouTube URL ┌──────────────────────────────┐
 │   Gradio UI   │────────────▶ │ Azure Container App (yt-dlp)  │
 └───────────────┘              └──────────┬───────────────────┘
                                           │ uploads audio
                                           ▼
                                ┌──────────────────────────────┐
                                │ Azure Blob Storage (WAV 16k) │
                                └──────────┬───────────────────┘
                                           │
                                           ▼
                              ┌──────────────────────────────┐
                              │ faster-whisper transcription │
                              └──────────┬───────────────────┘
                                           │ text
                                           ▼
                              ┌──────────────────────────────┐
                              │ Azure Phi-4-multimodal-instr │
                              │ summarization                │
                              └──────────────────────────────┘

```

For non-YouTube inputs (local upload, mic, direct MP3 URL), the flow remains internal to the HF space: download/convert → transcription → summarization.

---

## Docker & Azure Container Apps

### Optimization: Microsoft Slim Base in ACR
The Docker image now uses a **Microsoft slim base image** hosted in **Azure Container Registry (ACR)** to speed up builds (less reliance on external pulls).  
- ✅ **Advantage**: faster, more predictable builds in Azure / CI.  
- ⚠️ **Caveat**: you must **refresh the slim base in ACR routinely** to catch upstream security patches, updates, or bug fixes.

**Best Practice Recommendation:**  
Set up a scheduled job (e.g. via ACR Task or Azure DevOps pipeline) to pull the latest Microsoft slim base and update your ACR copy on a regular cadence (e.g. weekly) so your deployed containers remain current.

### Build & Run Example
```bash
# Build locally
docker build -t audiosummarizer:latest .

# Run container
docker run --rm -p 7860:7860   -e AC_OPENAI_ENDPOINT=...   -e AC_MODEL_DEPLOYMENT=...   -e AC_OPENAI_API_KEY=...   -e AC_OPENAI_API_VERSION=...   audiosummarizer:latest
```

For ACA deployment:
1. Push the Docker image to your ACR.
2. Deploy the image via **Azure Container Apps** with necessary environment variables.
3. The ACA will serve as the YouTube‐to‑Blob “fetcher” component, supporting the main HF app.

---

## Prerequisites
- Python **3.10+**  
- Azure subscription with deployment of **Phi‑4‑multimodal-instruct**  
- `ffmpeg` installed and in `$PATH`  
- A valid `metadata.json` containing default prompts  
- For HF spaces: `packages.txt` including `ffmpeg`  

---

## Python Dependencies
Add to `requirements.txt`:
```
azure-identity>=1.17.1
openai>=1.0.0
gradio>=4.44.0
python-dotenv>=1.0.1
requests>=2.32.3
yt-dlp>=2024.8.6
faster-whisper>=0.10.0
beautifulsoup4>=4.12.2   # optional, for fallback scraping
```

Install as usual:
```bash
python -m venv .venv
source .venv/bin/activate  # on Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

---

## Installation
```bash
git clone https://github.com/samir72/AudioSummarizer.git
cd AudioSummarizer
```
Install dependencies and make sure `ffmpeg` is available (or included via `packages.txt` in HF deployment).

---

## Configuration
Create a `.env` file at the project root:
```env
AC_OPENAI_ENDPOINT=https://<your-azure-resource>.openai.azure.com/
AC_MODEL_DEPLOYMENT=<your‑phi‑4 deployment name>
AC_OPENAI_API_KEY=<your azure openai api key>
AC_OPENAI_API_VERSION=<api version e.g. 2024-10-01>

GRADIO_SERVER_NAME=127.0.0.1
GRADIO_SERVER_PORT=7860
```

If you’re running the Azure Container App, ensure it is configured with:
- Proper role / access to write to Azure Blob Storage  
- Environment variables for any keys or connection strings it needs  
- Networking/firewall settings so the HF app can fetch from the blob store

---

## Usage
Run the app:
```bash
python app.py
```
Then open your browser to [http://127.0.0.1:7860](http://127.0.0.1:7860) or use your HF Space URL.

### Input options
- Upload MP3 file  
- Record via microphone  
- Enter a YouTube / direct MP3 URL  
- Modify system/user prompts (via `metadata.json`)  
- Click **Summarize** → get structured output (Summary, Key Details, Insights)

---

## Contributing
We welcome your improvements—especially around cloud integration, performance, and reliability.

**Suggested contribution areas:**
- Better error handling for cookie expiry, fallback strategies 
- Enhancements to the Azure Container App + Blob Storage pipeline  
- Caching / sync between ACA and the HF app  
- Automation of **ACR slim base refresh**  
 

**How to contribute:**
1. Fork the repository  
2. Create a feature branch (e.g. `git checkout -b feat/xyz`)  
3. Commit changes with meaningful messages  
4. Push and open a Pull Request  

Please reference this `README.md` when describing how the YouTube → ACA → Blob → HF flow works.

---

## License
This project is licensed under the **MIT License** — see [LICENSE](./LICENSE) for details.

---

## Acknowledgments
- Built with **Gradio** for UI 
- Application deployed on **Hugging Face Spaces**
- ACA deployed on **Azure**
- Application layer on ACA served by **FastAPI** 
- Intelligence by **Azure Phi-4-multimodal-instruct**  
- YouTube audio extraction with **yt-dlp**  
- Transcription enabled by **faster-whisper**

---


## Contact
For questions or feedback, reach out to **Sayed Amir Rizvi**  
Email: syedamirhusain@gmail.com  
