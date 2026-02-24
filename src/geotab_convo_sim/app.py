import streamlit as st
from geotab_convo_sim.core.llm_client import chat_completion
from geotab_convo_sim.core.guards import is_on_topic
from geotab_convo_sim.services.tts import speak_text
from geotab_convo_sim.ui.sidebar import initialize_session_state, render_sidebar
from geotab_convo_sim.ui.chat_display import render_chat_area
from geotab_convo_sim.ui.voice_input import render_voice_input_section
from geotab_convo_sim.ui.text_input import render_text_input_section
from geotab_convo_sim.ui.coaching_feedback import (
    render_coaching_feedback_button,
    render_coaching_feedback_display,
)


def main() -> None:
    """Run the Streamlit application."""
    st.set_page_config(page_title="Difficult Conversation Simulator")
    st.title("Difficult Conversation Simulator")

    initialize_session_state()

    provider_key, role_model, coach_model = render_sidebar()

    render_chat_area()

    user_input = ""

    if st.session_state.voice_mode:
        user_input = render_voice_input_section()

    if not user_input and not st.session_state.voice_mode:
        user_input = render_text_input_section()

    if user_input:
        ok, reason = is_on_topic(user_input, st.session_state.persona, st.session_state.messages)
        if not ok:
            st.warning(reason or "Please stay on topic. Your message was not sent to the LLM.")
        else:
            st.session_state.messages.append({"role": "user", "content": user_input})
            with st.chat_message("user"):
                st.markdown(user_input)

            reply = chat_completion(
                st.session_state.messages,
                model=role_model,
                temperature=0.8,
                provider=provider_key,
            )
            st.session_state.messages.append({"role": "assistant", "content": reply})

            with st.chat_message("assistant"):
                st.markdown(reply)

            if st.session_state.voice_mode and reply != st.session_state.last_spoken_response:
                st.info("Playing audio response...")
                speak_text(reply, voice=st.session_state.tts_voice)
                st.session_state.last_spoken_response = reply

            st.session_state.last_sent_message = user_input

    render_coaching_feedback_button(provider_key, coach_model)
    render_coaching_feedback_display()


if __name__ == "__main__":
    main()
