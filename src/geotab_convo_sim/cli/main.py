from geotab_convo_sim.core.llm_client import chat_completion
from geotab_convo_sim.core.personas import get_persona, PERSONAS
from geotab_convo_sim.core.coach import coach_feedback
from geotab_convo_sim.core.guards import is_on_topic

def run_cli():
    print("=== Difficult Conversation Simulator (CLI) ===\n")

    # LLM Provider selection
    print("Available LLM providers:")
    print("1. OpenAI (GPT-4o-mini)")
    print("2. Ollama Local (Qwen2)")
    provider_choice = input("Choose provider (1 or 2, default: 1): ").strip() or "1"

    if provider_choice == "2":
        provider = "ollama"
        role_model = "qwen2.5-3b-instruct"
        coach_model = "qwen2.5-7b-instruct"
    else:
        provider = "openai"
        role_model = "gpt-4o-mini"
        coach_model = "gpt-4o"

    print(f"\nUsing {provider.upper()} ({role_model})\n")

    available = list(PERSONAS.keys())
    if not available:
        print("No personas are configured. Exiting.")
        return

    print("Available personas:", ", ".join(available))
    default = available[0]
    persona_name = input(f"Choose persona ({default}): ").strip() or default

    if persona_name not in PERSONAS:
        print(f"Unknown persona '{persona_name}', using default '{default}'.")
        persona_name = default

    try:
        persona = get_persona(persona_name)
    except ValueError:
        print(f"Failed to load persona '{persona_name}', using default '{default}'.")
        persona = get_persona(default)

    print(f"\nPersona: {persona['label']}")
    print(f"Scenario: {persona['scenario']}")
    print("Type your feedback as the MANAGER. Type 'END' when you want coaching.\n")

    messages = [
        {"role": "system", "content": persona["system_prompt"]},
        {"role": "system", "content": persona["scenario"]},
    ]

    while True:
        user_input = input("You (Manager): ")
        if user_input.strip().upper() == "END":
            break

        ok, reason = is_on_topic(user_input, persona, messages)
        if not ok:
            print(f"[Guard] {reason}\n")
            continue

        messages.append({"role": "user", "content": user_input})

        reply = chat_completion(messages, model=role_model, provider=provider)
        messages.append({"role": "assistant", "content": reply})

        print(f"\nEmployee ({persona['label']}): {reply}\n")

    print("\n=== Coaching Feedback ===\n")
    feedback = coach_feedback(messages, provider=provider, model=coach_model, use_pinecone=False)
    print(feedback)

if __name__ == "__main__":
    run_cli()
