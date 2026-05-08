"""Cow posture classification — Roboflow hosted inference + aspect-ratio fallback.

The pipeline classifies each tracked cow's bounding box as STANDING or DOWN.
Two implementations are available:

- AspectRatioClassifier — lightweight heuristic, no network calls. Good for
  default/offline use and as a fallback when Roboflow is unavailable.

- RoboflowClassifier — uses the hosted "cow-posture-detection/3" model on
  Roboflow Universe. Calls the API once every N frames for the full frame,
  caches predictions, and matches each YOLO-tracked box to a Roboflow box by
  highest IoU. Falls back to aspect ratio if a call fails or no Roboflow box
  overlaps the YOLO box well enough to be a confident match.
"""

import base64
import os
import time

import cv2
import requests

DOWN = "DOWN"
STANDING = "STANDING"


def _iou(a, b) -> float:
    """Intersection over Union for two boxes in xyxy pixel format."""
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
    intersection = iw * ih
    area_a = (ax2 - ax1) * (ay2 - ay1)
    area_b = (bx2 - bx1) * (by2 - by1)
    union = area_a + area_b - intersection
    return intersection / union if union > 0 else 0.0


class AspectRatioClassifier:
    """Standing cows are roughly portrait (h > w); lying cows are roughly
    landscape (w > h, ratio ~2.0+). Threshold 1.8 chosen to avoid classifying
    standing cows seen at slight angles (which can produce ratios near 1.4)
    as DOWN.
    """

    DOWN_RATIO_THRESHOLD = 1.8

    def update_frame(self, frame) -> bool:
        return False  # stateless

    def classify(self, xyxy) -> str:
        x1, y1, x2, y2 = xyxy
        w = x2 - x1
        h = y2 - y1
        if h <= 0:
            return STANDING
        return DOWN if (w / h) > self.DOWN_RATIO_THRESHOLD else STANDING


class RoboflowClassifier:
    """Calls Roboflow's hosted cow-posture-detection model on every Nth frame.

    Each call gets back a list of cow detections labeled "standing_cow" or
    "lying_cow". We cache them and, for every YOLO-tracked box, find the
    Roboflow detection with the highest IoU and return its posture label.

    Why we don't call per-cow: latency. Per-frame full-image inference is
    ~150-300ms; per-cow would multiply that by the number of cows on screen.

    Why every Nth frame and not every frame: cows don't change posture
    multiple times per second, so calling more often than ~5/sec wastes API
    quota and slows playback for no gain.
    """

    URL_TEMPLATE = "https://serverless.roboflow.com/{model_id}"
    MODEL_ID = "cow-posture-detection/2"
    DOWN_LABEL = "lying_cow"
    IOU_MATCH_THRESHOLD = 0.3  # below this, treat as no Roboflow match

    def __init__(self, api_key: str, every_n_frames: int = 5):
        self._api_key = api_key
        self._every_n = max(1, every_n_frames)
        self._frame_idx = -1
        self._cache: list[tuple[tuple[float, float, float, float], str]] = []
        self._fallback = AspectRatioClassifier()

    def update_frame(self, frame) -> bool:
        """Call once per frame, before any classify() calls.

        Returns True if Roboflow was queried this frame, False if we used
        the cache from a recent call.
        """
        self._frame_idx += 1
        if self._frame_idx % self._every_n != 0:
            return False

        try:
            ok, buf = cv2.imencode(".jpg", frame)
            if not ok:
                return False
            img_b64 = base64.b64encode(buf).decode("ascii")

            t0 = time.time()
            resp = requests.post(
                self.URL_TEMPLATE.format(model_id=self.MODEL_ID),
                params={"api_key": self._api_key},
                data=img_b64,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=5,
            )
            resp.raise_for_status()
            data = resp.json()

            self._cache = [
                (self._pred_to_xyxy(p), p.get("class", ""))
                for p in data.get("predictions", [])
            ]
            elapsed_ms = (time.time() - t0) * 1000
            print(f"  Roboflow: {len(self._cache)} predictions in {elapsed_ms:.0f}ms")
            return True

        except Exception as e:
            print(f"  Roboflow inference failed (frame {self._frame_idx}): {e}")
            return False

    def classify(self, xyxy) -> str:
        if not self._cache:
            return self._fallback.classify(xyxy)

        best_iou = 0.0
        best_class = ""
        for rf_box, rf_class in self._cache:
            score = _iou(xyxy, rf_box)
            if score > best_iou:
                best_iou = score
                best_class = rf_class

        if best_iou < self.IOU_MATCH_THRESHOLD:
            return self._fallback.classify(xyxy)

        return DOWN if best_class == self.DOWN_LABEL else STANDING

    @staticmethod
    def _pred_to_xyxy(pred: dict) -> tuple[float, float, float, float]:
        # Roboflow returns center-based coords (x, y = center; width, height = full dims).
        cx = pred["x"]
        cy = pred["y"]
        w = pred["width"]
        h = pred["height"]
        return (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)


def make_classifier(every_n_frames: int = 5):
    """Returns a RoboflowClassifier if ROBOFLOW_API_KEY is set, else AspectRatioClassifier."""
    api_key = os.environ.get("ROBOFLOW_API_KEY")
    if api_key:
        print(f"Using Roboflow cow-posture-detection (1 inference per {every_n_frames} frames)")
        return RoboflowClassifier(api_key, every_n_frames)
    print("ROBOFLOW_API_KEY not set — using aspect ratio heuristic")
    return AspectRatioClassifier()
