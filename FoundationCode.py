# Add references
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
import gradio as gr
from dotenv import load_dotenv
import requests
import os
import tempfile
import base64

# Placeholder for your summarization function.
# Replace this with your actual function that takes a WAV file path and returns the summary.
def summarize_audio(audio_data,sysprompt,userprompt):
    # Code to summarize the audio file using LLM and Azure OpenAI

    try: 

            # Get configuration settings 
            load_dotenv()
            project_endpoint = os.getenv("AC_PROJECT_ENDPOINT")
            model_deployment =  os.getenv("AC_MODEL_DEPLOYMENT")

            # Initialize the project client
            project_client = AIProjectClient(            
                credential=DefaultAzureCredential(
                    exclude_environment_credential=True,
                    exclude_managed_identity_credential=True
                ),
                endpoint=project_endpoint,
            )


            # Get a chat client
            openai_client = project_client.get_openai_client(api_version="2024-10-21")
            

            # Initialize prompts
            if sysprompt:
                system_message = sysprompt
            else:
                system_message = "You are an AI assistant with a charter to clearly analyse the customer enquiry."
            
            prompt = ""

            # Loop until the user types 'quit'
            while True:
                #prompt = input("\nAsk a question about the audio\n(or type 'quit' to exit)\n")
                if userprompt:
                    prompt = userprompt
                else:
                    prompt = "quit"
                if prompt.lower() == "quit":
                    break
                elif len(prompt) == 0:
                        print("Please enter a question.\n")
                else:
                    print("Getting a response ...\n")

                    # Encode the audio file
                    #audio_data = encode_audio(wav_path)

                    # Get a response to audio input
                    response = openai_client.chat.completions.create(
                        model=model_deployment,
                        messages=[
                            {"role": "system", "content": system_message},
                            { "role": "user",
                                "content": [
                                { 
                                    "type": "text",
                                    "text": prompt
                                },
                                {
                                    "type": "input_audio",
                                    "input_audio": {
                                        "data": audio_data,
                                        "format": "mp3"
                                    }
                                }
                            ] }
                        ]
                    )
                    print(response.choices[0].message.content)
                    userprompt = ""
                
    except Exception as ex:
            print(ex)
    return response.choices[0].message.content

def encode_audio(audio_file,action):
        """Encode audio files in the specified folder to base64."""
        try:
                if action == "Read":
                    with open(audio_file, 'rb') as audio_file:
                        audio_data = base64.b64encode(audio_file.read()).decode('utf-8')
                    return audio_data
                elif action == "Download":
                     audio_data = base64.b64encode(audio_file).decode('utf-8')
                     return audio_data
                     
        except Exception as e:
            raise ValueError(f"Failed to encode audio file: {str(e)}")

def download_wav_from_url(url):
    if not url:
        return None
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        return response.content
    except Exception as e:
        raise ValueError(f"Failed to download WAV from URL: {str(e)}")

def process_audio(upload_audio, record_audio, url,sysprompt,userprompt):
    wav_path = None
    temp_files = []  # To clean up temp files later if needed
    
    if upload_audio:
        wav_path = upload_audio
        audio_data = encode_audio(wav_path,"Read")
    elif record_audio:
        wav_path = record_audio
        audio_data = encode_audio(wav_path,"Read")
    elif url:
        wav_path = download_wav_from_url(url)
        audio_data = encode_audio(wav_path,"Download")
        if audio_data:
            temp_files.append(audio_data)
    
    if not wav_path:
        return "Please provide an audio file via upload, recording, or URL."
    
    try:
        summary = summarize_audio(audio_data,sysprompt,userprompt)
        return summary
    finally:
        # Optional: Clean up temp files
        for temp in temp_files:
            if os.path.exists(temp):
                os.remove(temp)

with gr.Blocks(title="Audio Summarizer UI") as demo:
    gr.Markdown("# Audio File Summarizer")
    gr.Markdown("Upload a WAV file, record audio, or provide a URL to a WAV file for summarization.")
    
    with gr.Row():
        with gr.Column():
            upload_audio = gr.Audio(sources="upload", type="filepath", label="Upload WAV File")
        with gr.Column():
            record_audio = gr.Audio(sources="microphone", type="filepath", label="Record Audio")
        with gr.Column():
            url_input = gr.Textbox(label="Enter URL to WAV File", placeholder="https://example.com/audio.wav")
        with gr.Column():
            userprompt_input = gr.Textbox(label="Enter User Prompt", placeholder="Ask a question about the audio",value="Summarize the audio content")
        with gr.Column():
            sysprompt_input = gr.Textbox(label="Enter System Prompt",value="You are an AI assistant with a listening charter to clearly analyse the customer enquiry.")
    
    submit_btn = gr.Button("Summarize")
    output = gr.Textbox(label="Summary", lines=10)
    
    submit_btn.click(
        fn=process_audio,
        inputs=[upload_audio, record_audio, url_input,sysprompt_input,userprompt_input],
        outputs=output
    )

demo.launch()