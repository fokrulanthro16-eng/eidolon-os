"""
Quick smoke test — ingest a test image + run a search.
Run from project root: python scripts/seed_test.py
"""
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


async def main():
    from PIL import Image, ImageDraw, ImageFont
    from apps.api.db.database import AsyncSessionLocal, init_db
    from apps.api.engines.memory.ingestion import ingest_image, ingest_text
    from apps.api.engines.memory.vector_store import get_vector_store
    from apps.api.engines.memory.embedder import get_embedder

    print("Initializing DB...")
    await init_db()

    # Create a synthetic test image with text
    img = Image.new("RGB", (800, 400), color=(30, 30, 40))
    d = ImageDraw.Draw(img)
    d.text((50, 50), "EIDOLON OS — Memory Test", fill=(0, 220, 120))
    d.text((50, 120), "Screen capture: VSCode editor open", fill=(200, 200, 200))
    d.text((50, 160), "Working on neural embedding pipeline", fill=(200, 200, 200))
    d.text((50, 200), "File: engines/memory/embedder.py", fill=(150, 150, 255))

    print("Ingesting test image...")
    async with AsyncSessionLocal() as db:
        record = await ingest_image(
            image=img,
            db=db,
            source_type="screenshot",
            source_app="Test",
            window_title="EIDOLON Smoke Test",
        )
    print(f"  record_id={record.id}, chunks={record.chunk_count}, conf={record.ocr_confidence}")

    print("\nIngesting test text...")
    async with AsyncSessionLocal() as db:
        rec2 = await ingest_text(
            text="Python FastAPI backend with ChromaDB vector storage and sentence transformers for semantic search.",
            db=db,
            source_type="note",
            source_app="Test",
        )
    print(f"  record_id={rec2.id}, chunks={rec2.chunk_count}")

    print("\nRunning semantic search: 'neural embedding'")
    query_vec = get_embedder().embed_query("neural embedding")
    results = get_vector_store().search(query_vec, top_k=5)
    for i, r in enumerate(results):
        print(f"  [{i+1}] score={r['score']:.3f} | {r['chunk_text'][:80]}")

    print("\nSmoke test complete.")


if __name__ == "__main__":
    asyncio.run(main())
