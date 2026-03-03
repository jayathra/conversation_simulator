import os
import time
import streamlit as st
from geotab_convo_sim.core.personas import PERSONAS, get_persona, build_employee_system_prompt
from geotab_convo_sim.core.background_worker import start_pdf_processing, get_job_status


def initialize_session_state():
    """Initialize all session state variables."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "persona" not in st.session_state:
        st.session_state.persona = None
    if "coach_feedback" not in st.session_state:
        st.session_state.coach_feedback = None
    if "pdf_job_id" not in st.session_state:
        st.session_state.pdf_job_id = None
    if "voice_mode" not in st.session_state:
        st.session_state.voice_mode = False
    if "transcribed_text" not in st.session_state:
        st.session_state.transcribed_text = ""
    if "tts_voice" not in st.session_state:
        st.session_state.tts_voice = "nova"
    if "last_spoken_response" not in st.session_state:
        st.session_state.last_spoken_response = None
    if "last_sent_message" not in st.session_state:
        st.session_state.last_sent_message = None
    if "pdf_uploaded_in_session" not in st.session_state:
        st.session_state.pdf_uploaded_in_session = False
    if "last_audio_hash" not in st.session_state:
        st.session_state.last_audio_hash = None
    if "last_returned_text" not in st.session_state:
        st.session_state.last_returned_text = ""


def render_llm_provider_config():
    """Render LLM provider selection (OpenAI vs Ollama).
    """
    st.sidebar.header("LLM Configuration")
    provider = st.sidebar.radio(
        "Select LLM Provider",
        ["OpenAI", "Local"],
        key="llm_provider"
    )
    provider_key = "openai" if provider == "OpenAI" else "ollama"

    if provider_key == "openai":
        role_model = "gpt-4o-mini"
        coach_model = "gpt-4o"
    else:
        role_model = "qwen2.5:3b"
        coach_model = "qwen2.5:7b"
    
    return provider_key, role_model, coach_model


def render_voice_mode_config():
    """Render voice mode toggle and voice selection."""
    st.sidebar.markdown("---")
    st.sidebar.header("Voice Mode")
    st.sidebar.checkbox(
        "Enable Voice",
        key="voice_mode",
        help="Record voice messages (speech-to-text) and hear responses (text-to-speech)"
    )

    if st.session_state.voice_mode:
        st.sidebar.success("Voice enabled")
        st.sidebar.selectbox(
            "Response Voice",
            options=["alloy", "echo", "fable", "onyx", "nova", "shimmer"],
            key="tts_voice",
            help="Choose the voice for spoken responses (OpenAI TTS)"
        )
    else:
        st.sidebar.info("Text input only")


def render_persona_selection():
    """Render persona selection and handle persona switching.
    """
    st.sidebar.markdown("---")
    st.sidebar.header("Persona Selection")
    
    persona_map = {
        k: v.get("persona", v.get("name", k))
        for k, v in PERSONAS.items()
    }
    persona_options = list(persona_map.values())
    persona_choice = st.sidebar.selectbox("Choose Persona", persona_options)

    # Map display label back to persona key
    selected_key = None
    for k, name in persona_map.items():
        if name == persona_choice:
            selected_key = k
            break
    
    if selected_key is None and persona_map:
        selected_key = next(iter(persona_map))

    # Handle persona change
    if "persona_key" not in st.session_state or st.session_state.get("persona_key") != selected_key:
        persona = get_persona(selected_key)
        st.session_state.persona = persona
        st.session_state.persona_key = selected_key
        
        # Reset conversation when changing personas
        system_prompt = build_employee_system_prompt(persona)
        st.session_state.messages = [
            {"role": "system", "content": system_prompt},
        ]
        st.session_state.coach_feedback = None
        
        # Reset all state when changing personas
        st.session_state.transcribed_text = ""
        st.session_state.last_sent_message = None
        st.session_state.last_spoken_response = None
        st.session_state.pdf_uploaded_in_session = False
    
    return selected_key


def render_pdf_upload_section():
    """Render PDF upload and processing section."""
    st.sidebar.markdown("---")
    st.sidebar.header("Company Knowledge Base")
    
    # Show info about how the system works
    st.sidebar.info("📄 Upload a company document to provide context for coaching feedback. Each new upload replaces the previous document.")
    
    uploaded_file = st.sidebar.file_uploader(
        "Upload company PDF (coaching guidelines, policies, etc.)",
        type=["pdf"]
    )

    if uploaded_file is not None:
        # Save uploaded file to disk
        upload_dir = "uploads"
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, uploaded_file.name)

        # Only save if not already processing
        if st.session_state.pdf_job_id is None:
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            st.sidebar.success(f"Saved: {uploaded_file.name}")

            if st.sidebar.button("Process PDF (Background)"):
                job_id = f"{uploaded_file.name}_{int(time.time())}"
                start_pdf_processing(
                    job_id,
                    file_path,
                    chunk_size=500,
                    overlap=50
                )
                st.session_state.pdf_job_id = job_id
                st.session_state.pdf_uploaded_in_session = True
                st.rerun()
        else:
            # Show job status
            job = get_job_status(st.session_state.pdf_job_id)
            if job:
                status = job.get("status", "unknown")
                progress = job.get("progress", "")

                if status == "queued":
                    st.sidebar.info(f"{progress}")
                elif status == "processing":
                    st.sidebar.info(f"{progress}")
                elif status == "completed":
                    st.sidebar.success(f"{progress}")
                    if st.sidebar.button("Clear Status"):
                        st.session_state.pdf_job_id = None
                        st.rerun()
                elif status == "failed":
                    error = job.get("error", "Unknown error")
                    st.sidebar.error(f"Failed: {error}")
                    if st.sidebar.button("Clear Status"):
                        st.session_state.pdf_job_id = None
                        st.rerun()

                # Auto-refresh while processing
                if status in ["queued", "processing"]:
                    time.sleep(0.5)
                    st.rerun()
    
    # Add button to manually clear knowledge base
    if st.sidebar.button("Clear Knowledge Base", help="Remove all uploaded documents from the vector database"):
        try:
            from geotab_convo_sim.core.pinecone_utils import delete_namespace
            if delete_namespace("company-docs"):
                st.sidebar.success("Knowledge base cleared successfully")
            else:
                st.sidebar.warning("Knowledge base may not be fully cleared")
        except Exception as e:
            st.sidebar.error(f"Failed to clear knowledge base: {e}")
        st.rerun()

    st.sidebar.markdown("---")


def render_reset_button():
    """Render reset conversation button."""
    if st.sidebar.button("Reset Conversation", use_container_width=True):
        # Clear conversation but keep persona
        if st.session_state.persona:
            from geotab_convo_sim.core.personas import build_employee_system_prompt
            system_prompt = build_employee_system_prompt(st.session_state.persona)
            st.session_state.messages = [
                {"role": "system", "content": system_prompt},
            ]
        else:
            st.session_state.messages = []
        
        # Clear feedback and voice state
        st.session_state.coach_feedback = None
        st.session_state.transcribed_text = ""
        st.session_state.last_sent_message = None
        st.session_state.last_spoken_response = None
        st.session_state.last_audio_hash = None
        st.session_state.last_returned_text = ""
        
        st.rerun()


def render_sidebar():
    """Render the entire sidebar and return configuration.
    
    Returns:
        Tuple: (provider_key, role_model, coach_model)
    """
    provider_key, role_model, coach_model = render_llm_provider_config()
    render_voice_mode_config()
    render_persona_selection()
    render_pdf_upload_section()
    render_reset_button()
    
    return provider_key, role_model, coach_model
