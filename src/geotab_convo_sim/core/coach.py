from .llm_client import chat_completion
from .pinecone_utils import query_relevant_chunks
import json
import re

def build_coach_system_prompt() -> str:
    """Constructs a detailed analytical system prompt for the manager coaching agent.
    """
    return (
        "You are an expert executive coach specializing in difficult conversations and feedback delivery.\n\n"
        "Your role is to analyze a conversation between a manager and employee, then provide constructive feedback.\n\n"
        "EVALUATION FRAMEWORK:\n\n"
        "1. EMPATHY (0-10)\n"
        "   - Did the manager acknowledge the employee's feelings?\n"
        "   - Were they curious about the employee's perspective?\n"
        "   - Did they validate concerns before problem-solving?\n\n"
        "2. CLARITY (0-10)\n"
        "   - Was the core issue communicated clearly?\n"
        "   - Did the manager avoid vague language?\n"
        "   - Were expectations and next steps specific?\n\n"
        "3. EFFECTIVENESS (0-10)\n"
        "   - Did the conversation progress productively?\n"
        "   - Was the employee able to open up?\n"
        "   - Were solutions collaborative vs. dictated?\n\n"
        "INSTRUCTIONS:\n"
        "- Provide numeric scores for Empathy, Clarity, and Effectiveness (0-10) with brief rationale.\n"
        "- List 2-3 concrete strengths with examples from the transcript.\n"
        "- List 2-3 specific improvements and example phrasings the manager could use.\n"
        "- Provide 2-3 key insights or turning points from the conversation.\n\n"
        "Be concise, actionable, and cite transcript excerpts when possible."
    )


def build_sales_coach_system_prompt() -> str:
    """Constructs a detailed analytical system prompt for the sales coaching agent.
    """
    return (
        "You are an expert sales coach specializing in evaluating Geotab sales representative performance.\n\n"
        "Your role is to analyze a sales conversation between a Geotab representative (user role) "
        "and a prospective customer (assistant role), then provide constructive feedback.\n\n"
        "EVALUATION FRAMEWORK:\n\n"
        "1. DISCOVERY QUALITY (0-10)\n"
        "   - Did the rep ask targeted qualifying questions to understand customer needs?\n"
        "   - Were questions specific to the customer's business pain points and objectives?\n"
        "   - Did the rep listen actively and probe deeper based on customer responses?\n\n"
        "2. VALUE ARTICULATION (0-10)\n"
        "   - Did the rep clearly explain how Geotab's solution addresses customer needs?\n"
        "   - Were tangible business benefits (ROI, efficiency gains, safety) connected to customer goals?\n"
        "   - Did the rep avoid generic features talk and focus on customer-specific outcomes?\n\n"
        "3. OBJECTION HANDLING (0-10)\n"
        "   - Did the rep address customer concerns without defensiveness?\n"
        "   - Were objections treated as opportunities to clarify value vs. obstacles?\n"
        "   - Did the rep provide relevant examples or evidence to overcome skepticism?\n\n"
        "INSTRUCTIONS:\n"
        "- Provide numeric scores for Discovery Quality, Value Articulation, and Objection Handling (0-10) with brief rationale.\n"
        "- List 2-3 concrete strengths with specific examples from the sales conversation.\n"
        "- List 2-3 specific improvements and techniques the rep could use next time.\n"
        "- Provide 2-3 key insights about customer buying signals, objections, or decision criteria.\n\n"
        "Be concise, actionable, and cite transcript excerpts when possible."
    )

