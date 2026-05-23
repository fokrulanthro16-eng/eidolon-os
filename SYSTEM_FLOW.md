# EIDOLON OS — System Flow

## 1. Screen Capture Pipeline

```
screen_watcher.py (background process)
        │
        ▼  every 30 seconds
  mss.grab()  →  PIL Image  →  PNG file  (storage/screenshots/)
        │
        ▼
  Active window detection (pywin32 / psutil)
  → app_name, window_title, exe_name
        │
        ▼
  OCR extraction (pytesseract → fallback to empty)
  → text, engine, confidence
        │
        ▼
  Vision scene analysis (heuristic)
  → scene_type, workflow_type, ui_layout, visual_tags
        │
        ▼
  Build MemoryItem  { type=screenshot, text=ocr_text, metadata={...} }
        │
        ▼
  embed_for_storage(title, text)  →  optional 384-dim embedding
        │
        ▼
  memory_store.add()  →  atomic write to memories.json
```

## 2. PDF Ingestion Pipeline

```
POST /memory/ingest-pdf
        │
        ▼
  Validate + save PDF  (storage/uploads/pdfs/)
        │
        ▼
  PyMuPDF text extraction
  → text per page, page_count, pages_extracted
        │
        ▼
  OCR fallback for scanned pages (if Tesseract available)
        │
        ▼
  Build MemoryItem  { type=pdf, text=full_extracted_text }
        │
        ▼
  embed_for_storage(filename, text[:800])
        │
        ▼
  memory_store.add()
```

## 3. Video Intelligence Pipeline

```
POST /vision/ingest-video
        │
        ├── video_store.add_video()  → placeholder video record
        ├── save_video_file()         → storage/videos/
        ├── memory_store.add()        → MemoryItem type=video (status=analyzing)
        │
        └── background thread  (daemon)
                │
                ▼
          cv2.VideoCapture()  →  open video
                │
                ▼  sample 1 frame/second
          YOLO nano forward pass  (CCTV_CLASSES only)
          OR motion-only if ultralytics missing
                │
                ▼
          _SimpleTracker.update()  →  IoU matching across frames
          _MotionDetector.check()  →  absdiff > 1.5%
                │
                ▼
          emit events:
            person_appeared  /  person_left
            vehicle_appeared
            crowd_detected (≥3 persons)
            bag_detected
            motion_detected
                │
                ▼
          save JPEG thumbnail  (storage/videos/thumbnails/)
          video_store.append_events()  (flush every 50 events)
                │
                ▼  analysis complete
          video_store.update(status=done, labels=[...])
          memory_store.update(text=summary, metadata={...})
          embed_for_storage(filename, summary)
```

## 4. Search Pipeline

```
POST /memory/search  { query: "python error" }
        │
        ▼
  embed query  →  384-dim vector (optional)
        │
        ▼
  For each memory in store:
    keyword_score   = TF match in title + text
    semantic_score  = cosine(query_embedding, item_embedding)  [if available]
    recency_score   = 1 / (1 + age_days × 0.1)

    final_score = 0.35 × keyword
               + 0.55 × semantic
               + 0.10 × recency
        │
        ▼
  Sort descending, return top 20
```

## 5. PDF Chat Pipeline

```
POST /pdf/chat  { question: "...", pdf_memory_id: "..." }
        │
        ▼
  Get chunks from pdf_chunk_service
  (parse [Page N] text format, 800-1200 char overlap, MD5 dedup)
        │
        ▼
  embed question
        │
        ▼
  For each chunk:
    score = 0.70 × cosine(question, chunk) + 0.30 × keyword_overlap
        │
        ▼
  Select top-K chunks above threshold
        │
        ▼
  _build_answer():
    concatenate unique chunk snippets  (max 800 chars)
    confidence = min(best_score × 1.2, 1.0)
        │
        ▼
  Return { answer, pdf_title, matched_chunks, confidence, source_pages }
```

## 6. Memory Graph Pipeline

```
GET /graph/overview
        │
        ▼
  memories = memory_store.list()[-120:]
        │
        ├── _session_edges()    → shared session_id
        ├── _time_edges()       → within 30 min window
        ├── _app_edges()        → same metadata.app_name
        ├── _topic_edges()      → 3+ shared non-noise keywords
        ├── _workflow_edges()   → same non-trivial workflow_type
        └── _semantic_edges()   → cosine ≥ 0.70 (if embeddings)
                │
                ▼
          Deduplicate (frozenset key)
          Cap edges per node (MAX_EDGES_PER_NODE = 8)
                │
                ▼
          Return { nodes, edges, stats }
```

## 7. Suggestion Pipeline

```
GET /suggestions
        │
        ▼
  memories = memory_store.list()
        │
        ├── _pdf_cluster_suggestions()  → 3+ PDFs share keyword
        ├── _app_dominance_suggestion() → one app > 40%
        ├── _time_pattern_suggestion()  → top 3 hours > 45% activity
        ├── _topic_insight_suggestion() → keyword in 4+ recent memories
        └── _session_pattern_suggestion() → session > 2h
                │
                ▼
          Load dismissed IDs from dismissed_suggestions.json
          Filter dismissed suggestions
          Sort by confidence desc, cap at 5
                │
                ▼
          Return { count, suggestions }
```
