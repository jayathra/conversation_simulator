import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def chat_completion(messages, model="gpt-4o", temperature=0.7, provider="openai"):
    """Call an LLM: OpenAI or local Ollama instance.

    Args:
        messages: Conversation history (list of dicts with role/content)
        model: Model name (e.g., "gpt-4o" for OpenAI, "mistral" for Ollama)
        temperature: Creativity level (0-1)
        provider: "openai" or "ollama"

    Returns:
        String response from the model
    """
    if provider == "ollama":
        return _ollama_completion(messages, model, temperature)
    else:
        return _openai_completion(messages, model, temperature)


def _openai_completion(messages, model, temperature):
    """Call OpenAI API."""
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
    )
    # Choices may be a list; handle attribute and dict-like shapes from different SDK versions
    choice = None
    try:
        choice = response.choices[0]
    except Exception:
        # fallback: if choices isn't indexable, try attribute access
        try:
            choice = response.choices
        except Exception:
            return str(response)

    # Try attribute-style (SDK object)
    if hasattr(choice, "message"):
        msg = choice.message
        return getattr(msg, "content", getattr(msg, "text", str(msg)))

    # Try dict-style
    try:
        if isinstance(choice, dict):
            msg = choice.get("message") or {}
            return msg.get("content") or choice.get("text") or str(choice)
    except Exception:
        pass

    # Fallback: string representation
    return str(choice)


def _ollama_completion(messages, model, temperature):
    """Call a local Ollama instance running on localhost:11434."""
    import requests

    url = "http://localhost:11434/api/chat"

    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature},
    }

    try:
        response = requests.post(url, json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()
        return data.get("message", {}).get("content", str(data))
    except requests.exceptions.ConnectionError:
        return "Error: Cannot connect to Ollama at localhost:11434. Is Ollama running?"
    except requests.exceptions.RequestException as e:
        return f"Error: Ollama request failed: {str(e)}"
