# Dairy Demo — Down Cow Detection

Detects cows in a video file, identifies "down cows" (laying), draws bounding boxes on output video, and sends push notifications to an Android phone when a cow has been down past a configurable threshold.

**Stack:** Python + YOLOv8 + OpenCV · Flask · AWS SNS → Firebase FCM · React Native (Expo)

---

## Project Structure

```
dairy-demo/
├── cv/                   Python CV pipeline (video in → annotated video out)
├── backend/              Flask alert server (receives CV updates, fires SNS push)
└── mobile/               Expo React Native Android app (alerts + threshold slider)
```

---

## Prerequisites

- Python 3.10+ (currently using 3.9 — works but boto3 has dropped 3.9 support; upgrade when possible)
- Node.js 20+ — install with `brew install node`
- An [Expo account](https://expo.dev) (free) — needed for EAS Build
- An AWS account with SNS access
- A Firebase project (for the FCM server key that SNS uses to deliver to Android)

---

## One-Time Setup

### 1. Python dependencies

```bash
pip install -r cv/requirements.txt
pip install -r backend/requirements.txt
```

### 2. Firebase project (provides the FCM key that Android requires)

1. Go to [console.firebase.google.com](https://console.firebase.google.com) → **Add project**
2. Click the **Android icon** on the project overview
3. Package name: `com.dairydemo.monitor` (must match `app.json` exactly)
4. Click **Register app** → download `google-services.json` → save to `mobile/google-services.json`
5. Go to **Project Settings → Cloud Messaging** → copy the **Server key**

> Firebase is only used here for its FCM delivery credential. The Python backend talks to AWS SNS, not Firebase directly.

### 3. AWS SNS Platform Application

1. Open AWS Console → **SNS** → **Mobile** → **Push notifications** → **Create platform application**
2. Platform: **Firebase Cloud Messaging (FCM)**
3. Paste the Firebase **Server key** from step 2
4. Click **Create** → copy the resulting **Platform Application ARN**

### 4. Backend environment variables

```bash
export SNS_PLATFORM_APP_ARN="arn:aws:sns:us-east-1:123456789:app/GCM/dairy-demo"
export AWS_REGION="us-east-1"
# Your normal AWS credentials must also be set (AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY
# or an IAM role / AWS profile)
```

### 5. Mobile app — update backend URL

Edit `mobile/constants/Config.ts` and replace the IP with your Mac's local IP:

```bash
ipconfig getifaddr en0   # prints your Mac's IP, e.g. 192.168.1.47
```

```ts
export const BACKEND_URL = "http://192.168.1.47:5000";
```

Your Mac and the Android phone must be on the same WiFi network.

### 6. Mobile app — Node dependencies

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

While processing, the script POSTs state updates to the Flask backend. When any cow exceeds the threshold, a push notification fires. When done, `output_annotated.mp4` has bounding boxes and down-timers drawn on every frame.

The backend URL defaults to `http://localhost:5000`. Override with `--backend http://other-ip:5000` if running backend elsewhere.

---

## Demo Flow (Interview)

1. Open the Android app — shows empty dashboard
2. In **Alert Settings**, set threshold to 30 seconds (demo mode)
3. Start `python3 main.py` in one terminal
4. Run `python3 process_video.py cow_video.mp4 output.mp4` in another
5. Watch cow IDs and down-timers appear on the phone dashboard as the video processes
6. When a cow exceeds 30s, the phone gets a push notification
7. After processing, play `output.mp4` to show the annotated video

---

## Adjusting the Down-Cow Detection

The current classifier is in `cv/process_video.py → classify_posture()`. It uses bounding-box aspect ratio: a lying cow's box is wider than tall (ratio > 1.4); a standing cow is taller than wide.

This works well for standard camera angles. To replace it with a trained model, swap the body of `classify_posture()` — the rest of the pipeline is unchanged.

Candidate dataset for fine-tuning: [cow & its posture detection (Roboflow Universe)](https://universe.roboflow.com/fyp-iovvt/cow---its-posture-detection) — 5,872 images with standing/lying labels.
