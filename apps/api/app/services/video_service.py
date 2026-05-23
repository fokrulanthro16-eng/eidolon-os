"""
Video Intelligence Service — YOLO nano + motion detection + IoU tracking.

Dependencies (all optional at import time):
    pip install opencv-python-headless ultralytics numpy

Analysis pipeline
-----------------
1. Open video with OpenCV, sample at SAMPLE_FPS (default 1 fps).
2. Run YOLOv8n on each sampled frame (CCTV-relevant classes only).
3. Track objects across frames with a simple IoU matcher.
4. Detect motion via frame differencing (cv2.absdiff).
5. Emit VideoEvent dicts when notable things happen.
6. Generate JPEG thumbnail from the first person/crowd event frame.
7. Write events to video_store in batches; update progress on record.
"""

import logging
import threading
import time
import uuid
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# COCO class IDs that matter for CCTV / activity intelligence
CCTV_CLASSES: list[int] = [
    0,   # person
    1,   # bicycle
    2,   # car
    3,   # motorcycle
    5,   # bus
    7,   # truck
    24,  # backpack
    25,  # umbrella
    26,  # handbag
    28,  # suitcase
]

COCO_NAMES: dict[int, str] = {
    0: "person", 1: "bicycle", 2: "car", 3: "motorcycle",
    5: "bus", 7: "truck", 24: "backpack", 25: "umbrella",
    26: "handbag", 28: "suitcase",
}

SAMPLE_FPS: float     = 1.0      # analyse 1 frame per second
MAX_FRAMES: int       = 10_800   # cap at 3 h of footage
CONF_THRESHOLD: float = 0.40
IOU_THRESHOLD: float  = 0.30
MOTION_THRESHOLD: float = 0.015  # 1.5 % pixels changed = motion
CROWD_THRESHOLD: int  = 3        # persons ≥ this = crowd
TRACK_TIMEOUT: int    = 5        # sampled frames before track evicted
THUMB_W: int          = 320
THUMB_H: int          = 180
EVENT_BATCH: int      = 50       # flush events every N events


# ---------------------------------------------------------------------------
# Availability probe
# ---------------------------------------------------------------------------

def is_available() -> tuple[bool, bool]:
    """Return (opencv_ok, yolo_ok). Both must be True for full analysis."""
    cv_ok = False
    yolo_ok = False
    try:
        import cv2  # noqa: F401
        cv_ok = True
    except ImportError:
        pass
    try:
        from ultralytics import YOLO  # noqa: F401
        yolo_ok = True
    except ImportError:
        pass
    return cv_ok, yolo_ok


# ---------------------------------------------------------------------------
# Simple IoU tracker
# ---------------------------------------------------------------------------

class _Track:
    __slots__ = ("track_id", "cls_id", "box", "age", "last_seen")

    def __init__(self, track_id: str, cls_id: int, box: list[float], frame_idx: int) -> None:
        self.track_id = track_id
        self.cls_id   = cls_id
        self.box      = box          # [x1, y1, x2, y2] normalised 0-1
        self.age      = 0
        self.last_seen = frame_idx


def _iou(a: list[float], b: list[float]) -> float:
    """IoU between two [x1, y1, x2, y2] boxes."""
    ix1 = max(a[0], b[0]); iy1 = max(a[1], b[1])
    ix2 = min(a[2], b[2]); iy2 = min(a[3], b[3])
    iw = max(0.0, ix2 - ix1); ih = max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter == 0:
        return 0.0
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    return inter / (area_a + area_b - inter)


