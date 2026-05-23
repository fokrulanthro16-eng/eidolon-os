"""
Neural Cross-Modal Search endpoint — Phase 15.

POST /search/neural — search across all memory modalities simultaneously
"""

import logging
from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/search", tags=["neural-search"])


class DateRange(BaseModel):
    start: Optional[str] = None
    end: Optional[str] = None


class NeuralSearchFilters(BaseModel):
    types: Optional[List[str]] = None
    date_range: Optional[DateRange] = None


class NeuralSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Natural language search query")
    filters: Optional[NeuralSearchFilters] = None
    limit: int = Field(default=50, ge=1, le=200)


@router.post("/neural", summary="Cross-modal neural search across all memory types")
async def neural_search(req: NeuralSearchRequest):
    """
    Search across ALL memory modalities simultaneously:
      screenshots, PDFs, voice memos, video events, camera events.

    Returns ranked results grouped by modality, a chronological timeline,
    and a rule-based answer summary.

    No LLM required — all ranking is hybrid keyword + semantic (if available).

    Example query:
      "Find when I edited CCTV frontend while discussing YOLO"
    """
    from app.services.cross_modal_search_service import neural_search as _search
    from app.services.memory_store import memory_store

    type_filter = req.filters.types if req.filters else None
    date_range  = None
    if req.filters and req.filters.date_range:
        date_range = {
            "start": req.filters.date_range.start,
            "end":   req.filters.date_range.end,
        }

    memories = memory_store.list()
    return _search(
        req.query,
        memories,
        type_filter=type_filter,
        date_range=date_range,
        limit=req.limit,
    )
