import os
import base64
import tempfile
import requests
from datetime import datetime
import gradio as gr
from dotenv import load_dotenv
from openai import AzureOpenAI  # official OpenAI SDK, works with Azure endpoints
import json
import subprocess
import Youtubetranscription_summarizer
from app.app.Youtubeextraction import extract  # Youtube download helper functions 
#from pydantic import BaseModel, AnyUrl # Pydantic models for request validation in yiutube extraction
#from fastapi import FastAPI, HTTPException # FastAPI for building the API
#app = FastAPI() ## Initialize FastAPI app for testing in local
#from extractor.app.storage import upload_and_sign  # Youtube storage helper functions
import re

# --- LLM call (Azure OpenAI with API key) -----------------------------------

def summarize_input(audio_b64: str = None, text_input: str = None, sys_prompt: str = None, user_prompt: str = None, Starttime: datetime = None) -> str:
    """
    Calls Azure OpenAI Chat Completions with audio input (base64 mp3) or text input, or both.
    """
    load_dotenv()

    endpoint = os.getenv("AC_OPENAI_ENDPOINT")
    api_key = os.getenv("AC_OPENAI_API_KEY")
    deployment = os.getenv("AC_MODEL_DEPLOYMENT")
    api_version = os.getenv("AC_OPENAI_API_VERSION")

    if not endpoint or not api_key or not deployment:
        return "Server misconfiguration: required env vars missing."
    # Reset json_text for logging
    json_text = ""
    try:
        client = AzureOpenAI(
            api_key=api_key,
            api_version=api_version,
            azure_endpoint=endpoint,
        )

        system_message = sys_prompt.strip() if sys_prompt else (
            "You are an AI assistant with a charter to clearly analyze the customer enquiry."
        )
        user_text = user_prompt.strip() if user_prompt else (
            "Summarize the provided content." if audio_b64 or text_input else "No input provided."
        )

        content = [{"type": "text", "text": user_text}]
        
        if audio_b64:
            content.append({
                "type": "input_audio",
                "input_audio": {"data": audio_b64, "format": "mp3"},
            })
        if text_input is not None:
            # Debugging: Print the type and value of text_input
            #print(f"Debug: text_input type={type(text_input)}, value={text_input}")
            if isinstance(text_input, str):
                try:
                    # Try to parse the string as JSON to see if it's a list or dict
                    parsed = json.loads(text_input)
                    if isinstance(parsed, (list, dict)):
                        # If it's a list or dict, convert back to JSON string
                        content.append({"type": "text", "text": json.dumps(parsed)})
                    else:
                        # If it's a string but not a JSON list/dict, use it as-is
                        content.append({"type": "text", "text": text_input})
                except json.JSONDecodeError:
                    # If it's not valid JSON, treat it as a regular string
                    content.append({"type": "text", "text": text_input})
            elif isinstance(text_input, (list, dict)):
                try:
                    # Convert list or dict to JSON-formatted string
                    json_text = json.dumps(text_input)
                    content.append({"type": "text", "text": json_text})
                except (TypeError, ValueError):
                    return "Error: text_input (list or dict) could not be converted to JSON."
            else:
                return f"Error: text_input must be a string, list, or dict, got {type(text_input)}."
            
        response = client.chat.completions.create(
            model=deployment,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": content},
            ],
        )
        Enddate = datetime.now()
        Callduration = Enddate - Starttime[0]
        print(f"AudioChatSummarizer API call with a duration of {Callduration}: prompt_length={len(user_prompt or '')}, "
              f"audio_size={len(audio_b64 or '')}, text_input_size={len(json_text or '')}")
        return response.choices[0].message.content

    except Exception as ex:
        return print(f"Error from Azure OpenAI: {ex}")

#----Retrieve meta data from metadata.json file------------------------------
def retrieve_file_path(file_name):
    path = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(path, file_name)
    if os.path.isfile(file_path):
        return file_path
    elif not os.path.exists(file_path):
        print(f"'{file_path}' does not exist.")
        return None
    return None

def retrieve_json_record(file_path, record_id):
    with open(file_path, 'r') as file:
        data = json.load(file)
        if isinstance(data, list):
            for record in data:
                if record.get('metadata', {}).get('id') == record_id:
                    return record
        elif isinstance(data, dict):
            if data.get('metadata', {}).get('id') == record_id:
                return data
    return None
# --- I/O helpers ------------------------------------------------------------

