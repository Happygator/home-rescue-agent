# Cloudflare Hosting — Implementation Plan

Goal: host everything that does **not** ship inside the Flutter app on Cloudflare —
the FastAPI backend, its data (cases DB + uploaded media), and a hosted web build.
The Flutter mobile app stays a store-distributed client; it only gets repointed at
the new backend URL.

## Decisions (locked 2026-06-29)
- **Backend host pivoted to Google Cloud Run** (the app is a Gemini/ADK app; Cloud Run
  runs the container with a real free tier and no paid-plan gate like Cloudflare Containers).
- **Cases DB → Firestore (Native mode)** — Google-native, always-free tier, and on Cloud Run
  it auth's via the service account (ADC), so no DB secrets. (Cloudflare D1 also still works
  over HTTP and remains coded as an alternative.)
- **Media → Google Cloud Storage** — same ADC story, no keys. (R2 also still coded.)
- **Web → hosted Flutter web build on Cloud Run / a static host** (NOT the stale `frontend/`
  folder, which is a dead vanilla-JS prototype calling `/api/tickets`; the live client is the
  Flutter app under `mobile/`). `frontend/` is out of scope.

The code supports ALL of these via env-var backend selection (SQLite | D1 | Firestore for the
DB; local | R2 | GCS for media), so nothing is locked in code — the deploy env picks the backend.

## Progress
- **Phase 1 (containerize): DONE + verified.** `Dockerfile` + `.dockerignore` build and
  run locally (`docker run` boots uvicorn, API smoke passes). Local Docker is pinned to
  4.37.1 — see the [[docker-desktop-pinned-4371]] memory.
- **Phase 2 (storage refactor): code DONE, all 123 tests green.**
  - Cases DB: `home_rescue/case_store.py` now runs its (unchanged) SQL through a pluggable
    executor — local SQLite by default, **D1 over its HTTP API** when `CF_ACCOUNT_ID` +
    `D1_DATABASE_ID` + `D1_API_TOKEN` are set. Selection happens inside `CaseStore.__init__`
    so both the API and the agent pick it up. Added `httpx` dep.
  - Media: new `home_rescue/media_store.py` — local filesystem by default, **R2** (S3 API)
    when `R2_BUCKET` + account id + `R2_ACCESS_KEY_ID` + `R2_SECRET_ACCESS_KEY` are set.
    `app/fast_api_app.py` (upload/get/image_path) and `app/turns.py` (`default_plate`) route
    through it. R2 backend materializes objects to a local temp path so the agent vision
    contract (`image_path` ending with the ref) is preserved. Added `boto3` dep.
  - Remaining: provision D1 (schema migration) + R2 bucket; wire env/secrets in wrangler.
- **Phase 3+ (wrangler/Worker/deploy, Flutter web → Pages): not started.**

---

## 1. What moves where

| Component | Today | Cloudflare target | Why |
|---|---|---|---|
| FastAPI + ADK/Gemini backend (`app/`, `home_rescue/`) | uvicorn on localhost:8000 | **Cloudflare Containers** (Docker behind a Worker) | google-adk / google-genai / uvicorn are native CPython — Workers' Pyodide runtime can't run them |
| Cases DB (`home_rescue.db`, `CaseStore`) | local SQLite file | **D1** (Cloudflare SQLite) — *primary*, or Neon Postgres via Hyperdrive — *alt* | container disk is ephemeral; state must live in a managed store |
| Uploaded media (`media/<case>/...`) | local filesystem | **R2** (S3-compatible object store) | same ephemeral-disk reason; R2 has an S3 API a Python container can use |
| Static web frontend (`frontend/`) | served separately | **Cloudflare Pages** (or static assets on the Worker) | pure HTML/JS/CSS |
| Gemini API key | `GEMINI_KEY.txt` / env | **Worker/Container secret** | never bake the key into the image |
| Curated grounding (fixes, manuals, models) | in-repo Python modules | bundled in the image | no DB needed — ships with code |
| Flutter app (`mobile/`) | localhost default | **stays off Cloudflare** | distributed via app stores; just set `--dart-define=API_BASE_URL` |

**Compute decision:** Cloudflare Workers (even Python Workers) cannot host this
backend — it depends on native packages and a long-lived uvicorn process.
**Cloudflare Containers** is the only Cloudflare product that runs the stack
as-is: a small Worker ("container class") fronts a Docker container that runs
uvicorn. All HTTP, SSE streaming, and outbound HTTPS to Gemini work normally.

---

## 2. Target architecture

```
Flutter app ─┐
             ├─► Cloudflare Worker (router + container binding)
Web (Pages) ─┘            │
                          ├─► Container: uvicorn → app.fast_api_app:app
                          │        │
                          │        ├─► D1   (cases)        via D1 HTTP API
                          │        ├─► R2   (media)        via S3 API
                          │        └─► Gemini / AI Studio  (outbound HTTPS)
                          └─► (Pages serves the static frontend)
```

---

## 3. Code changes required (the real work)

Three storage assumptions are baked into the code and must be abstracted. Each
is cleanly isolated, so the blast radius is small.

