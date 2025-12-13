from google.cloud import texttospeech
import os
from dotenv import load_dotenv

load_dotenv()

def list_voices():
    try:
        client = texttospeech.TextToSpeechClient()
        response = client.list_voices(language_code="zh-CN")
        
        print("\n--- Available Chinese (Simplified) Voices ---")
        voices = sorted(response.voices, key=lambda v: v.name)
        for voice in voices:
            # print(f"Name: {voice.name}, Gender: {voice.ssml_gender.name}")
            print(f"'{voice.name}', # {voice.ssml_gender.name}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    list_voices()
