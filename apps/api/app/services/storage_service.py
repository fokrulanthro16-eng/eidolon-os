import re
from pathlib import Path

from fastapi import HTTPException, UploadFile

from app.core.config import (
    ALLOWED_IMAGE_EXTENSIONS,
    ALLOWED_VIDEO_EXTENSIONS,
    AUDIO_UPLOADS_DIR,
    MAX_AUDIO_BYTES,
    MAX_PDF_BYTES,
    MAX_UPLOAD_BYTES,
    MAX_VIDEO_BYTES,
    PDF_UPLOADS_DIR,
    UPLOADS_DIR,
    VIDEO_DB_DIR,
    VIDEO_THUMBS_DIR,
    VIDEOS_DIR,
)


def ensure_storage_dirs() -> None:
    """Create all required storage directories if they do not exist."""
    from app.core.config import MEMORY_DB_DIR, SCREENSHOTS_DIR, SESSION_DB_DIR
    for directory in (
        UPLOADS_DIR, PDF_UPLOADS_DIR, AUDIO_UPLOADS_DIR,
        VIDEOS_DIR, VIDEO_THUMBS_DIR, VIDEO_DB_DIR,
        SCREENSHOTS_DIR, MEMORY_DB_DIR, SESSION_DB_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)


def sanitize_filename(filename: str) -> str:
    """
    Strip directory components and replace unsafe characters.
    Prevents path traversal attacks.
    """
    # Take only the final component — kills any ../ or subdirectory tricks
    name = Path(filename).name
    # Replace anything that isn't alphanumeric, dash, underscore, or dot
    name = re.sub(r"[^\w\-.]", "_", name)
    # Collapse multiple underscores/dots
    name = re.sub(r"_+", "_", name)
    return name or "upload"


def validate_image_extension(filename: str) -> None:
    """Raise HTTP 400 if the file extension is not in ALLOWED_IMAGE_EXTENSIONS."""
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type '{ext}'. "
                f"Allowed: {', '.join(sorted(ALLOWED_IMAGE_EXTENSIONS))}"
            ),
        )


async def save_upload_file(file: UploadFile, memory_id: str) -> Path:
    """
    Validate, sanitize, and save an uploaded image.

    Filename format: {memory_id}_{sanitized_original_name}
    Writes in 1 MB chunks to handle large files without loading into RAM.
    Returns the absolute Path to the saved file.
    """
    original_name = file.filename or "upload.png"
    validate_image_extension(original_name)

    safe_name = sanitize_filename(original_name)
    dest: Path = UPLOADS_DIR / f"{memory_id}_{safe_name}"

    chunk_size = 1024 * 1024  # 1 MB
    total = 0

    with open(dest, "wb") as out:
        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_UPLOAD_BYTES:
                out.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=413,
                    detail=f"File exceeds the {MAX_UPLOAD_BYTES // (1024*1024)} MB limit.",
                )
            out.write(chunk)

    return dest


def delete_file(path: str | Path | None) -> bool:
    """Delete a file safely. Returns True if deleted, False if not found."""
    if path is None:
        return False
    p = Path(path) if not isinstance(path, Path) else path
    try:
        p.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def get_image_metadata(path: Path) -> dict[str, int]:
    """
    Return basic image metadata.
    Falls back to zeros on any error rather than crashing the pipeline.
    """
    try:
        from PIL import Image
        with Image.open(path) as img:
            width, height = img.size
        file_size = path.stat().st_size
        return {"width": width, "height": height, "file_size": file_size}
    except Exception:
        return {"width": 0, "height": 0, "file_size": 0}


async def save_audio_file(file: UploadFile, memory_id: str) -> Path:
    """
    Validate and save an uploaded audio file to AUDIO_UPLOADS_DIR.
    Accepts .mp3, .wav, .m4a, .ogg, .flac, .webm
    Returns the absolute Path to the saved file.
    """
    from app.services.voice_service import ALLOWED_AUDIO_EXTENSIONS
    original_name = file.filename or "recording.mp3"
    ext = Path(original_name).suffix.lower()
    if ext not in ALLOWED_AUDIO_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported audio type '{ext}'. "
                f"Allowed: {', '.join(sorted(ALLOWED_AUDIO_EXTENSIONS))}"
            ),
        )

    safe_name = sanitize_filename(original_name)
    dest: Path = AUDIO_UPLOADS_DIR / f"{memory_id}_{safe_name}"

    chunk_size = 1024 * 1024  # 1 MB
    total = 0

    with open(dest, "wb") as out:
        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_AUDIO_BYTES:
                out.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=413,
                    detail=f"Audio file exceeds the {MAX_AUDIO_BYTES // (1024 * 1024)} MB limit.",
                )
            out.write(chunk)

    return dest


async def save_video_file(file: UploadFile, video_id: str) -> Path:
    """
    Validate and save an uploaded video file to VIDEOS_DIR.
    Accepts .mp4 .avi .mov .mkv .wmv .webm .m4v up to MAX_VIDEO_MB.
    Returns the absolute Path to the saved file.
    """
    original_name = file.filename or "video.mp4"
    ext = Path(original_name).suffix.lower()
    if ext not in ALLOWED_VIDEO_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported video type '{ext}'. "
                f"Allowed: {', '.join(sorted(ALLOWED_VIDEO_EXTENSIONS))}"
            ),
        )

    safe_name = sanitize_filename(original_name)
    dest: Path = VIDEOS_DIR / f"{video_id}_{safe_name}"

    chunk_size = 4 * 1024 * 1024  # 4 MB chunks for large videos
    total = 0

    with open(dest, "wb") as out:
        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_VIDEO_BYTES:
                out.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=413,
                    detail=f"Video exceeds the {MAX_VIDEO_BYTES // (1024 * 1024)} MB limit.",
                )
            out.write(chunk)

    return dest


async def save_pdf_file(file: UploadFile, memory_id: str) -> Path:
    """
    Validate and save an uploaded PDF file to PDF_UPLOADS_DIR.

    Filename format: {memory_id}_{sanitized_original_name}
    Writes in 1 MB chunks to handle large files without loading into RAM.
    Returns the absolute Path to the saved file.
    """
    original_name = file.filename or "document.pdf"
    if not original_name.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are accepted (.pdf extension required).",
        )

    safe_name = sanitize_filename(original_name)
    if not safe_name.lower().endswith(".pdf"):
        safe_name += ".pdf"

    dest: Path = PDF_UPLOADS_DIR / f"{memory_id}_{safe_name}"

    chunk_size = 1024 * 1024  # 1 MB
    total = 0

    with open(dest, "wb") as out:
        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_PDF_BYTES:
                out.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=413,
                    detail=f"PDF exceeds the {MAX_PDF_BYTES // (1024 * 1024)} MB limit.",
                )
            out.write(chunk)

    return dest
