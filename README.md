# AudioSummarizer

## Overview
AudioSummarizer is a web application deployed on Hugging Face Spaces that summarizes audio content from multiple sources—file upload, microphone recording, or URL download (including YouTube)—using the Phi-4-multimodal-instruct model deployed on Azure for summarization of audio and transcribed text. The app supports YouTube URL transcription using the faster-whisper model and yt-dlp for audio extraction, with a user-friendly Gradio UI. System and user prompts are loaded from a metadata.json file to provide structured responses.

## Features
- Upload a local MP3 file, record audio via microphone, or provide a YouTube or standard MP3 URL.
- Create your own system and user prompts.
- Transcribes YouTube videos using faster-whisper and summarizes audio or text using Phi-4-multimodal-instruct on Azure.
- Configurable system and user prompts, with defaults loaded from metadata.json for structured output (Summary, Key Details, Insights).
- Clean and minimal Gradio UI for easy interaction.
- Environment-based configuration using API key authentication for Azure.
- YouTube audio extraction to 16 kHz mono WAV using yt-dlp and ffmpeg.
- DNS lookup for URL validation and robust error handling for YouTube processing.

## Architecture Overview
```
 ┌───────────────┐     file/mic/url     ┌───────────────────────┐
 │   Gradio UI   │  ──────────────────▶ │  process_audio(...)    │
 └──────┬────────┘                      └──────────┬─────────────┘
        │                                        validates/reads
        │                             ┌───────────────────────────┐
        │                             │ encode_audio(...)         │
        │                             │ download_to_temp_mp3(...) │
        │                             |                           |
        │                             └──────────┬────────────────┘
        │                                        │ base64 audio/text
        ▼                                        ▼
 ┌───────────────────────────┐        ┌─────────────────────────────┐
 │ summarize_input(audio,...)│  ───▶  │ Azure Phi-4-multimodal-instruct → │
 └───────────────────────────┘        │ Chat Completions           │
                                     │ (multimodal: text + audio)  │
                                     └─────────────────────────────┘

 YouTube Path:
 ┌───────────────┐     YouTube URL     ┌───────────────────────────┐
 │   Gradio UI   │  ──────────────────▶ │ download_youtube_audio_wav16k_api(...) │
 └───────────────┘                      └──────────┬────────────────┘
                                                │ 16kHz mono WAV
                                                ▼
                                     ┌─────────────────────────────┐
                                     │ transcribe_faster_whisper(...) │
                                     └──────────┬────────────────┘
                                                │ transcribed text
                                                ▼
                                     ┌─────────────────────────────┐
                                     │ Azure Phi-4-multimodal-instruct → │
                                     │ Chat Completions           │
                                     │ (multimodal: text)          │
                                     └─────────────────────────────┘
```

## Prerequisites
- Python 3.10 or higher.
- An Azure subscription with access to the Phi-4-multimodal-instruct model deployed on Azure.
- ffmpeg installed and available in PATH for YouTube audio processing.
- A metadata.json file with system and user prompt defaults.
- For deployment, a Hugging Face Spaces environment with packages.txt configured.

## Python Dependencies
Create a `requirements.txt` with the following:
```
azure-identity>=1.17.1
openai>=1.0.0
gradio>=4.44.0
python-dotenv>=1.0.1
requests>=2.32.3
yt-dlp>=2024.8.6
faster-whisper>=0.10.0
```

Install dependencies:
```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## System Dependencies
Install ffmpeg:
- Ubuntu/Debian: `sudo apt-get install ffmpeg`
- macOS: `brew install ffmpeg`
- Windows: [Download from ffmpeg.org](https://ffmpeg.org) and add to PATH

For Hugging Face Spaces, create a `packages.txt` file at the project root with:
```
ffmpeg
```

## Installation
```bash
git clone https://github.com/samir72/AudioChatTranscriber.git
cd AudioChatTranscriber
```
Install dependencies (see above).  
Ensure ffmpeg is installed and available in PATH, or include packages.txt for Hugging Face Spaces builds.

## Configuration
Create a `.env` file at the project root:
```env
AC_OPENAI_ENDPOINT=https://<your-resource>.openai.azure.com/
AC_MODEL_DEPLOYMENT=<your-phi-4-multimodal-instruct-deployment-name>
AC_OPENAI_API_KEY=<your-api-key>
AC_OPENAI_API_VERSION=<your-api-version>
GRADIO_SERVER_NAME=127.0.0.1
GRADIO_SERVER_PORT=7860
```

Create a `metadata.json` file at the project root (see example in repo).

For Hugging Face Spaces, create a `packages.txt` file with:
```
ffmpeg
```

## Usage
Run locally:
```bash
python app.py
```
Open the URL printed by Gradio (default: [http://127.0.0.1:7860](http://127.0.0.1:7860)) or visit the Hugging Face Spaces deployment.

### Input Methods
- Upload an MP3 file
- Record audio via microphone
- Enter a YouTube or standard MP3 URL
- Modify system/user prompts (defaults loaded from `metadata.json`)
- Click **Summarize** to view the structured response

## Code Walkthrough
- `process_audio(...)`: Orchestrates input selection and summarization
- `encode_audio_from_path(...)`: Encodes audio files to Base64
- `download_to_temp_mp3(...)`: Downloads MP3 URLs to temporary files
- `download_youtube_audio_wav16k_api(...)`: Converts YouTube audio to 16 kHz mono WAV
- `transcribe_faster_whisper(...)`: Transcribes audio
- `summarize_input(...)`: Calls Azure Phi-4-multimodal-instruct Chat Completions
- `retrieve_json_record(...)`: Loads prompts from metadata.json
- `nslookup(...)`: Validates URL domains
- `ensure_ffmpeg(...)`: Verifies ffmpeg availability

## Troubleshooting
- Credential errors → Verify API key and Azure resource
- Deployment not found → Confirm model deployment name
- HTTP 403/401 → Check key permissions
- Misconfiguration → Validate `.env` values
- YouTube errors → Verify yt-dlp + ffmpeg installation
- Metadata errors → Ensure JSON structure is valid

## Improvements & TODOs
- Standardize audio format handling
- Improve error handling & feedback
- Multi-turn conversation support
- Metadata validation
- Chunked summarization for long YouTube videos

## Project Structure
```
.
├── app.py
├── Youtubetranscription_summarizer.py
├── requirements.txt
├── .env
├── metadata.json
├── packages.txt
├── README.md
└── LICENSE
```

## Contributing
Contributions are welcome!
1. Fork the repository
2. Create a new branch (`git checkout -b feature/your-feature-name`)
3. Commit changes (`git commit -m "Add feature"`)
4. Push to branch (`git push origin feature/your-feature-name`)
5. Open a pull request

## License
MIT License - see [LICENSE](./LICENSE)

## Acknowledgments
- Built with **Gradio** for UI  
- Deployed on **Hugging Face Spaces**
- Intelligence by **Azure Phi-4-multimodal-instruct**  
- YouTube audio extraction with **yt-dlp**  
- Transcription enabled by **faster-whisper**  


## Contact
For questions or feedback, contact Sayed Amir Rizvi @ syedamirhusain@gmail.com
