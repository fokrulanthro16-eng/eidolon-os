import uuid


def create_memory_id() -> str:
    """Return a short, readable memory ID: mem_<8-char hex>."""
    return f"mem_{uuid.uuid4().hex[:8]}"
