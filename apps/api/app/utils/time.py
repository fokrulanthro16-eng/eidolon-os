from datetime import datetime, timezone


def utc_now_iso() -> str:
    """Return the current UTC time as a timezone-aware ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()
