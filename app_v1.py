import os
import base64
import tempfile
import requests
from datetime import datetime
import gradio as gr
from dotenv import load_dotenv
from openai import AzureOpenAI  # official OpenAI SDK, works with Azure endpoints
import json
import subprocess # to execute youtube-dl version
import Youtubetranscription_summarizer

# --- LLM call (Azure OpenAI with API key) -----------------------------------

def summarize_audio_b64(audio_b64: str, sys_prompt: str, user_prompt: str) -> str:
    """
    Calls Azure OpenAI Chat Completions with audio input (base64 mp3).
    """
    load_dotenv()

    endpoint = os.getenv("AC_OPENAI_ENDPOINT")
    api_key = os.getenv("AC_OPENAI_API_KEY")
    deployment = os.getenv("AC_MODEL_DEPLOYMENT")
    api_version = os.getenv("AC_OPENAI_API_VERSION")

    if not endpoint or not api_key or not deployment:
        return "Server misconfiguration: required env vars missing."
    

    try:
        client = AzureOpenAI(
            api_key=api_key,
            api_version=api_version,
            azure_endpoint=endpoint,
        )

        system_message = sys_prompt.strip() if sys_prompt else (
            "You are an AI assistant with a charter to clearly analyze the customer enquiry."
        )
        user_text = user_prompt.strip() if user_prompt else "Summarize the audio content."

        response = client.chat.completions.create(
            model=deployment,
            messages=[
                {"role": "system", "content": system_message},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_text},
                        {
                            "type": "input_audio",
                            #"input_audio": {"data": audio_b64, "format": "mp3"},
                            "input_audio": {"data": audio_b64, "format": "wav"},
                        },
                    ],
                },
            ],
        )
        print(f"Azure API call at {datetime.now()}: prompt_length={len(user_prompt)}, audio_size={len(audio_b64)}")
        return response.choices[0].message.content

    except Exception as ex:
        return print(f"Error from Azure OpenAI: {ex}")
        #pass

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


def process_audio(upload_path, record_path, url, sys_prompt, user_prompt):
    tmp_to_cleanup = []
    try:
        audio_path = None
        if upload_path:
            audio_path = upload_path
        elif record_path:
            audio_path = record_path
        elif url and url.strip():
            #audio_path = download_to_temp_mp3(url.strip())
            audio_path = Youtubetranscription_summarizer.main(url.strip())
            tmp_to_cleanup.append(audio_path)

        if not audio_path:
            return "Please provide an audio file via upload, recording, or URL."

        audio_b64 = encode_audio_from_path(audio_path)
        return summarize_audio_b64(audio_b64, sys_prompt, user_prompt)

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
    gr.Markdown("Upload a mp3, record audio, or paste a URL. The app sends base64 audio to Azure OpenAI.")

    with gr.Row():
        with gr.Column():
            upload_audio = gr.Audio(sources=["upload"], type="filepath", label="Upload mp3")
        with gr.Column():
            record_audio = gr.Audio(sources=["microphone"], type="filepath", label="Record Audio")
        with gr.Column():
            url_input = gr.Textbox(label="mp3 URL", placeholder="https://example.com/audio.mp3")

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
