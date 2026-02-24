import streamlit as st


def render_text_input_section() -> str:
    """Render text input and return user input if provided.
    """
    if not st.session_state.voice_mode:
        text_input = st.chat_input("Type what you would say as the manager...")
        if text_input and text_input != st.session_state.last_sent_message:
            return text_input
    return ""