def coach_feedback(conversation_messages, provider: str = "openai", model: str | None = None, use_pinecone: bool = True, training_mode: str = "manager"):
    """Generate coaching feedback for either manager training or sales training.
    """
    
    # Set up mode-specific prompts and score keys
    is_sales_mode = training_mode.lower() == "sales"
    
    if is_sales_mode:
        system_prompt_func = build_sales_coach_system_prompt
        score_keys = {
            "score_1": "discovery_quality_score",
            "score_2": "value_articulation_score",
            "score_3": "objection_handling_score",
            "score_1_label": "Discovery Quality",
            "score_2_label": "Value Articulation",
            "score_3_label": "Objection Handling"
        }
        user_prompt_intro = (
            "Here is a transcript of a sales conversation between a Geotab sales representative (user role) "
            "and a prospective customer (assistant role).\n\n"
            "TASKS:\n"
            "1. Give a Discovery Quality score from 1 to 10 and explain briefly.\n"
            "2. Give a Value Articulation score from 1 to 10 and explain briefly.\n"
            "3. Suggest 2–3 concrete improvements the sales rep could make next time.\n\n"
            "Transcript (messages are in chronological order):\n"
        )
    else:
        system_prompt_func = build_coach_system_prompt
        score_keys = {
            "score_1": "empathy_score",
            "score_2": "clarity_score",
            "score_3": "effectiveness_score",
            "score_1_label": "Empathy",
            "score_2_label": "Clarity",
            "score_3_label": "Effectiveness"
        }
        user_prompt_intro = (
            "Here is a transcript of a conversation between a manager (user role) "
            "and an employee (assistant role).\n\n"
            "TASKS:\n"
            "1. Give an Empathy score from 1 to 5 and explain briefly.\n"
            "2. Give a Clarity score from 1 to 5 and explain briefly.\n"
            "3. Suggest 2–3 concrete improvements the manager could make next time.\n\n"
            "Transcript (messages are in chronological order):\n"
        )

    transcript_text = ""
    for msg in conversation_messages:
        if msg["role"] == "user":
            speaker = "Sales Rep" if is_sales_mode else "Manager"
        elif msg["role"] == "assistant":
            speaker = "Customer" if is_sales_mode else "Employee"
        else:
            speaker = "System"
        transcript_text += f"{speaker}: {msg.get('content','')}\n"
    
    def _summarize_insight_fallback(text: str, max_len: int = 200) -> str:
        cleaned = re.sub(r"\s+", " ", (text or "").strip())
        if not cleaned:
            return ""
        if len(cleaned) <= max_len:
            return cleaned
        cut = cleaned[:max_len]
        last_period = cut.rfind(".")
        if last_period > 80:
            return cut[: last_period + 1].strip()
        return cut.rstrip() + "..."

    # Choose model if not provided
    if model is None:
        if provider == "openai":
            model = "gpt-4o"
        else:
            model = "qwen2.5-7b-instruct"

    def _summarize_insight_llm(text: str) -> str:
        cleaned = re.sub(r"\s+", " ", (text or "").strip())
        if not cleaned:
            return ""
        messages = [
            {
                "role": "system",
                "content": "Summarize the input in 1-2 concise sentences. Preserve key details.",
            },
            {"role": "user", "content": cleaned},
        ]
        try:
            return chat_completion(messages, model=model, temperature=0.2, provider=provider).strip()
        except Exception:
            return _summarize_insight_fallback(cleaned)

    # Query Pinecone for relevant company knowledge (only if PDF was uploaded in current session)
    company_context = ""
    relevant_insights = []
    seen_insights = set()  # Track unique insights to avoid duplicates
    
    if use_pinecone:
        try:
            # Use transcript as query to find relevant company policies/guidelines
            relevant_chunks = query_relevant_chunks(transcript_text, top_k=3)
            if relevant_chunks:
                company_context = "\n\nRELEVANT COMPANY GUIDELINES:\n"
                for i, chunk_data in enumerate(relevant_chunks, 1):
                    text = chunk_data.get("text", "")
                    page_num = chunk_data.get("page_num")
                    source_file = chunk_data.get("source_file", "document")
                    
                    page_ref = f" (Page {page_num})" if page_num else ""
                    company_context += f"\n[Context {i} from {source_file}{page_ref}]:\n{text}\n"
                    
                    # Only add insight if the text is unique (not already added)
                    if text:
                        summary = _summarize_insight_llm(text)
                        insight_key = f"{source_file}{page_ref}:{summary}"
                        
                        # Check if this exact insight hasn't been added before
                        if insight_key not in seen_insights:
                            relevant_insights.append(f"{source_file}{page_ref}: {summary}")
                            seen_insights.add(insight_key)
                
                company_context += "\nUse the above company guidelines when evaluating the manager's approach and suggesting improvements.\n"
        except Exception as e:
            # If Pinecone query fails, continue without company context
            print(f"Failed to query Pinecone: {e}")

    # Ask the model to return a structured JSON object with specific keys.
    prompt = (
        user_prompt_intro
        + transcript_text
        + company_context
        + "\n\nINSTRUCTIONS:\n"
        + "- Output ONLY a single valid JSON object and nothing else. Do not include any explanatory text.\n"
        + "- The JSON must include the following keys (use these exact key names):\n"
        + f"  {score_keys['score_1']} (0-10), {score_keys['score_2']} (0-10), {score_keys['score_3']} (0-10),\n"
        + "  strengths (list of strings), improvements (list of strings), key_insights (list of strings).\n"
        + "- If numeric scores are not possible, provide the closest numeric estimate.\n\n"
        + "EXAMPLE_OUTPUT:\n"
        + "{\n"
        + f"  \"{score_keys['score_1']}\": 7,\n"
        + f"  \"{score_keys['score_2']}\": 6,\n"
        + f"  \"{score_keys['score_3']}\": 5,\n"
        + "  \"strengths\": [\n"
    )
    
    if is_sales_mode:
        prompt += (
            "    \"Asked probing questions about customer's current pain points\",\n"
            "    \"Connected Geotab's real-time visibility feature to fleet cost reduction goal\"\n"
        )
    else:
        prompt += (
            "    \"Acknowledged employee's feelings: 'I can see why you're frustrated'\",\n"
            "    \"Asked open questions to invite perspective\"\n"
        )
    
    prompt += (
        "  ],\n"
        "  \"improvements\": [\n"
    )
    
    if is_sales_mode:
        prompt += (
            "    \"Ask about current technology stack and integration requirements before jumping to features\",\n"
            "    \"Provide a ROI case study from a similar fleet size to address cost concerns\"\n"
        )
    else:
        prompt += (
            "    \"Be specific about the missed deliverable and date (e.g., 'The report due on March 1 was not submitted')\",\n"
            "    \"Offer concrete next steps and checkpoints (e.g., 'Let's set a new deadline and weekly check-ins')\"\n"
        )
    
    prompt += (
        "  ],\n"
        "  \"key_insights\": [\n"
    )
    
    if is_sales_mode:
        prompt += (
            "    \"Customer is concerned about implementation timeline; opportunity to discuss our rapid onboarding process\",\n"
            "    \"Customer needs data integration with SAP; this is a key integration strength to highlight\"\n"
        )
    else:
        prompt += (
            "    \"Manager used some empathy statements which reduced tension\",\n"
            "    \"Conversation lacked clear next steps and specific examples of the issue.\"\n"
        )
    
    prompt += (
        "  ]\n"
        "}\n\n"
        "Now produce the JSON object that corresponds to the transcript above."
    )

    messages = [
        {"role": "system", "content": system_prompt_func()},
        {"role": "user", "content": prompt},
    ]

    raw = chat_completion(messages, model=model, temperature=0.2, provider=provider)

    # Try to parse JSON directly
    parsed = None
    try:
        parsed = json.loads(raw)
    except Exception:
        # Try to extract a JSON object from the text
        m = re.search(r"\{[\s\S]*\}", raw)
        if m:
            try:
                parsed = json.loads(m.group(0))
            except Exception:
                parsed = None

    def _format_parsed(p: dict) -> str:
        parts = []

        # Scores - handle both manager and sales modes
        score_1 = p.get(score_keys['score_1'])
        score_2 = p.get(score_keys['score_2'])
        score_3 = p.get(score_keys['score_3'])

        if score_1 is not None:
            parts.append(f"**{score_keys['score_1_label']}:** {score_1}/10")
        if score_2 is not None:
            parts.append(f"**{score_keys['score_2_label']}:** {score_2}/10")
        if score_3 is not None:
            parts.append(f"**{score_keys['score_3_label']}:** {score_3}/10")

        # Strengths
        strengths = p.get("strengths")
        if strengths:
            parts.append("\n**Strengths:**")
            if isinstance(strengths, list):
                for s in strengths:
                    if isinstance(s, list):
                        for sub in s:
                            parts.append(f"- {sub}")
                    else:
                        parts.append(f"- {s}")
            else:
                parts.append(f"- {strengths}")

        # Improvements
        improvements = p.get("improvements")
        if improvements:
            parts.append("\n**Areas for Improvement:**")
            if isinstance(improvements, list):
                for im in improvements:
                    if isinstance(im, list):
                        for sub in im:
                            parts.append(f"- {sub}")
                    else:
                        parts.append(f"- {im}")
            else:
                parts.append(f"- {improvements}")

        # Key insights
        insights = p.get("key_insights")
        if insights:
            parts.append("\n**Key Insights:**")
            if isinstance(insights, list):
                for ins in insights:
                    if isinstance(ins, list):
                        for sub in ins:
                            parts.append(f"- {sub}")
                    else:
                        parts.append(f"- {ins}")
            else:
                parts.append(str(insights))

        # Relevant Insights (only add once at the end)
        if use_pinecone:
            parts.append("\n**Relevant Insights from Uploaded Documents:**")
            if relevant_insights:
                for item in relevant_insights:
                    parts.append(f"- {item}")
            else:
                parts.append("- No relevant insights were found in the uploaded documents.")
        else:
            parts.append("\n**Note:** No documents were uploaded for this conversation.")

        # If nothing parsed into structured sections, include raw JSON
        if not parts:
            return "**Coach (structured):**\n\n" + json.dumps(p, indent=2)

        return "\n\n".join(parts)

    if isinstance(parsed, dict):
        return _format_parsed(parsed)

    # Fallback: return the raw string in a readable block
    output = "**Coach (raw):**\n\n" + raw
    if use_pinecone:
        output += "\n\n**Relevant Insights from Uploaded Documents:**"
        if relevant_insights:
            for item in relevant_insights:
                output += f"\n- {item}"
        else:
            output += "\n- No relevant insights were found in the uploaded documents."
    else:
        output += "\n\n**Note:** No documents were uploaded for this conversation."
    return output
