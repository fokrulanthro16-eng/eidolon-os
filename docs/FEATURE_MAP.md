# EIDOLON OS — Feature Map

All implemented features across 20 phases. Every feature is local-only, no cloud required.

---

## Phase 1–5: Core Memory Foundation

| Feature | Endpoint | Service |
|---------|----------|---------|
| Timeline | GET /memory/timeline | memory_store |
| Image ingestion + OCR | POST /memory/ingest-image | ocr_service |
| PDF ingestion | POST /memory/ingest-pdf | pdf_service |
| Hybrid search | POST /memory/search | search_service |
| Session detection | GET /sessions/list | session_service |
| Session replay (v1) | GET /sessions/{id}/replay | replay_service |

## Phase 6–7: Intelligence Layer

| Feature | Endpoint | Service |
|---------|----------|---------|
| Profile / Digital Soul | GET /profile/summary | profile_service |
| Autonomous suggestions | GET /suggestions | suggestions_service |
| PDF Chat | POST /pdf/chat | pdf_service |
| Export | POST /export | export_service |

## Phase 8–9: Modality Expansion

| Feature | Endpoint | Service |
|---------|----------|---------|
| Voice ingestion | POST /memory/ingest-audio | voice_service |
| Voice search | POST /memory/search | search_service |
| Memory graph | GET /graph/overview | graph_service |
| Graph for session | GET /graph/session/{id} | graph_service |

## Phase 10: Video Intelligence

| Feature | Endpoint | Service |
|---------|----------|---------|
| Video upload + YOLO | POST /vision/ingest-video | video_service |
| Video event timeline | GET /video/{id}/events | video_service |
| Live camera (CCTV) | POST /vision/camera/start | camera_service |
| Camera events → memory | (background) | camera_service |

## Phase 11: Vision Intelligence

| Feature | Endpoint | Service |
|---------|----------|---------|
| App fingerprinting | (embedded) | vision_intelligence_service |
| Workflow detection | GET /agent/workflow | workflow_service |
| Smart titles | (embedded) | vision_intelligence_service |
| Probable task | (embedded) | vision_intelligence_service |
| Daily summary | GET /agent/daily-summary | workflow_service |

## Phase 12: AI Agent Mode

| Feature | Endpoint | Service |
|---------|----------|---------|
| List safe actions | GET /agent/actions | agent_service |
| Execute action | POST /agent/execute | agent_service |
| Agent status | GET /agent/status | agent_service |

**Safe actions:** open_app, open_folder, summarize_today, search_memories, open_latest_pdf, continue_last_session, start_screen_watch, stop_screen_watch

## Phase 13: Replay Engine 2.0

| Feature | Endpoint | Service |
|---------|----------|---------|
| Replay by date | GET /replay/day?date= | replay_intelligence_service |
| Replay by topic | GET /replay/topic?query= | replay_intelligence_service |
| Replay by modality | GET /replay/modality?type= | replay_intelligence_service |
| Smart session replay | GET /replay/session/{id}/smart | replay_intelligence_service |

**Key moment types:** debug_start, ai_research, pdf_upload, voice_capture, camera_event, app_switch

## Phase 14: Digital Soul Intelligence

| Feature | Endpoint | Service |
|---------|----------|---------|
| Full soul profile | GET /soul/profile | digital_soul_service |
| Behavioral patterns | GET /soul/patterns | digital_soul_service |
| Workflow rhythm | GET /soul/workflow-rhythm | digital_soul_service |
| Project memory | GET /soul/project-memory | digital_soul_service |

**Pattern types:** Coding Focus, Active Researcher, Document Reader, Voice Note Taker, Multi-Tool Workflow, Active Debugger

## Phase 15: Neural Cross-Modal Search

| Feature | Endpoint | Service |
|---------|----------|---------|
| Neural search | POST /search/neural | cross_modal_search_service |

**Returns:** answer_summary, grouped_by_modality, timeline, confidence, search_mode (hybrid/keyword/fallback)

## Phase 16: Multi-Camera Intelligence

| Feature | Endpoint | Service |
|---------|----------|---------|
| List cameras | GET /cameras/list | multi_camera_service |
| Add camera | POST /cameras/add | multi_camera_service |
| Start camera | POST /cameras/{id}/start | multi_camera_service |
| Stop camera | POST /cameras/{id}/stop | multi_camera_service |
| Camera status | GET /cameras/{id}/status | multi_camera_service |
| Camera events | GET /cameras/events | multi_camera_service |
| Delete camera | DELETE /cameras/{id} | multi_camera_service |

**Source types:** webcam (device index), rtsp (URL), file (path for replay/testing)
**Registry:** persisted to `storage/cameras/camera_registry.json`

## Phase 17: World Model Layer

| Feature | Endpoint | Service |
|---------|----------|---------|
| World state snapshot | GET /world/state | world_model_service |
| Active camera predictions | GET /world/predictions | world_model_service |
| Recent camera events | GET /world/events | world_model_service |

**World state includes:** world_state text, active_entities, recent_events, movement_predictions, zones (3×3 grid), risk_notes, confidence, disclaimer
**All predictions labeled [Estimated] — heuristic, not guaranteed**

## Phase 18: Brain Adapter (Optional Local LLM)

| Feature | Endpoint | Service |
|---------|----------|---------|
| Brain status | GET /brain/status | brain_router |
| Brain chat | POST /brain/chat | brain_router |
| Re-probe brain | POST /brain/reset | brain_router |

**Default provider:** `local_semantic` (zero dependencies, always works)
**Optional:** `BRAIN_PROVIDER=ollama` or `BRAIN_PROVIDER=lmstudio` in .env
**No model download, no crash, graceful fallback everywhere**

---

## Prediction Layer (bundled with Phase 10)

| Feature | Endpoint | Service |
|---------|----------|---------|
| Active predictions | GET /vision/camera/predictions/active | prediction_service |

**Prediction events:** person_moving_toward_camera, person_leaving_scene, vehicle_entering_area, object_stationary_too_long, possible_crossing_motion
