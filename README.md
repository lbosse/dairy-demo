# Dairy Demo — Down Cow Detection

Detects cows in a video file, identifies "down cows" (laying), draws bounding boxes on output video, and sends push notifications to an Android phone when a cow has been down past a configurable threshold.

**Stack:** Python + YOLOv8 + OpenCV · Flask · AWS SNS → Firebase FCM · React Native (Expo)

---

## Project Structure

```
dairy-demo/
├── cv/                   Python CV pipeline (video in → annotated video out)
├── backend/              Flask alert server (receives CV updates, fires SNS push)
├── infra/                Terraform — provisions Firebase, SNS, and IAM
└── mobile/               Expo React Native Android app (alerts + threshold slider)
```

---

## Prerequisites

- Python 3.10+
- Node.js 20+ — `brew install node`
- Terraform — `brew install terraform`
- An [Expo account](https://expo.dev) (free) — needed for EAS Build
- A GCP project with billing enabled
- AWS credentials configured locally (`aws configure` or a named profile)

---

## One-Time Setup

### 1. Python dependencies

Set up a virtual environment (one time) and install the dependencies into it:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r cv/requirements.txt
pip install -r backend/requirements.txt
```

Activate the venv (`source .venv/bin/activate`) in any new terminal before running Python scripts.

### 2. Infrastructure (Terraform)

Terraform provisions the Firebase project, registers the Android app, writes `mobile/google-services.json`, creates a least-privilege AWS IAM user, and sets up the SNS Platform Application.

**Step 1 — Firebase + IAM + google-services.json**

```bash
cd infra
cp terraform.tfvars.example terraform.tfvars
```

Fill in your GCP project ID in `terraform.tfvars`, then:

```bash
terraform init
terraform apply
```

This writes `mobile/google-services.json` automatically.

**Step 2 — SNS Platform Application**

AWS SNS uses FCM HTTP v1 (token-based auth) which requires a Firebase service account private key, not the legacy Server key.

After step 1 completes:

1. Go to [Firebase console](https://console.firebase.google.com) → **Project Settings → Service accounts** tab
2. Click **Generate new private key** → download the JSON file
3. Save it **outside the repo** — it's a secret credential
4. Add the path to `terraform.tfvars`:
   ```
   fcm_service_account_json_path = "/path/to/service-account.json"
   ```
5. Run `terraform apply` again

### 3. Backend environment variables

Export the outputs from Terraform:

```bash
cd infra
export SNS_PLATFORM_APP_ARN=$(terraform output -raw sns_platform_application_arn)
export AWS_ACCESS_KEY_ID=$(terraform output -raw iam_access_key_id)
export AWS_SECRET_ACCESS_KEY=$(terraform output -raw iam_secret_access_key)
export AWS_REGION="us-east-1"
```

### 4. Mobile app — update backend URL

Edit `mobile/constants/Config.ts` and replace the IP with your Mac's local IP:

```bash
ipconfig getifaddr en0   # e.g. 192.168.1.47
```

```ts
export const BACKEND_URL = "http://192.168.1.47:5000";
```

Your Mac and the Android phone must be on the same network.

### 5. Mobile app — Node dependencies

```bash
cd mobile
npm install
```

---

## Getting the App onto the Android Phone

There are two paths. **Use EAS Build for the actual demo** — Expo Go won't deliver push notifications.

### Option A: EAS Build (required for push notifications)

This builds a real APK on Expo's cloud servers (~10 min). Use this for the demo.

```bash
cd mobile
npx eas login           # log in to your Expo account
npx eas build:configure # first time only — initializes eas.json
npx eas build --platform android --profile preview
```

When the build finishes, EAS prints a download URL (also visible at [expo.dev/builds](https://expo.dev/builds)).

**Install on the phone:**

1. On the Android phone: **Settings → Security → Install unknown apps** → allow **Chrome** (or Files)
2. Open the EAS download URL in Chrome on the phone → download → tap to install
3. Alternatively: download the APK to your Mac, transfer via USB or Google Drive, open and install

### Option B: Expo Go (UI only — no push notifications)

Use this to iterate on the UI quickly without waiting for a build. Push notifications will not fire.

```bash
cd mobile
npx expo start
```

Install **Expo Go** from the Play Store on the Android phone. Scan the QR code shown in the terminal.

---

## Running the Demo

### Start the backend

```bash
cd backend
python3 main.py
```

Flask starts on port 5000. Keep this terminal open.

### Test with the simulator (no video needed)

Run this to verify the backend, SNS, and phone notifications work end-to-end before you have a video:

```bash
cd backend
python3 simulate_demo.py --threshold 30
```

This simulates 3 cows over ~50 seconds. Cow #1 goes down and stays down past 30 seconds → push notification fires on the phone. Watch the app dashboard update in real time.

### Process a real video

```bash
cd cv
python3 process_video.py input.mp4 output_annotated.mp4
```

A preview window opens and plays the annotated video at the source framerate as frames are processed. Press `q` in the window to stop early. Each frame is also written to `output_annotated.mp4`.

While processing, the script POSTs state updates to the Flask backend. When any cow exceeds the threshold, a push notification fires.

**Flags:**

| Flag | Effect |
|---|---|
| `--backend URL` | Flask backend URL (default `http://localhost:5000`) |
| `--fast` | Process as fast as inference allows; skip real-time pacing |
| `--no-preview` | Disable the live preview window (write-only mode) |

---

## Down-Cow Detection — Two Modes

The classifier lives in `cv/posture_classifier.py` and is selected by env var:

### Roboflow hosted inference (recommended)

Uses the [cow-posture-detection](https://universe.roboflow.com/cow-posture-detection/cow-posture-detection) model on Roboflow Universe (`cow-posture-detection/3`). Classes: `lying_cow`, `standing_cow`.

Setup:

```bash
export ROBOFLOW_API_KEY="your-private-api-key"
```

Get the key from your Roboflow account settings (free tier works). With the env var set, the CV script automatically uses Roboflow — full-frame inference every 5 frames, with results cached for the in-between frames. Each YOLO-tracked cow box is matched to a Roboflow prediction by highest IoU overlap.

Tune the cadence with `--roboflow-every N` if needed (lower N = more API calls, higher latency, more responsive posture classification).

### Aspect ratio heuristic (fallback)

If `ROBOFLOW_API_KEY` is not set, the script falls back to a simple bounding-box shape heuristic: lying cows' boxes are wider than tall (ratio > 1.4); standing cows are taller than wide. No network calls. Works well for standard barn camera angles.

The Roboflow classifier also falls back to this heuristic if a network call fails or no Roboflow box overlaps a YOLO box well enough — so the pipeline never crashes on a transient API issue.