class _SimpleTracker:
    """Greedy IoU matcher — works well for 1 fps sparse sampling."""

    def __init__(self) -> None:
        self._tracks: list[_Track] = []
        self._counter = 0

    def _new_id(self) -> str:
        self._counter += 1
        return f"T{self._counter:04d}"

    def update(
        self,
        detections: list[dict],  # [{cls_id, box, conf}]
        frame_idx: int,
    ) -> tuple[list[dict], list[dict]]:
        """
        Match detections to existing tracks.
        Returns (matched_dets, new_dets).
        matched_dets have track_id injected.
        new_dets are freshly created tracks.
        """
        unmatched_dets = list(detections)
        matched: list[dict] = []
        new_tracks: list[dict] = []

        for track in self._tracks:
            if not unmatched_dets:
                break
            best_idx, best_iou = -1, 0.0
            for i, det in enumerate(unmatched_dets):
                if det["cls_id"] != track.cls_id:
                    continue
                score = _iou(track.box, det["box"])
                if score > best_iou:
                    best_iou, best_idx = score, i
            if best_idx >= 0 and best_iou >= IOU_THRESHOLD:
                det = unmatched_dets.pop(best_idx)
                det["track_id"] = track.track_id
                track.box = det["box"]
                track.last_seen = frame_idx
                track.age += 1
                matched.append(det)

        # New detections become new tracks
        for det in unmatched_dets:
            t = _Track(self._new_id(), det["cls_id"], det["box"], frame_idx)
            self._tracks.append(t)
            det["track_id"] = t.track_id
            new_tracks.append(det)

        # Evict stale tracks
        self._tracks = [
            t for t in self._tracks
            if (frame_idx - t.last_seen) <= TRACK_TIMEOUT
        ]

        return matched, new_tracks

    def active_ids(self) -> list[str]:
        return [t.track_id for t in self._tracks]

    def active_count_by_class(self, cls_id: int) -> int:
        return sum(1 for t in self._tracks if t.cls_id == cls_id)


# ---------------------------------------------------------------------------
# Thumbnail helper
# ---------------------------------------------------------------------------

