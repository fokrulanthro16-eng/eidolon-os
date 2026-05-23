"""
Voice transcription service using faster-whisper (optional).

Gracefully degrades if faster-whisper is not installed:
  - Audio file is still stored as a memory item
  - Text field contains a clear installation hint
  - All downstream search / session features work as soon as transcription runs

Model: "base"  (~145 MB, downloads once to ~/.cache/huggingface/hub/)
Device: CPU + int8 quantisation → runs on any machine, no GPU required
"""

import logging
import math
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_MODEL_SIZE = "base"          # "tiny" (39 MB) | "base" (145 MB) | "small" (244 MB)
_BEAM_SIZE  = 3
_FALLBACK_MSG = (
    "[Voice transcription requires faster-whisper. "
    "Install with: pip install faster-whisper]"
)

_model       = None
_model_lock  = threading.Lock()
_available:  bool | None = None

ALLOWED_AUDIO_EXTENSIONS: frozenset[str] = frozenset(
    {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".webm"}
)


# ---------------------------------------------------------------------------
# Availability probe
# ---------------------------------------------------------------------------

def is_available() -> bool:
    """Return True if faster-whisper is importable."""
    global _available
    if _available is None:
        try:
            import faster_whisper  # noqa: F401
            _available = True
        except ImportError:
            _available = False
            logger.info("faster-whisper not installed — voice transcription disabled.")
    return _available


# ---------------------------------------------------------------------------
# Lazy model loader
# ---------------------------------------------------------------------------

def _get_model():
    global _model
    if _model is not None:
        return _model
    if not is_available():
        return None
    with _model_lock:
        if _model is not None:  # double-checked locking
            return _model
        try:
            from faster_whisper import WhisperModel
            logger.info("Loading Whisper %s model (CPU / int8)…", _MODEL_SIZE)
            _model = WhisperModel(_MODEL_SIZE, device="cpu", compute_type="int8")
            logger.info("Whisper model ready.")
        except Exception as exc:
            logger.warning("Failed to load Whisper model: %s", exc)
            _model = None
    return _model


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def transcribe_audio(path: Path) -> dict[str, Any]:
    """
    Transcribe an audio file.

    Returns
    -------
    text                str   — transcript or informational fallback
    language            str   — detected language code (e.g. "en") or "unknown"
    duration_secs       float — audio duration in seconds (0.0 if unavailable)
    transcript_confidence float — 0–1 (rough estimate from per-segment avg_logprob)
    available           bool  — False when transcription was skipped
    """
    if not is_available():
        return _fallback(False, msg=_FALLBACK_MSG)

    model = _get_model()
    if model is None:
        return _fallback(False, msg="[Whisper model failed to load. Try: pip install faster-whisper]")

    try:
        segments_iter, info = model.transcribe(
            str(path),
            beam_size=_BEAM_SIZE,
            language=None,       # auto-detect
            vad_filter=True,     # skip silence — faster for long audio
            vad_parameters={"min_silence_duration_ms": 500},
        )

        parts: list[str]    = []
        log_probs: list[float] = []

        for seg in segments_iter:
            text = seg.text.strip()
            if text:
                parts.append(text)
            if hasattr(seg, "avg_logprob"):
                # avg_logprob is ≤ 0; convert to a rough 0–1 probability
                log_probs.append(min(1.0, math.exp(seg.avg_logprob)))

        transcript = " ".join(parts) or "[No speech detected]"
        avg_conf   = (sum(log_probs) / len(log_probs)) if log_probs else 0.5

        return {
            "text":                  transcript,
            "language":              info.language or "unknown",
            "duration_secs":         round(info.duration, 2),
            "transcript_confidence": round(avg_conf, 3),
            "available":             True,
        }

    except Exception as exc:
        logger.warning("Transcription failed for '%s': %s", path.name, exc)
        return _fallback(False, msg=f"[Transcription failed: {exc}]")


def _fallback(available: bool, msg: str) -> dict[str, Any]:
    return {
        "text":                  msg,
        "language":              "unknown",
        "duration_secs":         0.0,
        "transcript_confidence": 0.0,
        "available":             available,
    }


def format_duration(secs: float) -> str:
    """Format seconds → "1m 23s" or "45s"."""
    if secs < 60:
        return f"{int(secs)}s"
    m = int(secs / 60)
    s = int(secs % 60)
    return f"{m}m {s}s" if s else f"{m}m"
