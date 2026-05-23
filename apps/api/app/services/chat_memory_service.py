"""
Rule-based memory recall — turns a natural language question into a
contextual answer synthesised from memory items.

No LLM required. Pipeline:
    extract_search_terms(message)
    → extract_temporal_filter(message)
    → search_memories(terms)
    → filter_by_time(results, start, end)
    → synthesize_answer(matches)
    → ChatRecallResult

LLM integration point: replace synthesize_answer() with a call to a
local model (e.g. Ollama + Mistral) that receives the same context dict.
"""

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from app.services.llm import get_brain
from app.services.llm.memory_context import build_memory_context
from app.services.memory_store import memory_store
from app.services.search_service import search_memories

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Word lists
# ---------------------------------------------------------------------------

_QUESTION_WORDS = frozenset(
    "what when where who which how why did does do was were is are have had "
    "can could should would show tell find give me".split()
)

_STOP_WORDS = frozenset(
    "i my me we our the a an that this it to of in on at for with about "
    "and or but not from by any all some its their your".split()
)

_TEMPORAL_WORDS = frozenset(
    "yesterday today tonight morning afternoon evening recently just now "
    "last past ago week month hour hours day days minute minutes year".split()
)

# Common words that appear on nearly every UI screenshot — not useful as signals
_UI_NOISE = frozenset(
    "file edit view help window terminal code format tools settings explorer "
    "source control extensions ocr unavailable image stored successfully "
    "engine configured yet run start stop build debug test open close new "
    "save copy paste undo redo find replace select all".split()
)

# ---------------------------------------------------------------------------
# Step 1 — query extraction
# ---------------------------------------------------------------------------

def extract_search_terms(message: str) -> str:
    """
    Strip question/stop/temporal words from the message to get a clean query.
    Falls back to the full message (lowercased) if nothing survives the filter.
    """
    words = re.findall(r"\b\w+\b", message.lower())
    content = [
        w for w in words
        if w not in _QUESTION_WORDS
        and w not in _STOP_WORDS
        and w not in _TEMPORAL_WORDS
        and len(w) > 2
    ]
    return " ".join(content) if content else message.strip().lower()


# ---------------------------------------------------------------------------
# Step 2 — temporal intent detection
# ---------------------------------------------------------------------------

def extract_temporal_filter(message: str) -> tuple[datetime | None, datetime | None]:
    """
    Detect temporal phrases and return (start, end) UTC datetimes.
    Returns (None, None) when no temporal intent is found.
    """
    msg = message.lower()
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if "yesterday" in msg:
        return today_start - timedelta(days=1), today_start

    if "this morning" in msg:
        return today_start, today_start.replace(hour=12)

    if "this afternoon" in msg:
        return today_start.replace(hour=12), today_start.replace(hour=18)

    if "tonight" in msg or "this evening" in msg:
        return today_start.replace(hour=18), None

    if "today" in msg:
        return today_start, None

    if "last hour" in msg or "past hour" in msg:
        return now - timedelta(hours=1), None

    if re.search(r"last\s+(\d+)\s+hours?", msg):
        m = re.search(r"last\s+(\d+)\s+hours?", msg)
        n = int(m.group(1))  # type: ignore[union-attr]
        return now - timedelta(hours=n), None

    if "recently" in msg or "just now" in msg:
        return now - timedelta(hours=3), None

    if "last week" in msg or "past week" in msg:
        return now - timedelta(days=7), None

    if "last month" in msg or "past month" in msg:
        return now - timedelta(days=30), None

    return None, None


def _apply_temporal_filter(
    matches: list[dict],
    start: datetime | None,
    end: datetime | None,
) -> list[dict]:
    if not start and not end:
        return matches

    filtered = []
    for m in matches:
        ts_str = m["item"].get("created_at", "")
        try:
            t = datetime.fromisoformat(ts_str)
            if t.tzinfo is None:
                t = t.replace(tzinfo=timezone.utc)
            if start and t < start:
                continue
            if end and t >= end:
                continue
            filtered.append(m)
        except (ValueError, TypeError):
            pass
    return filtered


# ---------------------------------------------------------------------------
# Step 3 — answer synthesis helpers
# ---------------------------------------------------------------------------

def _relative_time(iso: str) -> str:
    """Human-readable relative timestamp."""
    try:
        t = datetime.fromisoformat(iso)
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        diff = datetime.now(timezone.utc) - t
        secs = diff.total_seconds()

        if secs < 60:
            return "just now"
        if secs < 3600:
            m = int(secs / 60)
            return f"{m} minute{'s' if m != 1 else ''} ago"
        if secs < 86400:
            h = int(secs / 3600)
            return f"{h} hour{'s' if h != 1 else ''} ago"
        if diff.days == 1:
            return f"yesterday at {t.astimezone().strftime('%H:%M')}"
        if diff.days < 7:
            return f"{diff.days} days ago at {t.astimezone().strftime('%H:%M')}"
        return t.astimezone().strftime("%b %d at %H:%M")
    except Exception:
        return iso[:16]


