import logging

from fastapi import APIRouter

from apps.api.models.schemas import HealthResponse, ServiceStatus

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


@router.get("/api/v1/health", response_model=HealthResponse)
async def health():
    services: list[ServiceStatus] = []

    # PostgreSQL + pgvector
    try:
        from apps.api.engines.memory.vector_store import count_chunks
        count = await count_chunks()
        services.append(ServiceStatus(name="pgvector", status="ok", detail=f"{count} chunks"))
    except Exception as e:
        services.append(ServiceStatus(name="pgvector", status="down", detail=str(e)[:120]))

    # Redis
    try:
        import redis
        r = redis.from_url("redis://localhost:6379/0", socket_connect_timeout=2)
        r.ping()
        services.append(ServiceStatus(name="redis", status="ok"))
    except Exception as e:
        services.append(ServiceStatus(name="redis", status="down", detail=str(e)[:80]))

    # Embedder
    try:
        from apps.api.engines.memory.embedder import get_embedder
        dim = get_embedder().dimension
        services.append(ServiceStatus(name="embedder", status="ok", detail=f"dim={dim}"))
    except Exception as e:
        services.append(ServiceStatus(name="embedder", status="down", detail=str(e)[:80]))

    # OCR
    try:
        from apps.api.engines.memory.ocr.paddle_ocr import get_ocr_engine
        _ = get_ocr_engine()
        services.append(ServiceStatus(name="paddleocr", status="ok"))
    except Exception as e:
        services.append(ServiceStatus(name="paddleocr", status="degraded", detail=str(e)[:80]))

    # Ollama / Qwen2-VL
    try:
        import httpx
        from apps.api.config import settings
        r2 = httpx.get(f"{settings.ollama_base_url}/api/tags", timeout=2.0)
        services.append(ServiceStatus(
            name="ollama", status="ok" if r2.status_code == 200 else "degraded",
            detail=f"HTTP {r2.status_code} — {settings.qwen_vl_model}",
        ))
    except Exception:
        services.append(ServiceStatus(name="ollama", status="down", detail="Not reachable"))

    critical = {"pgvector", "embedder"}
    down_critical = any(s.status == "down" and s.name in critical for s in services)
    any_degraded = any(s.status in ("down", "degraded") for s in services)

    return HealthResponse(
        status="down" if down_critical else ("degraded" if any_degraded else "ok"),
        services=services,
    )