### 3a. Cases DB → D1
- `home_rescue/case_store.py` is a single `CaseStore` class (one `cases` table,
  a JSON `data` blob). Introduce a storage interface with the same method
  surface (`new_case`, `load_case`, `save_case`, `delete_case`, `list_cases`,
  `recap`) and add a D1-backed implementation that talks to the **D1 HTTP API**
  (the container is Python, so it can't use a Worker D1 binding directly).
- Schema maps 1:1 (D1 is SQLite); the `CREATE TABLE` in `_init_db` becomes a
  one-time migration run via `wrangler d1 execute`.
- Touch points that construct a store: `create_app()` in
  [app/fast_api_app.py](../app/fast_api_app.py) (`APP_DB` env) and `_store()` in
  [home_rescue/agent.py](../home_rescue/agent.py) (`tool_context.state["db_path"]`).
  Both should resolve the same configured backend instead of a file path.
- **Alternative (less rewrite):** Neon/Supabase Postgres reached directly with
  `psycopg`, optionally through **Hyperdrive** for pooling. Keeps real SQL and a
  normal driver; minor SQLite→Postgres dialect tweaks. Choose this if the D1
  HTTP round-trips per request (load-before-save) are a concern.

### 3b. Media → R2
- `upload_media` / `get_media` in [app/fast_api_app.py](../app/fast_api_app.py)
  currently `write_bytes` / `FileResponse` under `MEDIA_ROOT`. Swap to R2 via
  `boto3` against the R2 S3 endpoint (put on upload, stream/redirect on read).
- The agent vision path passes a **local file path** as `image_path` into
  `read_spec_plate` ([home_rescue/tools.py](../home_rescue/tools.py)), which does
  `photo_path.read_bytes()`. Change the contract to accept bytes (or fetch the
  R2 object to a temp file) so plate reads work without local media. The
  `/message` and `/start` handlers that build `image_path` from `MEDIA_ROOT` are
  the call sites to update.

### 3c. Secrets & config
- Replace `load_key()`'s `GEMINI_KEY.txt` fallback in deployed runs with the
  `GOOGLE_API_KEY` secret (set via `wrangler secret put`). Keep the file path
  only for local dev. (`GEMINI_KEY.txt` is already gitignored — good.)
- Honor `GOOGLE_GENAI_USE_VERTEXAI=0` and the `GOOGLE_API_KEY` precedence noted
  in `agent._ensure_api_env` so ADC OAuth doesn't shadow the key.

---

## 4. Frontend (Pages)

- `frontend/` is static and fetches **relative** `/api/...` paths, so it must be
  served same-origin as the API (route the Worker to serve both Pages assets and
  `/api/*` → container) **or** add a configurable API base + rely on the existing
  permissive CORS (`allow_origins=["*"]`).
- Note: `frontend/app.js` calls `/api/tickets/...` but the backend serves
  `/api/issues/...`. The static frontend appears to be a **stale prototype** —
  confirm whether it's still shipped. If it is, fix the path mismatch; if not,
  drop it from scope and deploy only the API (the Flutter app is the live
  client).

---

## 5. Step-by-step

**Phase 0 — Decide & prep**
1. Pick DB target: **D1** (Cloudflare-native, recommended) vs Neon-via-Hyperdrive.
2. Create the Cloudflare account resources: R2 bucket, D1 database (or Neon),
   and note their IDs/bindings.

**Phase 1 — Containerize (no Cloudflare yet)**
3. Add a `Dockerfile` (python:3.11-slim → `uv pip install .` →
   `uvicorn app.fast_api_app:app --host 0.0.0.0 --port 8000`).
4. Build and run locally; smoke-test the API + SSE against the existing SQLite/
   local-media behavior to confirm the image is correct before refactoring.

**Phase 2 — Storage refactor (§3)**
5. Abstract `CaseStore`; add the D1 (or Postgres) backend; run the schema
   migration.
6. Move media read/write to R2; update the `image_path` → bytes contract for
   plate reads.
7. Run the pytest suite against the new backends (use in-memory/local fakes for
   unit tests; an integration pass against real D1/R2).

**Phase 3 — Cloudflare wiring**
8. Add `wrangler.toml`: container definition + bindings for R2, D1, and the
   `GOOGLE_API_KEY` secret.
9. Add the front Worker (container class + router; serve `/api/*` → container,
   everything else → Pages assets if co-hosting the frontend).
10. `wrangler secret put GOOGLE_API_KEY`.

**Phase 4 — Deploy & verify**
11. `wrangler deploy` (builds/pushes the image + Worker, binds resources).
12. Verify end-to-end: create issue → upload media (lands in R2) → `/start` and
    `/message` **SSE stream through the Worker** (confirm no buffering) →
    escalate → resolve. Check Gemini calls succeed with the secret key.
13. `wrangler pages deploy frontend/` if the web client is in scope.

**Phase 5 — Repoint clients**
14. Rebuild Flutter with `--dart-define=API_BASE_URL=https://<backend-host>` and
    distribute via stores.
15. Optional: custom domain + Cloudflare Access in front of the API.

---

## 6. Risks / watch-items

- **SSE through the Worker→Container hop** — confirm the proxy streams
  `text/event-stream` without buffering (`/message`, `/start` rely on it).
- **D1 HTTP latency** — `save_case` does a `load_case` first; each is a network
  round-trip from the container. Fine at low volume; revisit with Postgres if
  it bites.
- **Cold starts** — Containers scale to zero; first request after idle pays a
  start cost. Acceptable for this workload; tune min-instances if not.
- **Ephemeral disk** — once §3 lands, nothing should touch local disk for
  durable state. Audit for any remaining `Path.write_*` before go-live.
- **Cost** — Containers + D1 + R2 are usage-billed; estimate against expected
  case/media volume.
```