def _extract_highlights(items: list[dict], query_used: str) -> str:
    """
    Pull distinctive content words from OCR text.
    Skips fallback messages, UI noise, and the query words themselves
    (already obvious from context).
    """
    query_words = set(re.findall(r"\w+", query_used.lower()))
    seen: set[str] = set()
    highlights: list[str] = []

    for item in items:
        text = item.get("text", "")
        if "[OCR" in text:          # skip fallback placeholder text
            continue
        # words: alphabetic, length 4+, mixed-case preserved
        for w in re.findall(r"\b[A-Za-z][a-zA-Z]{3,}\b", text):
            wl = w.lower()
            if wl in _UI_NOISE or wl in query_words or wl in seen:
                continue
            seen.add(wl)
            highlights.append(w)
            if len(highlights) >= 8:
                break
        if len(highlights) >= 8:
            break

    return ", ".join(highlights[:6]) if highlights else ""


def synthesize_answer(
    query_used: str,
    matches: list[dict],
    time_filtered: bool,
) -> str:
    """Build a natural-language answer from ranked memory matches."""
    if not matches:
        no_results = f'No memories found matching "{query_used}"'
        if time_filtered:
            no_results += " in that time window. Try without a time filter"
        else:
            no_results += ". The screen watcher may not have captured that activity yet"
        return no_results + "."

    top = matches[:5]
    items = [m["item"] for m in top]
    total = len(matches)

    # --- time range ---
    timestamps: list[datetime] = []
    for item in items:
        ts = item.get("created_at", "")
        try:
            t = datetime.fromisoformat(ts)
            timestamps.append(t.replace(tzinfo=timezone.utc) if t.tzinfo is None else t)
        except Exception:
            pass

    time_clause = ""
    if timestamps:
        newest = max(timestamps)
        oldest = min(timestamps)
        time_clause = _relative_time(newest.isoformat())
        if total > 1 and (newest - oldest).total_seconds() > 7200:
            time_clause = f"between {_relative_time(oldest.isoformat())} and {_relative_time(newest.isoformat())}"

    # --- sources ---
    sources = sorted({item.get("source", "") for item in items if item.get("source")})
    source_clause = ""
    if sources:
        source_clause = (
            f"via {sources[0]}" if len(sources) == 1
            else f"via {', '.join(sources[:-1])} and {sources[-1]}"
        )

    # --- OCR highlights ---
    highlights = _extract_highlights(items, query_used)

    # --- compose ---
    count_noun = "memory" if total == 1 else "memories"
    sentence = f"Found {total} {count_noun} matching \"{query_used}\""

    if time_clause:
        sentence += f", {time_clause}"
    if source_clause:
        sentence += f", {source_clause}"
    sentence += "."

    if highlights:
        sentence += f" Content captured: {highlights}."

    return sentence


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def chat_recall(
    message: str,
    top_n: int = 8,
) -> dict[str, Any]:
    """
    Main chat recall function.

    Returns:
        answer      str   — synthesised natural-language response
        matches     list  — top scored memory items (MemorySearchResult shape)
        count       int   — total matches before top_n slice
        query_used  str   — the extracted search terms (transparent)
        brain_mode  str   — "rule_based" | "local_llm"
    """
    query = extract_search_terms(message)
    time_start, time_end = extract_temporal_filter(message)
    time_filtered = time_start is not None or time_end is not None

    all_items = memory_store.list()
    raw_matches = search_memories(query=query, items=all_items)

    if time_filtered:
        raw_matches = _apply_temporal_filter(raw_matches, time_start, time_end)

    # Build rich context and delegate to the brain (rule-based or LLM)
    context = build_memory_context(
        user_message=message,
        query_used=query,
        raw_matches=raw_matches,
        time_filtered=time_filtered,
        time_start=time_start,
        time_end=time_end,
        all_items=all_items,
    )

    brain = get_brain()
    answer = brain.generate_response(
        user_message=message,
        memories=raw_matches,  # type: ignore[arg-type]
        context=context,
    )

    logger.info(
        "chat_recall: msg=%r query=%r matches=%d time_filter=%s brain=%s",
        message[:60],
        query,
        len(raw_matches),
        time_filtered,
        brain.mode().value,
    )

    return {
        "answer":     answer,
        "matches":    raw_matches[:top_n],
        "count":      len(raw_matches),
        "query_used": query,
        "brain_mode": brain.mode().value,
    }
