"""
Dairy demo — Flask alert backend.

Endpoints:
    POST /cow-state          CV script reports per-cow posture + down duration
    GET  /states             Mobile app polls for current cow states
    PUT  /threshold          Mobile app sets alert threshold (seconds)
    GET  /threshold          Get current threshold
    POST /register-device    Mobile app registers FCM token for push alerts
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from alert_service import register_device, send_alert

app = Flask(__name__)
CORS(app)

# ── state ──────────────────────────────────────────────────────────────────────
cow_states: dict[int, dict] = {}
alert_threshold_sec: float = 300.0  # mobile app controls this


# ── routes ─────────────────────────────────────────────────────────────────────

@app.route("/cow-state", methods=["POST"])
def update_cow_state():
    global cow_states, alert_threshold_sec
    data = request.get_json(force=True)
    cow_id: int = int(data["cow_id"])
    posture: str = data["posture"]
    down_sec: float = float(data.get("down_duration_sec", 0))

    prev = cow_states.get(cow_id, {"alerted": False})
    alerted = prev["alerted"]

    if posture == "STANDING":
        alerted = False  # reset so next down event re-alerts

    if posture == "DOWN" and down_sec >= alert_threshold_sec and not alerted:
        send_alert(cow_id, down_sec / 60)
        alerted = True

    cow_states[cow_id] = {
        "posture": posture,
        "down_duration_sec": round(down_sec, 1),
        "alerted": alerted,
    }

    return jsonify({"ok": True})


@app.route("/states", methods=["GET"])
def get_states():
    return jsonify(cow_states)


@app.route("/threshold", methods=["GET"])
def get_threshold():
    return jsonify({"threshold_sec": alert_threshold_sec})


@app.route("/threshold", methods=["PUT"])
def set_threshold():
    global alert_threshold_sec
    data = request.get_json(force=True)
    alert_threshold_sec = max(10.0, float(data["threshold_sec"]))
    print(f"Alert threshold set to {alert_threshold_sec}s")
    return jsonify({"threshold_sec": alert_threshold_sec})


@app.route("/register-device", methods=["POST"])
def register_device_route():
    data = request.get_json(force=True)
    token: str = data.get("token", "")
    if not token:
        return jsonify({"error": "token required"}), 400
    arn = register_device(token)
    return jsonify({"ok": True, "arn": arn})


if __name__ == "__main__":
    print("Starting dairy-demo backend on :5000")
    app.run(debug=True, port=5000, use_reloader=False)
