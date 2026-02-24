import re
from typing import Tuple, List, Optional

# try to use Guardrails or fallback to local heuristic.
try:
    from guardrails import Guard
    _HAS_GUARDRAILS = True
except Exception:
    Guard = None
    _HAS_GUARDRAILS = False

# Cached Guard object (lazy loaded)
_GUARD: Optional[object] = None


def _tokenize(text: str) -> List[str]:
    text = (text or "").lower()
    tokens = re.findall(r"[a-z0-9]+", text)
    stopwords = {
        "the",
        "is",
        "a",
        "an",
        "and",
        "or",
        "to",
        "of",
        "in",
        "on",
        "for",
        "with",
        "that",
        "this",
    }
    return [t for t in tokens if t and t not in stopwords]


def _is_brief_courtesy(text: str) -> bool:
    if not text:
        return False
    normalized = re.sub(r"\s+", " ", text.strip().lower())
    if len(normalized) > 120:
        return False
    courtesy_phrases = [
        "hi",
        "hello",
        "hey",
        "good morning",
        "good afternoon",
        "good evening",
        "do you have a moment",
        "can we chat",
        "can we talk",
        "can we speak",
        "a moment to speak",
        "quick chat",
        "thanks",
        "thank you",
        "thank you for your time",
        "thank you for taking the time",
        "appreciate it",
        "sounds good",
        "agreed",
        "okay",
        "ok",
    ]
    return any(phrase in normalized for phrase in courtesy_phrases)


def _heuristic_is_on_topic(user_text: str, persona: dict, transcript: list, threshold: float = 0.2) -> Tuple[bool, str, float]:
    if not user_text or not user_text.strip():
        return False, "Your message was empty. Please write something relevant to the conversation."

    if _is_brief_courtesy(user_text):
        return True, "", 1.0

    topic_source = []
    if isinstance(persona, dict):
        topic_source.append(persona.get("name", ""))
        topic_source.append(persona.get("scenario", ""))
        topic_source.append(persona.get("role", ""))
        topic_source.append(persona.get("persona", ""))
        traits = persona.get("personality_traits") or []
        if isinstance(traits, list):
            topic_source.extend(traits)
        else:
            topic_source.append(str(traits))

    try:
        for m in transcript:
            topic_source.append(m.get("content", ""))
    except Exception:
        pass

    topic_text = " ".join([str(s) for s in topic_source if s])
    input_tokens = set(_tokenize(user_text))
    topic_tokens = set(_tokenize(topic_text))

    if not input_tokens:
        return False, "Please write a short message related to the conversation.", 0.0

    overlap = input_tokens & topic_tokens
    ratio = len(overlap) / max(1, len(input_tokens))

    if ratio >= threshold:
        return True, "", ratio

    msg = "Please keep the input focused on the current conversation/topic."
    return False, msg, ratio


def is_on_topic(user_text: str, persona: dict, transcript: list) -> Tuple[bool, str]:
    """Return (is_on_topic, reason).

    - Run the fast local heuristic first.
    - If heuristic score is clearly low or high, return immediately.
    - If ambiguous, consult Guardrails (if available) to disambiguate.
    """
    # Run local heuristic first to avoid unnecessary Guardrails calls
    try:
        heuristic_on, heuristic_reason, score = _heuristic_is_on_topic(user_text, persona, transcript)
    except Exception:
        return False, "Please keep the input focused on the current conversation/topic."

    LOW = 0.15
    HIGH = 0.4

    # Clearly off-topic: do not call Guardrails
    if score <= LOW and not heuristic_on:
        return False, heuristic_reason

    # Clearly on-topic: accept immediately
    if score >= HIGH and heuristic_on:
        return True, ""

    # Ambiguous: consult Guardrails if available
    if _HAS_GUARDRAILS:
        global _GUARD
        try:
            if _GUARD is None:
                _GUARD = Guard.from_rail(__file__.replace("guards.py", "guardrails_on_topic.yml"))
            persona_text = persona.get("system_prompt") if isinstance(persona, dict) else str(persona)
            transcript_text = "\n".join(m.get("content", "") for m in (transcript or []))
            out = _GUARD.run(user_input=user_text, persona=persona_text, transcript=transcript_text)
            if isinstance(out, dict):
                is_on = bool(out.get("is_on_topic"))
                reason = out.get("reason") or ""
                return is_on, reason
        except Exception:
            # On any Guardrails failure, fall back to heuristic
            pass

    # Fallback to heuristic result
    return heuristic_on, heuristic_reason
