"""
World Model Service — Phase 17.

Aggregates video/camera events, active entity tracks, and prediction
data into a simple world-state snapshot.

Rules:
- Heuristic only — no genuine security guarantee
- All predictions labeled as [Estimated]
- Confidence capped at 0.88
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

_CACHE_TTL = 5  # seconds — live data, keep fresh
_cache: dict[str, Any] = {}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_dt(iso: str | None) -> datetime | None:
    if not iso:
        return None
    try:
        s = iso.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _zone(cx: float, cy: float) -> str:
    """Map normalized (0-1) coordinates to a simple 3×3 grid label."""
    col = "left" if cx < 0.33 else ("right" if cx > 0.67 else "center")
    row = "top"  if cy < 0.33 else ("bottom" if cy > 0.67 else "mid")
    return f"{row}-{col}"


# ---------------------------------------------------------------------------
# Event extraction helpers
# ---------------------------------------------------------------------------

def get_recent_camera_events(memories: list[dict], limit: int = 30) -> list[dict]:
    """Return recent camera / video events from the memory store."""
    events = [
        m for m in memories
        if m.get("type") == "video"
        and m.get("source") in ("live_camera", "video_upload", "video_analysis")
    ]
    events.sort(key=lambda m: m.get("created_at", ""), reverse=True)
    return events[:limit]


def _extract_entity_tracks(events: list[dict]) -> dict[str, dict]:
    """Build per-label entity summary from recent events."""
    entities: dict[str, dict] = {}
    for ev in events:
        meta   = ev.get("metadata") or {}
        labels = meta.get("labels") or meta.get("detected_objects") or ["motion"]
        for lbl in labels:
            if lbl not in entities:
                entities[lbl] = {
                    "count":      0,
                    "last_seen":  ev.get("created_at", ""),
                    "event_type": meta.get("event_type", "motion_detected"),
                }
            entities[lbl]["count"] += 1
    return entities


def _build_risk_notes(
    entities: dict[str, dict],
    predictions: list[dict],
) -> list[str]:
    """Heuristic risk notes — all labeled [Estimated]."""
    notes: list[str] = []

    person_count = entities.get("person", {}).get("count", 0)
    if person_count >= 3:
        notes.append(
            f"[Estimated] {person_count} person appearances detected recently."
        )

    for p in predictions:
        if p.get("direction") == "stationary" and p.get("stationary_secs", 0) > 10:
            notes.append(
                f"[Estimated] {p.get('label', 'Object')} appears stationary "
                f"for {int(p.get('stationary_secs', 0))}s."
            )

    vehicle_labels = {"car", "truck", "bus", "motorcycle", "bicycle"}
    for lbl, info in entities.items():
        if lbl in vehicle_labels and info["count"] >= 1:
            notes.append(
                f"[Estimated] Vehicle ({lbl}) observed {info['count']} time(s) recently."
            )
            break

    approaching = [p for p in predictions if p.get("direction") == "approaching"]
    if approaching:
        labels = ", ".join(p.get("label", "object") for p in approaching[:2])
        notes.append(f"[Estimated] {labels} moving toward camera.")

    return notes[:5]


# ---------------------------------------------------------------------------
# Core computation
# ---------------------------------------------------------------------------

def _compute_world_state(
    memories: list[dict],
    predictions: list[dict],
) -> dict:
    recent_events  = get_recent_camera_events(memories, limit=20)
    entity_tracks  = _extract_entity_tracks(recent_events)
    cutoff         = _utc_now() - timedelta(seconds=120)

    # Active entities — seen within the last 2 minutes
    active_entities: list[dict] = []
    for lbl, info in entity_tracks.items():
        dt = _parse_dt(info["last_seen"])
        if dt and dt >= cutoff:
            active_entities.append({
                "label":     lbl,
                "count":     info["count"],
                "last_seen": info["last_seen"],
                "active":    True,
            })

    # World state text
    if not recent_events:
        world_state = (
            "No recent camera events. Start a camera or upload a video "
            "to build world state."
        )
    elif active_entities:
        labels      = [e["label"] for e in active_entities[:3]]
        world_state = f"Active scene: {', '.join(labels)} detected recently."
    else:
        world_state = "Scene appears quiet — no activity in the last 2 minutes."

    # Zone map from live predictions
    zones: dict[str, list[str]] = defaultdict(list)
    for p in predictions:
        z = _zone(p.get("current_x", 0.5), p.get("current_y", 0.5))
        zones[z].append(p.get("label", "object"))

    # Movement predictions
    movement_preds = [
        {
            "track_id":    p.get("track_id"),
            "label":       p.get("label"),
            "direction":   p.get("direction"),
            "speed":       round(p.get("speed", 0), 3),
            "predicted_x": round(p.get("predicted_x", 0), 3),
            "predicted_y": round(p.get("predicted_y", 0), 3),
            "confidence":  round(p.get("confidence", 0), 2),
            "note":        "[Estimated] Heuristic linear extrapolation only.",
        }
        for p in predictions[:8]
    ]

    risk_notes = _build_risk_notes(entity_tracks, predictions)

    # Activity timeline
    timeline: list[dict] = []
    for ev in recent_events[:10]:
        meta = ev.get("metadata") or {}
        timeline.append({
            "created_at":  ev.get("created_at"),
            "event_type":  meta.get("event_type", "motion_detected"),
            "labels":      meta.get("labels") or meta.get("detected_objects") or ["motion"],
            "camera_id":   meta.get("camera_id"),
            "camera_name": meta.get("camera_name"),
        })

    confidence = round(min(0.35 + 0.05 * len(recent_events), 0.88), 2)

    return {
        "world_state":           world_state,
        "active_entities":       active_entities,
        "recent_events":         timeline,
        "movement_predictions":  movement_preds,
        "zones":                 dict(zones),
        "risk_notes":            risk_notes,
        "confidence":            confidence,
        "total_events_analyzed": len(recent_events),
        "prediction_count":      len(predictions),
        "disclaimer": (
            "World model is heuristic. Predictions are estimated, not guaranteed. "
            "Not a security system."
        ),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_world_state(memories: list[dict], predictions: list[dict]) -> dict:
    """Return current world state, with short TTL cache."""
    entry = _cache.get("world_state")
    now   = _utc_now()
    if entry and (now - entry["ts"]).total_seconds() < _CACHE_TTL:
        return entry["value"]
    value = _compute_world_state(memories, predictions)
    _cache["world_state"] = {"value": value, "ts": now}
    return value
