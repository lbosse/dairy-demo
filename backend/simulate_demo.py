"""
Demo simulation — run this to test the backend + push notifications
without a video file.

Simulates 3 cows: #1 and #3 go down, #2 stays standing.
Cow #1 exceeds the alert threshold; #3 stands back up in time.

Usage:
    python3 simulate_demo.py [--backend http://localhost:5000] [--threshold 30]
"""

import time
import argparse
import requests

def post(backend: str, cow_id: int, posture: str, down_sec: float):
    r = requests.post(f"{backend}/cow-state", json={
        "cow_id": cow_id,
        "posture": posture,
        "down_duration_sec": down_sec,
    }, timeout=2)
    print(f"  Cow #{cow_id} {posture:10s} {down_sec:5.0f}s → {r.status_code}")

def run(backend: str, threshold_sec: float):
    print(f"\nSetting alert threshold to {threshold_sec}s...")
    requests.put(f"{backend}/threshold", json={"threshold_sec": threshold_sec}, timeout=2)

    print("\nStarting simulation. Watch your phone for a push notification.")
    print("─" * 50)

    start = time.time()
    tick = 0

    while True:
        elapsed = time.time() - start
        tick += 1

        # Cow 2 always standing
        post(backend, 2, "STANDING", 0)

        # Cow 1: goes down at t=5s, stays down past threshold → ALERT
        if elapsed < 5:
            post(backend, 1, "STANDING", 0)
        else:
            post(backend, 1, "DOWN", elapsed - 5)

        # Cow 3: goes down at t=10s, stands back up at t=30s
        if elapsed < 10:
            post(backend, 3, "STANDING", 0)
        elif elapsed < 30:
            post(backend, 3, "DOWN", elapsed - 10)
        else:
            post(backend, 3, "STANDING", 0)

        if elapsed > threshold_sec + 20:
            print("\nSimulation complete. Check your phone — Cow #1 should have triggered an alert.")
            break

        time.sleep(2)

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--backend", default="http://localhost:5000")
    p.add_argument("--threshold", type=float, default=30.0,
                   help="Alert threshold in seconds (default: 30 for demo)")
    args = p.parse_args()
    run(args.backend, args.threshold)
