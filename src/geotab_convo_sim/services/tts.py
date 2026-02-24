import os
import streamlit as st
from openai import OpenAI

_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


@st.cache_data(show_spinner=False)
def _get_tts_audio(text: str, voice: str, speed: float) -> bytes:
    response = _client.audio.speech.create(
        model="tts-1",
        voice=voice,
        input=text,
        speed=speed,
    )
    return response.content

def speak_text(text: str, voice: str = "nova"):
    """Use OpenAI Text-to-Speech API to speak text aloud with natural voice.
    """
    if not text or not text.strip():
        return
    
    try:
        audio_bytes = _get_tts_audio(text=text, voice=voice, speed=1.2)
        st.audio(audio_bytes, format="audio/mp3", autoplay=True)
        
    except Exception as e:
        st.error(f"Text-to-speech failed: {str(e)}")
