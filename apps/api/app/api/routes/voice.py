"""
Voice Memory endpoint.

POST /voice/ingest-audio   — upload audio, transcribe with Whisper (if available),
                             create a searchable MemoryItem of type "voice"

Accepted formats: .mp3 .wav .m4a .ogg .flac .webm
Requires faster-whisper for transcription (pip install faster-whisper).
Falls back to metadata-only memory when Whisper is not installed.
"""

import logging

from fastapi import APIRouter, File, UploadFile, status

from app.models.memory import MemoryItem
from app.services.embedding_service import embedding_service
from app.services.memory_store import memory_store
from app.services.storage_service import save_audio_file
from app.services.voice_service import format_duration, is_available, transcribe_audio
from app.utils.ids import create_memory_id
from app.utils.time import utc_now_iso

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/voice", tags=["voice"])


@router.post(
    "/ingest-audio",
    status_code=status.HTTP_201_CREATED,
    summary="Upload audio for transcription and voice memory creation",
)
async def ingest_audio(file: UploadFile = File(...)):
    """
    Upload an audio file (.mp3 .wav .m4a .ogg .flac .webm).

    Pipeline:
        validate → save → transcribe (faster-whisper if available) → embed → persist

    If faster-whisper is not installed the file is stored and a placeholder
    memory is created; transcription can be added later after install.
    """
    memory_id = create_memory_id()
    now = utc_now_iso()
    original_name = file.filename or "recording.mp3"

    saved_path = await save_audio_file(file=file, memory_id=memory_id)
    file_size = saved_path.stat().st_size

    whisper_ok = is_available()
    transcript_result = transcribe_audio(saved_path) if whisper_ok else None

    if transcript_result and transcript_result.get("available"):
        transcript = transcript_result.get("text", "").strip()
        language = transcript_result.get("language", "unknown")
        duration_secs = transcript_result.get("duration_secs", 0.0)
        confidence = transcript_result.get("transcript_confidence", 0.0)
        duration_str = format_duration(duration_secs)
        title = f"Voice: {duration_str}"
        text = transcript or f"Audio recording ({duration_str})"
        transcript_available = bool(transcript)
        engine = "faster-whisper"
        fallback_mode = False
    else:
        title = f"Voice: {original_name}"
        text = (
            "Audio recording stored. Install faster-whisper for transcription: "
            "pip install faster-whisper"
        )
        language = "unknown"
        duration_secs = 0.0
        confidence = 0.0
        transcript_available = False
        engine = "none"
        fallback_mode = True

    tags = ["voice", "audio"]
    if transcript_available:
        tags.append("transcript")

    item = MemoryItem(
        id=memory_id,
        type="voice",
        title=title,
        text=text,
        file_path=str(saved_path),
        source="voice_upload",
        tags=tags,
        metadata={
            "original_filename":     original_name,
            "file_size":             file_size,
            "duration_secs":         duration_secs,
            "language":              language,
            "transcript_available":  transcript_available,
            "engine":                engine,
            "confidence":            round(confidence, 3),
            "fallback_mode":         fallback_mode,
        },
        created_at=now,
        updated_at=now,
    )

    item_dict = item.model_dump()
    embedding = embedding_service.embed_for_storage(title, text)
    if embedding is not None:
        item_dict["embedding"] = embedding

    saved = memory_store.add(item_dict)
    logger.info(
        "Voice memory ingested: %s  engine=%s  transcript=%s  duration=%.1fs",
        memory_id, engine, transcript_available, duration_secs,
    )

    return {
        "success":              True,
        "memory_id":            memory_id,
        "transcript_available": transcript_available,
        "language":             language,
        "duration_secs":        duration_secs,
        "fallback_mode":        fallback_mode,
        "memory":               saved,
    }
