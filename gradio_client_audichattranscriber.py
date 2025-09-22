from datetime import datetime
import gradio as gr
from dotenv import load_dotenv
from gradio_client import Client  # Gradio client for Hugging Face models

def main():
    """
    Calls Gradio app hosted on Hugging Face using Gradio client.
    """
    load_dotenv() # Load .env file for HF token if needed


    try:
        client = Client("samir72/AudioChatTranscriber")  # Hugging Face model with Gradio app
        #client.view_api()  # View available API endpoints
        response = client.predict(
			upload_path=None,
            record_path=None,
            url="https://audio-samples.github.io/samples/mp3/blizzard_biased/sample-0.mp3",
			sys_prompt="You are an AI assistant with a listening charter to clearly analyze the customer enquiry.",
			user_prompt="Summarize the audio content",
			api_name="/process_audio"
        )
        print(f"Gradio API call at {datetime.now()}")
        print(f"Summarized Output : {response}")
        return response

    except Exception as ex:
        return print(f"Error calling Gradio app: {ex}")
        #pass



if __name__ == "__main__":
    main()