def encode_audio_from_path(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def download_to_temp_mp3(url: str) -> str:
    r = requests.get(url, stream=True, timeout=30)
    r.raise_for_status()
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
        for chunk in r.iter_content(chunk_size=8192):
            if chunk:
                tmp.write(chunk)
        return tmp.name

# function to read files
def file_read(filepath):
    file_data = []
            
    try:
        with open(filepath, "rb") as f:
            file_data = f.read()
            
            print(f"Successfully validated {file_path} and read {len(file_data)} bytes.")
    except Exception as e:
                print(f"Could not read {file_path}: {e}")

    return file_data

###Download youtube video and extract audio using yt-dlp and ffmpeg

EXTRACT_API = os.getenv("AZURE_CONTAINER_APP_FQDN") ## Fast API endpoint for youtube extraction "https://<your-app-fqdn>/extract"
def fetch_audio_from_youtube(url):
    
    try:    
        r = requests.post(EXTRACT_API, json={
            "url": url,
            "format": "wav",
            "sample_rate": 16000,
            "mono": True
        }, timeout=90)
        r.raise_for_status()
        return r.json()["audio_url"]
    
    except Exception as e:
        print(f"{datetime.now()}: Error retrieving youtube wave file: {url} from Azure instance: {str(e)}")
        return (f"{datetime.now()}: Error retrieving youtube wave file from Azure instance : {url}")
        
def process_audio(upload_path, record_path, url, sys_prompt, user_prompt):
    tmp_to_cleanup = []
    audio_b64 = None
    text_input = None
    domaincheck = None
    extract_input = None
    audio_wav = None

    try:
        # Capture start time for logging
        Starttime = datetime.now(),
        print(f"AudioChatSummarizer API call starts at {datetime.now()}"),
        audio_path = None
        if upload_path:
            audio_path = upload_path
        elif record_path:
            audio_path = record_path
        elif url and url.strip():
            # Check dns resolution of the url domain
            domain = Youtubetranscription_summarizer.extract_domain(url)
            if domain:
                domaincheck = Youtubetranscription_summarizer.nslookup(domain)  # Check DNS resolution of the domain
            else:
                return "Invalid URL format."
            
            if domaincheck:
                # Check if the url is a youtube link
                CheckURL = re.search(r"Youtube", url, re.IGNORECASE)
                
                if CheckURL:
                    # Get the transcription from youtube
                    # text_input = Youtubetranscription_summarizer.main(url.strip()) # Youtube files are transcribed and summarized
                    extract_input = extract(url.strip()) # Youtube files are extracted from Azure instance.
                    # Test wav file transcription using faster-whisper
                    audio_wav = fetch_audio_from_youtube(extract_input['audio_url'])
                    #file_path = "/Users/sayedarizvi/AudioSummarizer/Data/test.wav"
                    #audio_wav = file_path
                    text_input = Youtubetranscription_summarizer.transcribe_faster_whisper(audio_wav, model_name="base.en")
                    #text_input = transcript['segments']
                    #audio_path = text_input['audio_filepath']
                    #tmp_to_cleanup.append(text_input)
                    tmp_to_cleanup.append(text_input)
                else:   
                    audio_path = download_to_temp_mp3(url.strip())
                    tmp_to_cleanup.append(audio_path)
            else:
                return f"DNS lookup failed for {domain}"
        if not audio_path and text_input is None:
            return "Please provide content via upload, recording, or URL."
        # If we have an audio file, encode it
        if audio_path:
            audio_b64 = encode_audio_from_path(audio_path)
        return summarize_input(audio_b64, text_input, sys_prompt, user_prompt, Starttime)

    except Exception as e:
        return print(f"Error processing audio at {datetime.now()}: prompt_length={len(user_prompt)}, audio_path={audio_path}: {str(e)}")
        

    finally:
        for p in tmp_to_cleanup:
            try:
                if os.path.exists(p):
                    os.remove(p)
            except Exception:
                pass


# --- UI ---------------------------------------------------------------------

with gr.Blocks(title="Audio Summarizer") as demo:
    gr.Markdown("# Audio File Summarizer (Azure OpenAI)")
    gr.Markdown("Upload an mp3(**YouTube is the new feature add**), record audio, or paste a URL, use the default user prompt and system prompt and  click 'Summarize'.")
    gr.Markdown("Users are encouraged to modify the user and system prompts to suit their needs.")

    with gr.Row():
        with gr.Column():
            upload_audio = gr.Audio(sources=["upload"], type="filepath", label="Upload mp3")
        with gr.Column():
            record_audio = gr.Audio(sources=["microphone"], type="filepath", label="Record Audio")
        with gr.Column():
            url_input = gr.Textbox(label="YouTube or standard mp3 URL", placeholder="https://example.com/audio.mp3")

    ### Get system and user prompts from metadata.json file
    file_name = 'metadata.json'
    record_id = '1'
    file_path = retrieve_file_path(file_name)
    
    jsonrecord = retrieve_json_record(file_path, record_id)
    if jsonrecord:
        print(json.dumps(jsonrecord, indent=2))
    else:
        print("Record not found.")

    sysprompt_default = jsonrecord['metadata']['content']['system_prompt']['content']
    userprompt_default = jsonrecord['metadata']['content']['user_prompt']['content']

    with gr.Row():
        userprompt_input = gr.Textbox(
            label="User Prompt",
            #value="Summarize the audio content",
            value=userprompt_default,
            placeholder="e.g., Extract key points and action items",
        )
        sysprompt_input = gr.Textbox(
            label="System Prompt",
            #value="You are an AI assistant with a charter to clearly analyze the customer enquiry.",
            value=sysprompt_default,
        )

    submit_btn = gr.Button("Summarize")
    output = gr.Textbox(label="Summary", lines=12)

    # Capture inputs for logging
    if upload_audio:
        upload_audio.change(
            fn=lambda x: print(f"Upload audio selected: {x}"),
            inputs=[upload_audio],
            outputs=[],
            # Reset other inputs to avoid confusion
        )
    if record_audio:
        record_audio.change(
            fn=lambda x: print(f"Record audio selected: {x}"),
            inputs=[record_audio],
            outputs=[],
        )
    if url_input:
        url_input.change(
            fn=lambda x: print(f"URL input changed: {x}"),
            inputs=[url_input],
            outputs=[],
        )
    submit_btn.click(
        fn=process_audio,
        inputs=[upload_audio, record_audio, url_input, sysprompt_input, userprompt_input],
        outputs=output,
    )

if __name__ == "__main__":
    demo.launch()
