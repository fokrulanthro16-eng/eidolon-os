"""
Prediction Service — lightweight object trajectory prediction.

No cloud, no heavy model. Uses linear velocity extrapolation from position history.

Algorithm:
1. Maintain a deque of (frame_idx, timestamp, cx, cy, area) per tracked object.
2. Compute vx = (last.cx - first.cx) / dt, vy = similar.
3. Classify direction from angle; use area trend for approaching/leaving.
4. Predict next position PREDICT_HORIZON_SECS ahead.
5. Emit named prediction events based on thresholds.
6. Confidence = min(0.45 + 0.08 * n_points, 0.88) — grows with history.
"""

import math
from collections import deque
from typing import Optional

MAX_HISTORY = 8
STATIONARY_SPEED = 0.018   # normalised units/s — below this = stationary
APPROACH_DELTA = 0.12      # relative bbox area growth ratio to call "approaching"
EDGE_MARGIN = 0.08         # 8 % from edge = entering/leaving boundary
STATIONARY_SECS = 6.0      # seconds standing still = stationary_too_long event
EVICT_AFTER_FRAMES = 12    # frames of silence before evicting a track
PREDICT_HORIZON_SECS = 1.5


class _Pt:
    __slots__ = ("frame_idx", "ts", "cx", "cy", "area")

    def __init__(self, frame_idx: int, ts: float, cx: float, cy: float, area: float) -> None:
        self.frame_idx = frame_idx
        self.ts = ts
        self.cx = cx
        self.cy = cy
        self.area = area


class TrackHistory:
    def __init__(self, track_id: str, cls_id: int, label: str) -> None:
        self.track_id = track_id
        self.cls_id = cls_id
        self.label = label
        self._pts: deque[_Pt] = deque(maxlen=MAX_HISTORY)
        self.last_frame_idx: int = 0

    def push(self, frame_idx: int, ts: float, cx: float, cy: float, area: float) -> None:
        self._pts.append(_Pt(frame_idx, ts, cx, cy, area))
        self.last_frame_idx = frame_idx

    def predict(self) -> Optional[dict]:
        """Return prediction dict, or None if insufficient history (< 2 points)."""
        pts = list(self._pts)
        if len(pts) < 2:
            return None

        first, last = pts[0], pts[-1]
        dt = last.ts - first.ts
        if dt <= 0:
            return None

        vx = (last.cx - first.cx) / dt
        vy = (last.cy - first.cy) / dt
        speed = math.hypot(vx, vy)

        area_ratio = (last.area - first.area) / max(first.area, 1e-6)
        if area_ratio > APPROACH_DELTA:
            area_trend = "growing"
        elif area_ratio < -APPROACH_DELTA:
            area_trend = "shrinking"
        else:
            area_trend = "stable"

        # Direction classification — screen y is top-down so flip vy for atan2
        if speed < STATIONARY_SPEED:
            direction = "stationary"
        elif area_trend == "growing":
            direction = "approaching"
        elif area_trend == "shrinking":
            direction = "leaving"
        else:
            angle = math.degrees(math.atan2(-vy, vx))
            if -45 <= angle < 45:
                direction = "right"
            elif 45 <= angle < 135:
                direction = "up"
            elif -135 <= angle < -45:
                direction = "down"
            else:
                direction = "left"

        pred_cx = max(0.0, min(1.0, last.cx + vx * PREDICT_HORIZON_SECS))
        pred_cy = max(0.0, min(1.0, last.cy + vy * PREDICT_HORIZON_SECS))

        stationary_secs = (last.ts - first.ts) if direction == "stationary" else 0.0

        prediction_events: list[str] = []

        if self.cls_id == 0:  # person
            if direction == "approaching":
                prediction_events.append("person_moving_toward_camera")
            elif direction == "leaving" or (
                pred_cy < EDGE_MARGIN
                or pred_cx < EDGE_MARGIN
                or pred_cx > 1 - EDGE_MARGIN
                or pred_cy > 1 - EDGE_MARGIN
            ):
                prediction_events.append("person_leaving_scene")

        if self.cls_id in (2, 3, 5, 7):  # vehicles
            near_edge = (
                last.cx < EDGE_MARGIN
                or last.cx > 1 - EDGE_MARGIN
                or last.cy < EDGE_MARGIN
                or last.cy > 1 - EDGE_MARGIN
            )
            if near_edge and direction not in ("stationary",):
                prediction_events.append("vehicle_entering_area")

        if direction == "stationary" and stationary_secs >= STATIONARY_SECS:
            prediction_events.append("object_stationary_too_long")

        if direction in ("left", "right") and speed > STATIONARY_SPEED * 2:
            prediction_events.append("possible_crossing_motion")

        confidence = min(0.45 + 0.08 * len(pts), 0.88)

        return {
            "track_id":          self.track_id,
            "label":             self.label,
            "cls_id":            self.cls_id,
            "direction":         direction,
            "speed":             round(speed, 4),
            "area_trend":        area_trend,
            "current_x":         round(last.cx, 4),
            "current_y":         round(last.cy, 4),
            "predicted_x":       round(pred_cx, 4),
            "predicted_y":       round(pred_cy, 4),
            "prediction_events": prediction_events,
            "confidence":        round(confidence, 3),
            "stationary_secs":   round(stationary_secs, 1),
        }


class PredictionTracker:
    """
    Manages TrackHistory objects for multiple tracked objects.
    Not thread-safe on its own — callers must hold a lock if used from multiple threads.
    For the live camera, use the module-level camera_tracker (guarded by camera_service._LOCK).
    """

    def __init__(self) -> None:
        self._tracks: dict[str, TrackHistory] = {}

    def update(
        self,
        track_id: str,
        cls_id: int,
        label: str,
        cx: float,
        cy: float,
        area: float,
        frame_idx: int,
        timestamp: float,
    ) -> Optional[dict]:
        """Record an observation and return the current prediction (or None if too few points)."""
        if track_id not in self._tracks:
            self._tracks[track_id] = TrackHistory(track_id, cls_id, label)
        th = self._tracks[track_id]
        th.push(frame_idx, timestamp, cx, cy, area)
        return th.predict()

    def get_active(self) -> list[dict]:
        """Return predictions for all tracks that have at least 2 data points."""
        result = []
        for th in self._tracks.values():
            pred = th.predict()
            if pred is not None:
                result.append(pred)
        return result

    def evict_stale(self, current_frame: int) -> None:
        """Remove tracks that haven't been seen for EVICT_AFTER_FRAMES frames."""
        stale = [
            tid for tid, th in self._tracks.items()
            if (current_frame - th.last_frame_idx) > EVICT_AFTER_FRAMES
        ]
        for tid in stale:
            del self._tracks[tid]

    def reset(self) -> None:
        self._tracks.clear()


# Shared singleton used by the live camera worker.
# Access is serialised via camera_service._LOCK.
camera_tracker = PredictionTracker()
