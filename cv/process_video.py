"""
Cow detection and down-cow alerting — video processor.

Usage:
    python process_video.py <input_video> <output_video> [--backend http://localhost:5000]

Detects cows using YOLOv8 (COCO class 19) with ByteTrack ID persistence.
Classifies each tracked cow as STANDING or DOWN via bounding-box aspect ratio.
Posts state updates to the Flask backend for alert threshold monitoring.
"""

import argparse
import time

import cv2
import requests
import torch
from ultralytics import YOLO

from cow_tracker import CowTracker

COCO_COW_CLASS = 19
COLOR_STANDING = (34, 197, 94)   # green
COLOR_DOWN = (239, 68, 68)        # red
COLOR_DOWN_ALERTED = (234, 179, 8)  # amber — already alerted, still down


def classify_posture(xyxy) -> str:
    """Aspect-ratio heuristic: lying cows have wider-than-tall bounding boxes.

    A standing cow is roughly portrait (h > w).
    A lying cow is roughly landscape (w > h), typically ratio > 1.4.
    Swap this function for a Roboflow model call when one is trained on farm data.
    """
    x1, y1, x2, y2 = xyxy
    w = x2 - x1
    h = y2 - y1
    if h <= 0:
        return "STANDING"
    return "DOWN" if (w / h) > 1.4 else "STANDING"


def draw_annotation(frame, box, track_id: int, posture: str, down_sec: float, alerted: bool):
    x1, y1, x2, y2 = (int(v) for v in box)

    if posture == "DOWN":
        color = COLOR_DOWN_ALERTED if alerted else COLOR_DOWN
    else:
        color = COLOR_STANDING

    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

    label = f"Cow #{track_id}  {posture}"
    if posture == "DOWN" and down_sec > 0:
        m, s = divmod(int(down_sec), 60)
        label += f"  {m:02d}:{s:02d}"
        if alerted:
            label += "  ALERT SENT"

    (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
    cv2.rectangle(frame, (x1, y1 - th - 10), (x1 + tw + 6, y1), color, -1)
    cv2.putText(frame, label, (x1 + 3, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)


def post_cow_state(backend_url: str, cow_id: int, posture: str, down_sec: float):
    try:
        requests.post(
            f"{backend_url}/cow-state",
            json={"cow_id": cow_id, "posture": posture, "down_duration_sec": down_sec},
            timeout=0.15,
        )
    except Exception:
        pass  # never block video processing on network latency


def process_video(input_path: str, output_path: str, backend_url: str):
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    print(f"Using device: {device}")

    model = YOLO("yolov8n.pt")
    model.to(device)

    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open: {input_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    tracker = CowTracker()
    frame_num = 0

    print(f"Processing {total} frames ({width}x{height} @ {fps:.1f}fps)...")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        now = time.time()

        results = model.track(
            frame,
            persist=True,
            classes=[COCO_COW_CLASS],
            tracker="bytetrack.yaml",
            verbose=False,
        )

        boxes_result = results[0].boxes
        if boxes_result is not None and boxes_result.id is not None:
            xyxys = boxes_result.xyxy.cpu().numpy()
            ids = boxes_result.id.cpu().numpy().astype(int)

            for xyxy, track_id in zip(xyxys, ids):
                raw_posture = classify_posture(xyxy)
                down_sec = tracker.update(int(track_id), raw_posture, now)
                alerted = tracker.was_alerted(int(track_id))

                post_cow_state(backend_url, int(track_id), tracker._states[int(track_id)].posture, down_sec)

                # mark alerted locally after posting (backend drives the actual alert)
                if down_sec > 0:
                    tracker.mark_alerted(int(track_id))  # backend handles de-dupe; this just colors the box

                draw_annotation(frame, xyxy, int(track_id), tracker._states[int(track_id)].posture, down_sec, alerted)

        out.write(frame)
        frame_num += 1

        if frame_num % 60 == 0:
            pct = (frame_num / total * 100) if total > 0 else 0
            print(f"  {frame_num}/{total} frames ({pct:.0f}%)")

    cap.release()
    out.release()
    print(f"\nDone. Output: {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cow detection + down-cow alerting")
    parser.add_argument("input", help="Input video file path")
    parser.add_argument("output", help="Output annotated video path")
    parser.add_argument("--backend", default="http://localhost:5000", help="Flask backend URL")
    args = parser.parse_args()

    process_video(args.input, args.output, args.backend)
