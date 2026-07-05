# Walkthrough — Running HomeRescue

> **The app is already hosted — try it live:** **https://home-rescue-4234e.web.app/**
>
> **The client ships to mobile.** The Flutter app runs on **web, Windows desktop,
> and mobile (Android / iOS)**, and can be **built into a standalone Android APK
> and installed on a physical phone** — see [Section 5, Deployment](#5-deployment).

This app has **two pieces**:

1. **Backend** — a Python FastAPI server (REST + SSE) that wraps the ADK + Gemini agent and a case store. **Currently deployed on Cloud Run** (Firestore for cases, GCS for media); it can also run locally against SQLite + local files.
2. **Client** — a Flutter app (the committed client surface) that talks to the backend over HTTP.

You can start the client straight away (it targets the hosted backend by default), or run the backend locally first and point the client at it. All paths below are relative to the repo root:

> **Shell note:** commands are shown for **PowerShell** (the default shell on this machine). Where the Bash equivalent differs it is noted inline.

---

## 0. One-time prerequisites

| Tool | Why | Check |
|------|-----|-------|
| Python 3.11–3.13 + the project `.venv` | Backend / agent / tests | `.venv\Scripts\python.exe --version` |
| Flutter SDK (Dart `^3.12`) | Mobile client | `flutter --version` |
| Gemini API key | Live agent chat + photo/plate reads | see below |

### Gemini API key

The agent reads its key from **`GEMINI_KEY.txt`** in the repo root (already present here), or from the `GOOGLE_API_KEY` / `GEMINI_API_KEY` environment variable. No key is needed to boot the server or to use the list/create/update endpoints — only the live agent turns (`/start`, `/message`) and photo/plate reads call Gemini. With the key missing or out of quota (429), those turns degrade gracefully to a fallback reply.

---

## 1. Backend — FastAPI server (optional — a hosted one is already live)

> **You can skip this whole section for a normal demo.** The client defaults to
> the live Cloud Run backend, so run the steps below only if you're developing the
> backend or want a fully local/offline stack. To use the hosted backend, jump to
> [Section 2](#2-client--flutter-app).

**Where:** repo root — `C:\Users\arthu\Documents\Google Agentic AI Course\appliance-fixer`

### 1a. (First time only) install dependencies into the venv

If `.venv` already has the deps (it does on this machine), skip to 1b.

```powershell
# PowerShell — create + populate the venv
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

### 1b. Run the server

> ⚠️ **You MUST launch with the project's `.venv` interpreter.** `google-adk` is installed only in `.venv`. A wrong interpreter still *boots* the server and the CRUD endpoints work, but every agent turn silently falls back with `ModuleNotFoundError: google.adk`.

```powershell
# PowerShell (repo root)
.venv\Scripts\python.exe -m uvicorn app.fast_api_app:app --host 0.0.0.0 --port 8000 --reload
```

```bash
# Bash equivalent
.venv/Scripts/python.exe -m uvicorn app.fast_api_app:app --host 0.0.0.0 --port 8000 --reload
```

The server listens on **http://127.0.0.1:8000**. It starts with no issues; any cases you create are persisted in the SQLite store (`home_rescue.db` in the repo root) and remain across restarts.

**Verify it's up** (in a second terminal):

```powershell
# PowerShell
Invoke-RestMethod http://127.0.0.1:8000/api/issues
# or open the interactive docs in a browser:
start http://127.0.0.1:8000/docs
```

Useful environment overrides (set before launching):

| Variable | Default | Purpose |
|----------|---------|---------|
| `APP_DB` | `home_rescue.db` | SQLite file path |
| `MEDIA_ROOT` | `media` | Where uploaded photos/videos are written |
| `GEMINI_MODEL` / `AGENT_MODEL` | `gemini-2.5-flash` | Model bucket (use a `-lite` bucket to stretch free-tier quota) |
| `GOOGLE_API_KEY` | (from `GEMINI_KEY.txt`) | Gemini key if not using the file |
| `SYMPTOM_ROUTER` | `schema` | How the agent maps a symptom to a curated fix bucket: `schema` (LLM extracts a structured feature schema → deterministic routing table) or `keyword` (legacy keyword matcher). Set to `keyword` to revert. |

```powershell
# Example: point at a lighter model bucket for dev
$env:GEMINI_MODEL = "gemini-2.5-flash-lite"
.venv\Scripts\python.exe -m uvicorn app.fast_api_app:app --host 0.0.0.0 --port 8000 --reload
```

Leave this terminal running.

---

## 2. Client — Flutter app

Runs on web, Windows desktop, and mobile (Android / iOS). To ship it as a
standalone phone app, see [Section 5, Deployment](#5-deployment).

**Where:** the `mobile/` subdirectory — `C:\Users\arthu\Documents\Google Agentic AI Course\appliance-fixer\mobile`

### 2a. (First time only) fetch packages

```powershell
cd mobile
flutter pub get
```

### 2b. Run the app

The base URL **defaults to the hosted Cloud Run backend** (production), so a bare build connects to the deployed backend with no flags. To target a **local** backend instead, pass `--dart-define-from-file=config/dev.json` (web, desktop Windows, iOS simulator). The **Android emulator** must use `10.0.2.2` to reach the host, so override it with `--dart-define=API_BASE_URL=http://10.0.2.2:8000`.

Pick the target that matches how you're demoing:

```powershell
# --- From the mobile/ directory ---

# Web (Chrome) — quickest to see it.
# Always pass a FIXED --web-port so the origin (and therefore the browser
# localStorage that holds the device id / saved issues) stays the same every
# run. Without it, Flutter picks a random port each launch -> a new origin ->
# the app looks like a brand-new user and "loses" prior issues. Helper:
#   ../scripts/run_web.ps1
flutter run -d chrome --web-hostname=127.0.0.1 --web-port=8080

# Windows desktop
flutter run -d windows

# Connected Android phone / iOS device (uses default 127.0.0.1 only if reverse-proxied;
# for a real device on the LAN, pass your host's IP instead)
flutter run -d <device-id>

# Android emulator — host is reachable at 10.0.2.2, NOT 127.0.0.1
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000
```

List available targets first if unsure:

```powershell
flutter devices
```

For a **real phone on the same Wi-Fi**, point at your machine's LAN IP and make sure the backend bound to `0.0.0.0` (it does above):

```powershell
flutter run --dart-define=API_BASE_URL=http://192.168.x.x:8000
```

Once running, the Home screen connects to the backend and shows an empty issue list on a fresh database. Tap **+ New Issue** to create your first case.

---

## 3. Tests

**Where:** repo root (Python tests) and `mobile/` (Flutter tests).

### Backend / Python tests

> Run with the **same `.venv` interpreter**. Do not let any other tooling run `pytest` here — a `conftest.py` redirects the temp root into `.tmp_pytest/` to avoid Windows access-denied temp dirs.

```powershell
# PowerShell (repo root) — full suite
.venv\Scripts\python.exe -m pytest

# A single file
.venv\Scripts\python.exe -m pytest tests/integration/test_state_integrity.py
```

### Eval suite (agent quality gate)

**Where:** repo root.

```powershell
# Live scoring (needs Gemini credits)
.venv\Scripts\python.exe tests/evals/run_evals.py

# Offline, from captured fixtures (no API calls — safe when quota is depleted)
.venv\Scripts\python.exe tests/evals/run_evals.py --fixtures-dir tests/evals/fixtures
```

### Flutter widget tests

**Where:** `mobile/`.

```powershell
cd mobile
flutter test
```

---

## 4. Helper scripts (optional)

**Where:** repo root, run with the `.venv` interpreter.

| Script | Command | What it does |
|--------|---------|--------------|
| Export OpenAPI snapshot | `.venv\Scripts\python.exe scripts/export_openapi.py` | Regenerates `app/openapi_snapshot.json` |
| End-to-end demo | `.venv\Scripts\python.exe scripts/e2e_demo.py` | Drives the three demo flows (reopen · happy path · escalation) |
| Capture Gemini fixtures | `.venv\Scripts\python.exe scripts/capture_fixtures.py` | Records live responses into `tests/evals/fixtures/` |
| Check billing/quota | `.venv\Scripts\python.exe scripts/check_billing.py` | Confirms the key has live quota before a demo |

---

## 5. Deployment

### 5a. Backend — hosted on Google Cloud Run (already live)

The backend is **already deployed** and serving production traffic:

| | |
|---|---|
| **Live URL** | https://home-rescue-1035771619142.us-central1.run.app |
| **Platform** | Google Cloud Run · project `agentic-coding-project-499917` · region `us-central1` · service `home-rescue` |
| **Cases DB** | Firestore Native (`(default)` database), collection `cases` |
| **Media** | GCS bucket `agentic-coding-project-499917-home-rescue-media` |
| **Gemini key** | Secret Manager secret `gemini-key`, mounted as env `GOOGLE_API_KEY` |

The same Docker image runs locally against SQLite + local files; three env vars
flip it to the cloud backends (`USE_FIRESTORE=1`, `GCS_BUCKET=…`,
`FIRESTORE_PROJECT=…`). Backend selection is env-driven in
`home_rescue/case_store.py` and `home_rescue/media_store.py`.

**Redeploy** (from repo root — run `gcloud auth login` first if your token expired):

```powershell
gcloud run deploy home-rescue --source . --region us-central1 --allow-unauthenticated `
  --service-account home-rescue-run@agentic-coding-project-499917.iam.gserviceaccount.com `
  --set-env-vars USE_FIRESTORE=1,GCS_BUCKET=agentic-coding-project-499917-home-rescue-media,FIRESTORE_PROJECT=agentic-coding-project-499917 `
  --set-secrets GOOGLE_API_KEY=gemini-key:latest `
  --project agentic-coding-project-499917 --quiet
```

The redeploy command above is self-contained: the same image runs locally
against SQLite + local files, and the three env vars flip it to the cloud
backends (Firestore + GCS).

### 5b. Mobile — build a standalone Android app

Because the client defaults to the hosted backend, a release APK is fully
self-contained — install it on a phone and it talks to Cloud Run with no local
server. The `--dart-define-from-file=config/prod.json` below pins the production
URL explicitly.

```powershell
# From the mobile/ directory
flutter build apk --release --dart-define-from-file=config/prod.json
```

The APK lands at `mobile/build/app/outputs/flutter-apk/app-release.apk`. Install
it on a connected device over ADB:

```powershell
adb install -r build/app/outputs/flutter-apk/app-release.apk
```

Notes:
- The **release build uses the debug signing config**, so no keystore is needed
  for sideloading a demo build.
- The launcher icon and `HomeRescue` home-screen label are already configured
  (`flutter_launcher_icons` + `AndroidManifest.xml`).
- **iOS** builds the same way (`flutter build ipa`) but needs an Apple signing
  identity; Android is the tested path.

---

## Quick start (TL;DR)

**Fastest path — client only, against the hosted backend (no local server):**

```powershell
# Flutter app (mobile/) — targets the live Cloud Run backend by default
cd mobile
flutter pub get
flutter run -d chrome --web-hostname=127.0.0.1 --web-port=8080   # fixed port: keeps the same origin/localStorage each run
# or ship it to a phone:  flutter build apk --release --dart-define-from-file=config/prod.json
```

**Full local stack (backend + client) — for backend dev / offline demos:**

```powershell
# Terminal 1 — backend (repo root)
.venv\Scripts\python.exe -m uvicorn app.fast_api_app:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2 — Flutter app (mobile/), pointed at the local backend
cd mobile
flutter pub get
flutter run -d chrome --web-hostname=127.0.0.1 --web-port=8080 --dart-define-from-file=config/dev.json
# or: flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000  (Android emulator)
```

Open the app → the Home list loads from the backend (empty on a fresh database) → tap **+ New Issue** to start a diagnosis. Live chat and photo reads require Gemini quota; with quota depleted, demo from the captured fixtures (`tests/evals/fixtures/`) so a 429 never blocks you.
