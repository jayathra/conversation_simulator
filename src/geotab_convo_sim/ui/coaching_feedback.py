import streamlit as st
from geotab_convo_sim.core.coach import coach_feedback


def _detect_training_mode(persona_key: str) -> str:
    """Detect whether the persona is for manager or sales training.
    
    Args:
        persona_key: The key of the persona (e.g., "defensive_engineer" or "fleet_ops_manager")
    
    Returns:
        Either "manager" or "sales"
    """
    sales_personas = {"fleet_ops_manager", "it_director", "c_suite_executive"}
    return "sales" if persona_key in sales_personas else "manager"


def render_coaching_feedback_button(provider_key: str, coach_model: str) -> None:
    """Render the coaching feedback button and handle feedback generation.
    """
    if st.button("Get Coaching Feedback"):
        with st.spinner("Analyzing conversation..."):
            # Determine training mode based on current persona
            persona_key = st.session_state.get("persona_key", "defensive_engineer")
            training_mode = _detect_training_mode(persona_key)
            
            feedback = coach_feedback(
                st.session_state.messages,
                provider=provider_key,
                model=coach_model,
                use_pinecone=st.session_state.pdf_uploaded_in_session,
                training_mode=training_mode
            )
            st.session_state.coach_feedback = feedback
            st.rerun()


def render_coaching_feedback_display() -> None:
    """Render the coaching feedback if available."""
    if st.session_state.coach_feedback:
        st.subheader("Coaching Feedback")
        st.markdown(st.session_state.coach_feedback)
