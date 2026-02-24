import streamlit as st
import os
import tempfile
from openai import OpenAI


def handle_voice_input() -> str:
    """Handle voice input: recording and transcription.
    """
    st.markdown("### Voice Input")

    audio_value = st.audio_input("Click the mic icon below to record", key="audio_recorder")

    # Auto-transcribe when audio is recorded (only if new audio)
    if audio_value and not st.session_state.transcribed_text:
        current_audio_data = audio_value.read()
        current_audio_hash = hash(current_audio_data)
        audio_value.seek(0)  # Reset stream position

        should_transcribe = current_audio_hash != st.session_state.last_audio_hash
    else:
        should_transcribe = False
        current_audio_data = None

    if should_transcribe:
        with st.spinner("Transcribing..."):
            try:
                client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

                # Save audio to temporary file
                audio_bytes = current_audio_data
                with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_file:
                    tmp_file.write(audio_bytes)
                    tmp_file_path = tmp_file.name

                # Transcribe using Whisper
                with open(tmp_file_path, "rb") as audio_file:
                    transcript = client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file
                    )

                st.session_state.transcribed_text = transcript.text
                st.session_state.last_audio_hash = current_audio_hash
                st.session_state.last_sent_message = transcript.text

                # Clean up temp file
                os.unlink(tmp_file_path)

                st.success("Transcribed! Sending...")
                # Don't rerun here - return the text to send it immediately

            except Exception as e:
                st.error(f"Transcription failed: {str(e)}")
                return ""

    st.markdown("---")

    # Return transcribed text if available and not yet sent
    if st.session_state.transcribed_text and st.session_state.transcribed_text != st.session_state.get("last_returned_text", ""):
        text_to_return = st.session_state.transcribed_text
        st.session_state.last_returned_text = text_to_return
        st.session_state.transcribed_text = ""  # Clear for next message
        return text_to_return

    return ""


def render_voice_input_section() -> str:
    """Render the voice input section and return user input if provided.
    """
    if st.session_state.voice_mode:
        return handle_voice_input()
    return ""
