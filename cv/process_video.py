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
from collections import deque

import cv2
import requests
import torch
from ultralytics import YOLO

from cow_tracker import CowTracker
from posture_classifier import make_classifier

COCO_COW_CLASS = 19
COLOR_STANDING = (34, 197, 94)   # green
COLOR_DOWN = (239, 68, 68)        # red
COLOR_DOWN_ALERTED = (234, 179, 8)  # amber — already alerted, still down


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
    """POST cow state to the backend; return the alerted state, or None if unreachable.

    The backend owns the real threshold and dedup logic — it's the source of truth
    for whether a push notification has fired. Returning None lets the caller fall
    back to a local threshold check so the visual preview still works when the
    backend isn't running (e.g., for CV-only iteration).
    """
    try:
        resp = requests.post(
            f"{backend_url}/cow-state",
            json={"cow_id": cow_id, "posture": posture, "down_duration_sec": down_sec},
            timeout=0.15,
        )
        return bool(resp.json().get("alerted", False))
    except Exception:
        return None


def process_video(input_path: str, output_path: str, backend_url: str, fast: bool = False, preview: bool = True, roboflow_every: int = 5, yolo_model: str = "yolov8s.pt", nms_iou: float = 0.45, imgsz: int = 1536, fp16: bool = True, frame_skip: int = 2, local_threshold: float = 30.0):
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    print(f"Using device: {device}, YOLO model: {yolo_model}, imgsz: {imgsz}, NMS IoU: {nms_iou}, FP16: {fp16}, frame skip: {frame_skip}")

    model = YOLO(yolo_model)
    model.to(device)

    # Posture classifier: Roboflow if ROBOFLOW_API_KEY is in env, else aspect-ratio heuristic.
    classifier = make_classifier(every_n_frames=roboflow_every)

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

    # Frame-skipping: run YOLO every Nth frame, reuse last detections in between.
    # Cows in dairy footage are mostly stationary, so stale boxes are visually fine
    # and YOLO calls per second drop by 1/frame_skip.
    cached_detections: tuple | None = None  # (xyxys ndarray, ids ndarray) or None

    # Rolling timing windows for FPS / per-stage breakdown over the last 30 frames.
    frame_times: deque[float] = deque(maxlen=30)
    yolo_times: deque[float] = deque(maxlen=30)
    pipeline_start = time.time()

    # Real-time pacing matches source FPS so the demo plays at natural speed.
    # --fast pumps the GUI at 1ms (process as quickly as inference allows).
    wait_ms = 1 if fast else max(1, int(1000 / fps))

    if preview:
        cv2.namedWindow("Dairy Monitor — Down Cow Detection", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("Dairy Monitor — Down Cow Detection", min(width, 1280), min(height, 720))

    mode = "fast" if fast else "real-time"
    print(f"Processing {total} frames ({width}x{height} @ {fps:.1f}fps, {mode}). Press 'q' in the preview window to stop.")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        loop_start = time.time()
        now = loop_start

        # Update the posture classifier's frame cache. For Roboflow, this sends
        # the full frame to the hosted API (every Nth frame). For the aspect
        # ratio heuristic, this is a no-op.
        classifier.update_frame(frame)

        # Run detection + ByteTrack. ByteTrack assigns each cow a stable track_id
        # that persists across frames, so per-cow down-duration in CowTracker stays
        # pinned to the right cow even as it moves around the frame. Without this,
        # every frame would look like fresh, unrelated detections and we'd never be
        # able to measure how long a specific cow has been down.
        # persist=True maintains ByteTrack's internal state between calls.
        # boxes_result.id may be None on early frames while ByteTrack is still
        # confirming initial detections.
        # Run YOLO on every Nth frame; reuse the previous frame's detections on
        # skipped frames. Cows in dairy footage move slowly, so stale boxes for
        # one frame are visually fine and we cut YOLO calls by 1/frame_skip.
        if frame_num % frame_skip == 0:
            yolo_t0 = time.time()
            results = model.track(
                frame,
                persist=True,
                classes=[COCO_COW_CLASS],
                tracker="bytetrack.yaml",
                iou=nms_iou,    # NMS IoU threshold — lower keeps overlapping cows separate
                imgsz=imgsz,    # input resolution — higher gives YOLO more pixels for occluded/distant cows
                half=fp16,      # half-precision (FP16) inference — ~1.5-2x faster on supported hardware
                verbose=False,
            )
            yolo_times.append(time.time() - yolo_t0)

            # Ultralytics returns a list of Results, one per input image. We process
            # one frame at a time, so always look at results[0]. .boxes holds the
            # detected bounding boxes + their attributes (coords, class, track_id).
            boxes_result = results[0].boxes
            if boxes_result is not None and boxes_result.id is not None:
                # PyTorch keeps tensors on the inference device (MPS on M2). .cpu()
                # copies them back to system memory, .numpy() converts them to a
                # numpy array so we can iterate in plain Python.
                #
                # xyxy is the bounding-box format YOLO returns:
                #   [x_top_left, y_top_left, x_bottom_right, y_bottom_right]
                # i.e. the pixel coordinates of two diagonal corners of the box.
                cached_detections = (
                    boxes_result.xyxy.cpu().numpy(),
                    boxes_result.id.cpu().numpy().astype(int),
                )
            else:
                cached_detections = None

        if cached_detections is not None:
            xyxys, ids = cached_detections

            # One iteration per detected cow (fresh from YOLO or cached from a recent frame).
            for xyxy, track_id in zip(xyxys, ids):
                # Classify this specific cow as STANDING or DOWN. With Roboflow
                # this looks up the cached prediction whose box best matches
                # this YOLO box. With the aspect ratio classifier this just
                # checks the shape of the box.
                raw_posture = classifier.classify(xyxy)

                # CowTracker smooths the per-frame classification across multiple
                # frames (so a single bad detection doesn't toggle state) and
                # returns how long this cow has been DOWN in seconds. 0 means
                # the cow is standing, or DOWN hasn't been confirmed yet.
                down_sec = tracker.update(int(track_id), raw_posture, now)

                # Report state to Flask. The backend owns the alert threshold
                # logic and decides when to actually fire a push notification —
                # this CV script is just a reporter. The response tells us
                # whether the backend has fired an alert on this cow yet.
                # Returns None if the backend is unreachable, in which case we
                # fall back to a local threshold check so the preview still
                # shows ALERT SENT correctly during standalone CV testing.
                backend_alerted = post_cow_state(backend_url, int(track_id), tracker._states[int(track_id)].posture, down_sec)
                if backend_alerted is None:
                    is_alerted = down_sec >= local_threshold
                else:
                    is_alerted = backend_alerted

                if is_alerted:
                    tracker.mark_alerted(int(track_id))

                # Draw the bounding box + label (cow ID, posture, timer, alert
                # status) onto the frame in place. This is what gets displayed
                # in the preview window and written to the output video.
                draw_annotation(frame, xyxy, int(track_id), tracker._states[int(track_id)].posture, down_sec, is_alerted)

        out.write(frame)
        frame_num += 1

        if preview:
            cv2.imshow("Dairy Monitor — Down Cow Detection", frame)
            if (cv2.waitKey(wait_ms) & 0xFF) == ord("q"):
                print("Stopped by user.")
                break

        # Record total per-frame time AFTER waitKey so it includes the pacing
        # delay in real-time mode. In --fast mode this is pure processing speed.
        frame_times.append(time.time() - loop_start)

        if frame_num % 30 == 0:
            avg_frame = sum(frame_times) / len(frame_times)
            avg_yolo = sum(yolo_times) / len(yolo_times)
            actual_fps = 1.0 / avg_frame if avg_frame > 0 else 0
            pct = (frame_num / total * 100) if total > 0 else 0
            print(
                f"  {frame_num}/{total} frames ({pct:.0f}%) — "
                f"actual {actual_fps:5.1f} FPS / target {fps:.1f} FPS  "
                f"(YOLO {avg_yolo*1000:5.1f}ms, frame {avg_frame*1000:5.1f}ms)"
            )

    cap.release()
    out.release()
    if preview:
        cv2.destroyAllWindows()

    elapsed = time.time() - pipeline_start
    overall_fps = frame_num / elapsed if elapsed > 0 else 0
    print(
        f"\nDone. Output: {output_path}\n"
        f"Processed {frame_num} frames in {elapsed:.1f}s "
        f"= {overall_fps:.1f} FPS overall (source video: {fps:.1f} FPS)"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cow detection + down-cow alerting")
    parser.add_argument("input", help="Input video file path")
    parser.add_argument("output", help="Output annotated video path")
    parser.add_argument("--backend", default="http://localhost:5000", help="Flask backend URL")
    parser.add_argument("--fast", action="store_true", help="Process as fast as possible (skip real-time pacing)")
    parser.add_argument("--no-preview", action="store_true", help="Don't open the live preview window")
    parser.add_argument("--roboflow-every", type=int, default=5, help="Call Roboflow every Nth frame (default 5; ignored if ROBOFLOW_API_KEY is unset)")
    parser.add_argument("--yolo-model", default="yolov8s.pt", help="YOLO weights file (yolov8n/s/m/l/x.pt; bigger = more accurate, slower)")
    parser.add_argument("--nms-iou", type=float, default=0.45, help="YOLO NMS IoU threshold (default 0.45; lower keeps overlapping cows as separate detections)")
    parser.add_argument("--imgsz", type=int, default=1536, help="YOLO input resolution / long side (default 1536; raise to 1920 for native 1080p detail, lower to 1280 or 640 for speed)")
    parser.add_argument("--no-fp16", action="store_true", help="Disable FP16 (half-precision) inference. FP16 is ~1.5-2x faster but slightly less precise.")
    parser.add_argument("--frame-skip", type=int, default=2, help="Run YOLO every Nth frame, reuse detections in between (default 2 = every other frame; 1 = no skip)")
    parser.add_argument("--local-threshold", type=float, default=30.0, help="Visual ALERT SENT threshold in seconds, used when backend is unreachable (default 30)")
    args = parser.parse_args()

    process_video(args.input, args.output, args.backend, fast=args.fast, preview=not args.no_preview, roboflow_every=args.roboflow_every, yolo_model=args.yolo_model, nms_iou=args.nms_iou, imgsz=args.imgsz, fp16=not args.no_fp16, frame_skip=max(1, args.frame_skip), local_threshold=args.local_threshold)
