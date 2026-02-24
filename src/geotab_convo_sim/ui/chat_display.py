import streamlit as st


def render_persona_info():
    """Render the current persona name and scenario."""
    if st.session_state.persona:
        st.write(f"**Name:** {st.session_state.persona.get('name', 'Unknown')}")
        st.write(f"**Scenario:** {st.session_state.persona.get('scenario', '')}")


def render_message_history():
    """Render the conversation message history."""
    for msg in st.session_state.messages:
        if msg["role"] in ["user", "assistant"]:
            with st.chat_message("user" if msg["role"] == "user" else "assistant"):
                st.markdown(msg["content"])


def render_chat_area():
    """Render persona info and message history."""
    render_persona_info()
    render_message_history()