def _save_thumbnail(frame, video_id: str, event_id: str) -> str | None:
    """
    Resize frame to THUMB_W×THUMB_H, save as JPEG.
    Returns relative URL path or None on failure.
    """
    try:
        import cv2
        from app.core.config import VIDEO_THUMBS_DIR
        thumb = cv2.resize(frame, (THUMB_W, THUMB_H))
        name = f"{video_id}_{event_id}.jpg"
        path = VIDEO_THUMBS_DIR / name
        cv2.imwrite(str(path), thumb, [cv2.IMWRITE_JPEG_QUALITY, 80])
        return f"/video-thumbs/{name}"
    except Exception as exc:
        logger.debug("thumbnail save failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Motion detector
# ---------------------------------------------------------------------------

class _MotionDetector:
    def __init__(self) -> None:
        self._prev = None

    def check(self, gray) -> bool:
        """Return True if motion exceeds MOTION_THRESHOLD vs previous frame."""
        import cv2
        import numpy as np
        if self._prev is None:
            self._prev = gray
            return False
        diff = cv2.absdiff(self._prev, gray)
        self._prev = gray
        changed = np.count_nonzero(diff > 25)
        total = gray.size
        return (changed / total) > MOTION_THRESHOLD


# ---------------------------------------------------------------------------
# Event builder helpers
# ---------------------------------------------------------------------------

def _uid() -> str:
    return str(uuid.uuid4())[:8]


def _make_event(
    event_type: str,
    timestamp_secs: float,
    frame_idx: int,
    description: str,
    label: str,
    track_id: str | None = None,
    confidence: float = 1.0,
    thumbnail: str | None = None,
    extra: dict | None = None,
) -> dict:
    ev = {
        "id":              _uid(),
        "type":            event_type,
        "timestamp_secs":  round(timestamp_secs, 2),
        "frame_index":     frame_idx,
        "description":     description,
        "label":           label,
        "track_id":        track_id,
        "confidence":      round(confidence, 3),
        "thumbnail_url":   thumbnail,
    }
    if extra:
        ev.update(extra)
    return ev


# ---------------------------------------------------------------------------
# Main analysis function (runs in background thread)
# ---------------------------------------------------------------------------

def _analyse(video_id: str, video_path: str, vs: Any) -> None:
    """
    Full analysis pipeline. Called in a daemon thread.
    vs = VideoStore instance (passed to avoid circular import at module load).
    """
    import cv2
    import numpy as np

    vs.update_video(video_id, status="analyzing", progress=0)

    try:
        yolo_model = None
        yolo_ok = False
        try:
            from ultralytics import YOLO
            yolo_model = YOLO("yolov8n.pt")  # downloads ~6 MB on first run
            yolo_ok = True
            logger.info("video[%s]: YOLO nano loaded", video_id)
        except Exception as exc:
            logger.warning("video[%s]: YOLO unavailable (%s) — motion-only mode", video_id, exc)

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            vs.update_video(video_id, status="error", error="Cannot open video file")
            return

        native_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
        width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        duration_secs = (total_frames / native_fps) if native_fps > 0 else 0

        step = max(1, int(native_fps / SAMPLE_FPS))  # read every N-th frame

        vs.update_video(
            video_id,
            duration_secs=round(duration_secs, 1),
            fps=round(native_fps, 2),
            resolution=f"{width}x{height}",
            frame_count=total_frames,
        )

        tracker = _SimpleTracker()
        motion_det = _MotionDetector()
        events: list[dict] = []
        flush_count = 0

        from app.services.prediction_service import PredictionTracker
        pred_tracker = PredictionTracker()

        # Track which object classes have been seen (for summary)
        seen_labels: set[str] = set()
        # Track IDs that have triggered appeared/left events
        appeared_ids: set[str] = set()
        last_person_count = 0
        crowd_active = False
        thumbnail_saved = False

        frame_idx = 0
        sampled = 0

        while sampled < MAX_FRAMES:
            ret, frame = cap.read()
            if not ret:
                break
            frame_idx += 1

            if (frame_idx - 1) % step != 0:
                continue

            sampled += 1
            ts = (frame_idx - 1) / native_fps

            # Progress update every 100 sampled frames
            if sampled % 100 == 0 and total_frames > 0:
                pct = min(99, int((frame_idx / total_frames) * 100))
                vs.update_video(video_id, progress=pct)

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            has_motion = motion_det.check(gray)

            if has_motion:
                events.append(_make_event(
                    "motion_detected", ts, frame_idx,
                    "Motion detected in frame",
                    "motion",
                    confidence=0.80,
                ))

            detections: list[dict] = []

            if yolo_ok and yolo_model is not None:
                try:
                    results = yolo_model(
                        frame,
                        classes=CCTV_CLASSES,
                        conf=CONF_THRESHOLD,
                        verbose=False,
                    )
                    for r in results:
                        if r.boxes is None:
                            continue
                        for box in r.boxes:
                            cls_id = int(box.cls[0])
                            conf   = float(box.conf[0])
                            # Normalise box to 0-1
                            x1, y1, x2, y2 = box.xyxyn[0].tolist()
                            detections.append({
                                "cls_id": cls_id,
                                "box":    [x1, y1, x2, y2],
                                "conf":   conf,
                            })
                except Exception as exc:
                    logger.debug("video[%s]: YOLO frame error: %s", video_id, exc)

            matched, new_tracks = tracker.update(detections, sampled)
            pred_tracker.evict_stale(sampled)

            # — prediction events from tracked objects
            for det in matched + new_tracks:
                try:
                    x1, y1, x2, y2 = det["box"]
                    cx = (x1 + x2) / 2
                    cy = (y1 + y2) / 2
                    area = (x2 - x1) * (y2 - y1)
                    lbl = COCO_NAMES.get(det["cls_id"], "object")
                    pred = pred_tracker.update(
                        det["track_id"], det["cls_id"], lbl,
                        cx, cy, area, sampled, ts,
                    )
                    if pred and pred.get("prediction_events"):
                        for pevt in pred["prediction_events"]:
                            events.append(_make_event(
                                pevt, ts, frame_idx,
                                f"Prediction: {pevt.replace('_', ' ')} — {lbl} moving {pred['direction']}",
                                lbl,
                                track_id=det["track_id"],
                                confidence=pred["confidence"],
                                extra={
                                    "prediction_type":    pevt,
                                    "direction":          pred["direction"],
                                    "speed":              pred["speed"],
                                    "area_trend":         pred["area_trend"],
                                    "current_position":   {"x": pred["current_x"], "y": pred["current_y"]},
                                    "predicted_position": {"x": pred["predicted_x"], "y": pred["predicted_y"]},
                                },
                            ))
                except Exception as pred_exc:
                    logger.debug("video pred_tracker error: %s", pred_exc)

            # — person appeared events
            for det in new_tracks:
                if det["cls_id"] == 0:  # person
                    tid = det["track_id"]
                    if tid not in appeared_ids:
                        appeared_ids.add(tid)
                        thumb = None
                        if not thumbnail_saved:
                            thumb = _save_thumbnail(frame, video_id, det["track_id"])
                            if thumb:
                                thumbnail_saved = True
                                vs.update_video(video_id, thumbnail_path=thumb)
                        events.append(_make_event(
                            "person_appeared", ts, frame_idx,
                            f"Person {tid} entered the frame",
                            "person",
                            track_id=tid,
                            confidence=det["conf"],
                            thumbnail=thumb,
                        ))
                        seen_labels.add("person")
                elif det["cls_id"] in (2, 3, 5, 7):  # vehicles
                    label = COCO_NAMES.get(det["cls_id"], "vehicle")
                    events.append(_make_event(
                        "vehicle_appeared", ts, frame_idx,
                        f"{label.capitalize()} entered the frame",
                        label,
                        track_id=det["track_id"],
                        confidence=det["conf"],
                    ))
                    seen_labels.add(label)
                elif det["cls_id"] in (24, 25, 26, 28):  # bags
                    label = COCO_NAMES.get(det["cls_id"], "bag")
                    events.append(_make_event(
                        "bag_detected", ts, frame_idx,
                        f"{label.capitalize()} detected",
                        label,
                        track_id=det["track_id"],
                        confidence=det["conf"],
                    ))
                    seen_labels.add(label)
                else:
                    label = COCO_NAMES.get(det["cls_id"], "object")
                    events.append(_make_event(
                        "object_appeared", ts, frame_idx,
                        f"{label.capitalize()} appeared",
                        label,
                        track_id=det["track_id"],
                        confidence=det["conf"],
                    ))
                    seen_labels.add(label)

            # — crowd detection
            person_count = tracker.active_count_by_class(0)
            if person_count >= CROWD_THRESHOLD and not crowd_active:
                crowd_active = True
                thumb = _save_thumbnail(frame, video_id, f"crowd_{_uid()}")
                if thumb and not thumbnail_saved:
                    thumbnail_saved = True
                    vs.update_video(video_id, thumbnail_path=thumb)
                events.append(_make_event(
                    "crowd_detected", ts, frame_idx,
                    f"Crowd detected — {person_count} persons in frame",
                    "crowd",
                    confidence=0.90,
                    thumbnail=thumb,
                    extra={"person_count": person_count},
                ))
                seen_labels.add("crowd")
            elif person_count < CROWD_THRESHOLD:
                crowd_active = False

            last_person_count = person_count

            # Flush events to store in batches
            if len(events) >= EVENT_BATCH:
                vs.append_events(video_id, events)
                flush_count += len(events)
                events = []

        cap.release()

        # Flush remaining events
        if events:
            vs.append_events(video_id, events)
            flush_count += len(events)

        # Build summary
        label_list = sorted(seen_labels)
        if label_list:
            summary = f"Detected: {', '.join(label_list)}."
        else:
            summary = "No objects detected." if yolo_ok else "Motion-only analysis (YOLO not installed)."

        vs.update_video(
            video_id,
            status="done",
            progress=100,
            analyzed_at=_now_iso(),
            labels=label_list,
            summary=summary,
        )
        logger.info("video[%s]: analysis complete — %d events, labels: %s", video_id, flush_count, label_list)

    except Exception as exc:
        logger.exception("video[%s]: analysis crashed: %s", video_id, exc)
        vs.update_video(video_id, status="error", error=str(exc), progress=0)


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def start_analysis(
    video_id: str,
    video_path: str,
    vs: Any,
    on_complete: Any = None,
) -> None:
    """
    Kick off video analysis in a background daemon thread.

    on_complete(results: dict) — optional callback fired when analysis finishes.
    results keys: summary, labels, event_count, analysis_engine, fallback_mode,
                  duration_secs, fps, frame_count, resolution, object_counts
    """
    def _run():
        _analyse(video_id, video_path, vs)
        if on_complete is not None:
            try:
                rec = vs.get_video(video_id)
                if rec:
                    events_raw = vs.get_events(video_id, limit=50)
                    # Build object_counts from event labels
                    from collections import Counter
                    obj_counts = Counter(e.get("label", "") for e in events_raw if e.get("label") != "motion")
                    on_complete({
                        "summary":         rec.get("summary", ""),
                        "labels":          rec.get("labels", []),
                        "event_count":     rec.get("event_count", 0),
                        "analysis_engine": "yolo_nano" if rec.get("labels") else "motion_only",
                        "fallback_mode":   not bool(rec.get("labels")),
                        "duration_secs":   rec.get("duration_secs"),
                        "fps":             rec.get("fps"),
                        "frame_count":     rec.get("frame_count"),
                        "resolution":      rec.get("resolution"),
                        "object_counts":   dict(obj_counts),
                        "event_timeline":  [
                            {
                                "t":    e.get("timestamp_secs"),
                                "type": e.get("type"),
                                "desc": e.get("description"),
                            }
                            for e in events_raw[:20]
                        ],
                    })
            except Exception as exc:
                logger.debug("video on_complete callback failed: %s", exc)

    t = threading.Thread(
        target=_run,
        name=f"video-analysis-{video_id}",
        daemon=True,
    )
    t.start()
    logger.info("video[%s]: analysis thread started", video_id)
