# Security Audit — Dairy Demo

Findings grouped by when they matter. "Deployment only" means no risk for local dev or pushing to a private/personal repo.

---

## Fix Before `git push`

### 1. No root-level or mobile-level `.gitignore` — BLOCKING

There is only one `.gitignore` in the repo (`infra/.gitignore`), and it only covers files inside `infra/`. Running `git add .` right now would commit:

- **`mobile/node_modules/` (420 MB)** — no gitignore covers it anywhere
- **`mobile/google-services.json`** — Terraform writes this file to `mobile/` after a successful apply. The `*.json` rule in `infra/.gitignore` does not scope outside `infra/`. This file contains your Firebase API key and client credentials.

**Fix:** Add a root `.gitignore` and a `mobile/.gitignore` before your first push.

---

### 2. Real GCP project ID committed in `CONTEXT.md`

`CONTEXT.md:103` contains `dairy-demo-14793` — your actual GCP project ID. `CONTEXT.md` is not gitignored and would be pushed as-is.

This alone is low severity (project IDs are not secrets), but it ties your name and a real cloud resource to a public repo if you ever open-source it.

**Fix:** Replace `dairy-demo-14793` with `<your-gcp-project-id>` in `CONTEXT.md`.

---

## Local Runtime — Low Risk at Home, Higher Risk on Shared WiFi

These are not a concern on your home network, but matter on the interview WiFi where other devices share the subnet.

### 3. Flask `debug=True` — `backend/main.py:84`

```python
app.run(debug=True, port=5000, use_reloader=False)
```

The Werkzeug interactive debugger is served over the network and allows arbitrary Python execution via the browser console. Anyone on the same WiFi who hits `http://<your-mac-ip>:5000` on an error page gets a live Python REPL.

**Risk level:** Low on home network. Real on demo WiFi with other guests.  
**Fix before demo:** Change to `debug=False`.

---

### 4. CORS fully open + all endpoints unauthenticated — `backend/main.py:17`

```python
CORS(app)  # allows all origins
```

All five routes (`/cow-state`, `/states`, `/threshold`, `/register-device`, `/health`) accept any request with no auth. Anyone on the same WiFi can read cow states, change the alert threshold, or register fake devices.

**Risk level:** Low on home network (you're the only one). On interview WiFi, another device could trivially interfere with the demo.  
**Fix before demo:** Restricting CORS is optional for a local demo, but disabling `debug` (above) is the more important one.

---

## Deployment Only — Not a Concern for Local Dev or This Demo

These are real issues for a production system, but have no impact on your local machine or a private git repo.

| Finding | Location | Why it's deployment-only |
|---|---|---|
| HTTP instead of HTTPS | `mobile/constants/Config.ts:4`, `simulate_demo.py:63` | No TLS means cleartext traffic, but only matters on untrusted networks at scale |
| No rate limiting | `backend/main.py` | DoS risk from the internet; irrelevant on a LAN demo |
| `request.get_json(force=True)` + missing field validation | `backend/main.py:29,66,74` | Crash risk from malformed input; only you are sending requests locally |
| In-memory state — no persistence | `backend/main.py:20` | Server restart loses data; fine for a demo |
| `iam_access_key_id` not marked `sensitive` in Terraform | `infra/outputs.tf:1` | Prints key ID in `terraform plan` output; harmless locally, worth fixing before a shared Terraform workflow |
| No request size limits | `backend/main.py` | Memory exhaustion from large payloads; not a local concern |
| Silent exception swallow on backend POST | `cv/process_video.py` | You'll notice the demo isn't working; fine for local use |
| `print`-based logging | `backend/main.py`, `alert_service.py` | No structured logging; irrelevant for a two-terminal demo |
| No certificate pinning in mobile app | `mobile/` | MITM risk on untrusted networks; overkill for a demo APK |

---

## Summary

| Action | When |
|---|---|
| Add root + mobile `.gitignore` | Before `git add .` |
| Replace real GCP project ID in `CONTEXT.md` | Before `git push` |
| Set `debug=False` in `backend/main.py` | Before running on interview WiFi |
| Everything else | Only if this goes to production |
