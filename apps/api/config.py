from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_cors_origins: str = "http://localhost:3000"

    # Database — PostgreSQL + pgvector
    database_url: str = "postgresql+asyncpg://eidolon:eidolon_dev@localhost:5432/eidolon_os"
    database_pool_size: int = 10
    database_max_overflow: int = 20

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # Storage
    storage_root: Path = _ROOT / "storage"
    screenshots_dir: Path = _ROOT / "storage" / "screenshots"
    uploads_dir: Path = _ROOT / "storage" / "uploads"
    thumbnails_dir: Path = _ROOT / "storage" / "thumbnails"

    # Embeddings
    embed_model: str = "BAAI/bge-m3"
    embed_device: str = "cpu"
    embed_batch_size: int = 32

    # OCR
    ocr_language: str = "en"
    ocr_confidence_threshold: float = 0.4
    ocr_use_gpu: bool = False
    ocr_use_angle_cls: bool = True

    # Screen Capture
    capture_interval_seconds: int = 30
    capture_max_width: int = 1920
    capture_enabled: bool = True

    # Ollama / Qwen2-VL
    ollama_base_url: str = "http://localhost:11434"
    qwen_vl_model: str = "qwen2-vl:2b"
    vl_enabled: bool = False

    # Memory retention
    memory_retain_days: int = 90

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.api_cors_origins.split(",")]

    def ensure_dirs(self) -> None:
        for d in [self.screenshots_dir, self.uploads_dir, self.thumbnails_dir]:
            d.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_dirs()
