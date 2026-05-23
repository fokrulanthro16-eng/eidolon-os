"""
Prompt builder for local LLMs (Ollama / Mistral / Gemma / Phi-3).

Produces two strings per request:
    SYSTEM_PROMPT  — constant; injected as the system role message
    build_user_prompt()  — dynamic; built from the MemoryContext dict

Design constraints:
    - Stays under ~1500 tokens total (safe for 2k-ctx models like Phi-3 mini)
    - No hallucination bait: every factual claim in the prompt comes from
      real memory data
    - Time-anchored: model sees relative timestamps so it can reason about
      recency without knowing today's date

Token budget (approximate, 4 chars ≈ 1 token):
    system prompt  ~120 tokens
    header + meta  ~80 tokens
    per memory     ~80 tokens × 6 = 480 tokens
    footer         ~40 tokens
    total          ~720 tokens  — leaves headroom for 200-token reply
"""


# ---------------------------------------------------------------------------
# System prompt  (inject once as system role)
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are EIDOLON's memory brain — a personal AI that helps the user recall \
what they were doing at their computer. You receive OCR text extracted from \
screenshots, window titles, and app context captured automatically.

Rules:
- Answer concisely (2-4 sentences max).
- Only state what the memory evidence actually shows; do not invent details.
- Use the provided timestamps to describe when things happened.
- If no relevant memories were found, say so honestly and suggest the user \
  run the screen watcher to capture more context.
- Speak directly to the user in first person: "You were...", "Your screen showed..."
"""


# ---------------------------------------------------------------------------
# Memory entry formatter
# ---------------------------------------------------------------------------

def format_memory_for_prompt(entry: dict, index: int) -> str:
    """
    Render one compressed memory entry as a readable block for the LLM.

    Input: a dict produced by compress_memories() in memory_context.py.
    """
    lines = [f"[Memory {index}]  score={entry['score']}  {entry['relative']}"]
    lines.append(f"  title  : {entry['title']}")
    lines.append(f"  type   : {entry['type']}   source: {entry['source']}")

    if entry.get("text"):
        # Truncate at a sentence boundary when possible
        text = entry["text"]
        if len(text) > 200:
            cutoff = text.rfind(".", 0, 200)
            text = text[: cutoff + 1] if cutoff > 80 else text[:200] + "…"
        lines.append(f"  ocr    : {text}")
    elif entry.get("keywords"):
        lines.append(f"  keywords: {', '.join(entry['keywords'])}")
    else:
        lines.append("  ocr    : (no text extracted)")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Full user-turn prompt
# ---------------------------------------------------------------------------

def build_user_prompt(
    user_message: str,
    context: dict,
) -> str:
    """
    Build the complete user-turn prompt from a MemoryContext dict.

    Parameters
    ----------
    user_message : str
        Original natural-language question.
    context : dict
        Output of build_memory_context() from memory_context.py.

    Returns
    -------
    str
        Ready-to-send prompt string for Ollama /api/generate.
    """
    lines: list[str] = []

    # ---- header ----
    lines.append(f'User asked: "{user_message}"')
    lines.append("")
    lines.append(f"Searched memory for: {context['query_used']!r}")
    lines.append(f"Time window: {context['time_window']}")
    lines.append(f"Total matches: {context['total_count']}")

    if context.get("sources"):
        lines.append(f"Sources seen: {', '.join(context['sources'])}")

    if context.get("activity_summary"):
        lines.append(f"Context: {context['activity_summary']}")

    lines.append("")

    # ---- memory blocks ----
    compressed: list[dict] = context.get("compressed", [])
    if not compressed:
        lines.append("No matching memories found in the database.")
    else:
        lines.append(f"Top {len(compressed)} relevant memories (newest to oldest):")
        lines.append("")
        for i, entry in enumerate(compressed, start=1):
            lines.append(format_memory_for_prompt(entry, i))
            lines.append("")

    # ---- instruction ----
    lines.append("---")
    lines.append(
        "Based only on the memories above, answer the user's question. "
        "Be concise and specific. If the memories are insufficient, say so."
    )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Chat-style prompt  (for models that use messages[] instead of prompt+system)
# ---------------------------------------------------------------------------

def build_messages_prompt(
    user_message: str,
    context: dict,
) -> list[dict]:
    """OpenAI-compatible messages array without session history."""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": build_user_prompt(user_message, context)},
    ]


def build_chat_messages_with_history(
    user_message: str,
    context: dict,
    history: list[dict],
    max_history_turns: int = 4,
) -> list[dict]:
    """
    Build the messages array for Ollama /api/chat, injecting the last
    max_history_turns conversation turns before the current question.

    Structure:
        [system]
        [user (turn -N)]   [assistant (turn -N)]
        ...
        [user (current)]   ← memory context injected here
    """
    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]

    # Inject prior turns (already role-tagged dicts)
    # history contains alternating user/assistant entries
    prior = history[-(max_history_turns * 2):]  # last N full turns
    messages.extend(prior)

    # Current user turn with full memory context
    messages.append({
        "role":    "user",
        "content": build_user_prompt(user_message, context),
    })

    return messages
