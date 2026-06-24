# Build Plan: Appliance Fixer (rebuild → Flutter mobile app)

Status: PROPOSED · 2026-06-24
Stack: Google ADK + Gemini (`gemini-2.5-flash`, multimodal) · SQLite · FastAPI (REST + SSE) · **Flutter mobile app (iOS + Android)**
Canonical design: [DESIGN_COMPLETE.md](./DESIGN_COMPLETE.md) (supersedes [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md), which describes the older `adk web`-only build).

> **Scope decisions (locked 2026-06-24):**
> 1. **Rebuild from scratch.** The backend committed in `04bb38b` (`appliance_fixer/`, `app/`, `tests/`)
>    is **reference only** — it matches the old `adk web` design (`photos[]`, no inspection guide, no REST
>    layer). Recover snippets with `git show 04bb38b:<path>` when useful, but the new tree is authored fresh.
> 2. **Full Flutter mobile app** is the committed client surface. The existing `frontend/` vanilla-JS web app
>    is kept only as a REST-contract reference and desktop dev convenience — it is **not** a plan deliverable.
> 3. The **manufacturer MCP mock** (DESIGN_COMPLETE §16), washer config, and other optionals are **gated** —
>    at most one, and only after the core demo is recorded (DESIGN_COMPLETE §3 hard rule). They appear here
>    as parked segments, not committed work.

---

## How to read this plan

The work is split into **16 committed segments** plus **gated optionals**. Each segment is sized to be
**built and verified on its own** — it has a single goal, an explicit file set, and a concrete test you can
run in isolation before moving on. A segment is "done" only when its verification passes.

**Per-segment fields**
- **Goal** — the one capability the segment adds.
- **Depends on** — segments that must be green first.
- **Build** — the files/work.
- **✅ Verify (isolated)** — the exact command/check that proves *this* segment, with nothing downstream built.
- **Quota** — `none` (no Gemini calls — never blocked by free-tier limits) · `fixture` (runs on recorded
  responses) · `live` (needs a real Gemini call — gate behind cached fixtures per DESIGN_COMPLETE §4).

**Test taxonomy** (matches DESIGN_COMPLETE §12): **unit** (deterministic code) · **eval** (LLM behavior,
scored) · **integration** (REST/SSE over a real store) · **widget/E2E** (Flutter) · **smoke** (manual, on device).

---

## Segment overview

| # | Segment | Layer | Depends on | Test kind | Quota |
|---|---------|-------|-----------|-----------|-------|
| **B1** | Scaffold + `CaseStore` (cases table, JSON `data`, `media[]`, status, `next_step`) | Backend core | — | unit | none |
| **B2** | Reopen walking skeleton (`load_case → recap → continue`) — **HEADLINE** | Backend core | B1 | unit + E2E | none |
| **B3** | Perception tools: `read_spec_plate` + `validate_model` (O↔0 / I↔1) | Backend tools | B1 | unit | fixture/live |
| **B4** | Thin curated layer `appliances/fridge.py` + `get_fixes` + caching | Backend data | B1 | unit | none |
| **B5** | Agent gather-then-fix loop + `record_step_result` + `next_step`/`awaiting_user` | Backend agent | B1–B4 | eval | live |
| **B6** | `SafetyGuard` (`before_model_callback`) + prompt rules | Backend safety | B5 | unit + eval | fixture |
| **B7** | Escalation: `generate_escalation_draft` + `generate_inspection_guide` + packet | Backend escalation | B4 | unit | none |
| **B8** | `/api/issues` REST + SSE + media upload endpoints | Backend API | B1–B7 | integration | fixture |
| **B9** | 3-eval harness + recorded-response fixtures + one-command runner | Backend evals | B3,B5,B6 | eval | live→fixture |
| **F1** | Flutter scaffold + API client + models (REST/SSE) | Flutter | B8 | widget | none |
| **F2** | Home — My Repairs list (cards, badges, next-step, FAB, resolved view) | Flutter | F1 | widget | none |
| **F3** | New Repair camera-first intake → `POST /api/issues` + plate scan | Flutter | F1, B8 | widget + smoke | fixture |
| **F4** | Repair detail / chat (summary sheet + SSE chat + camera + safety bubble) | Flutter | F1, B8 | widget + smoke | fixture |
| **F5** | Escalation / Inspection screen (draft + guided video capture + share sheet) | Flutter | F1, B7, B8 | widget + smoke | none |
| **F6** | Mobile cross-cutting: permissions, offline queue, media upload, push reg. | Flutter | F1–F5 | widget + smoke | none |
| **X1** | End-to-end demo verification (reopen · happy path · escalation packet) | Integration | all B + all F | E2E + smoke | live |
| — | **Gated optionals** (MCP mock · washer · before/after · annotated-photo) | — | X1 recorded | — | — |

---

## Phase A — Backend core (no Gemini calls; never quota-blocked)

Build and prove the persistence + resume spine first. None of these touch the model, so they cannot be blocked
by the free-tier quota and give a verifiable foundation under everything else.

### B1 — Scaffold + CaseStore
- **Goal:** one DB row per repair; whole-case read/write; the new-design JSON blob (`media[]`, `next_step`).
- **Depends on:** —
- **Build:** project scaffold (`pyproject.toml`, package layout per DESIGN_COMPLETE §6); `appliance_fixer/case_store.py`
  — `new_case / load_case / save_case / recap`; SQLite `cases(case_id PK, user_id, appliance, brand, model_number,
  status, data JSON, created_at, updated_at)`; CaseFile blob with `symptom_text, error_code, media[], steps[],
  cache{}, diagnosis{}, escalation|null, next_step`. Status enum: `intake|diagnosing|awaiting_user|escalated|resolved`.
- **✅ Verify (isolated):** `pytest tests/test_case_store.py` — JSON round-trip (persist → rehydrate identical),
  **unbounded** `steps[]` and `media[]` survive a save/load, `recap()` renders model + symptom + each step's outcome,
  status transitions are accepted. No server, no model.
- **Quota:** none.

### B2 — Reopen walking skeleton (HEADLINE, built early)
- **Goal:** the resume mechanism — `reopen_existing_case(case_id) → recap → continue` in a fresh session.
- **Depends on:** B1.
- **Build:** `appliance_fixer/reopen.py`; minimal ADK agent stub wired only enough to accept a reopen and replay
  the recap (full loop comes in B5). This subsumes the still-pending **resume-feasibility spike** (DESIGN_COMPLETE §4).
- **✅ Verify (isolated):** `pytest tests/test_reopen.py` — `new → save → close → load_case(case_id) → recap →
  continue` end to end; missing/corrupt `case_id` → clear error (not a crash). This is the headline E2E, provable
  with **zero** API calls.
- **Quota:** none.

### B4 — Thin curated layer + `get_fixes` + caching
> Built before B3/B5 because it is pure data and unblocks both. (Numbered B4 to keep the agent-facing grouping.)
- **Goal:** the spike-confirmed thin KB and the pluggable fix source.
- **Depends on:** B1.
- **Build:** `appliance_fixer/appliances/fridge.py` — `error_codes` table, `safety_rules`, ~3–5 targeted corrections
  (F2 coils-vs-seal, F8 evaporator-vs-condenser, Samsung `OF OF` demo-mode), clarifying-question hints,
  `model_patterns`, `support_contact`, **`inspection_shots`** (where the plate is, where the code displays, the
  component to film per fault class). `appliance_fixer/grounding.py` — `get_fixes`: curated table first, iFixit/Search
  optional bonus; results cached into `data.cache.grounded_fixes` (decision #6).
- **✅ Verify (isolated):** `pytest tests/test_grounding.py` — known error code → expected meaning; out-of-table code
  → surfaced verbatim with "check your manual" (never guessed); `get_fixes` returns ranked curated fixes with grounding
  off; second call reads from cache (no recompute). Validate `inspection_shots` shape for the demo fault classes.
- **Quota:** none (grounding off by default; the live demo never depends on it).

---

## Phase B — Perception, agent, safety (Gemini calls; gate behind fixtures)

These touch the model. Per DESIGN_COMPLETE §4, **capture recorded-response fixtures first** so a rate-limit never
blocks a take. Develop against `gemini-2.5-flash-lite` (separate free-tier bucket) and confirm on `flash` once.

### B3 — Perception tools
- **Goal:** read the spec plate from a photo and canonicalize the model number.
- **Depends on:** B1 (uses CaseStore for the plate-read cache).
- **Build:** `appliance_fixer/tools.py` — `read_spec_plate` (Gemini multimodal), `validate_model`
  (per-brand regex + membership check + **O↔0 / I↔1 canonicalization**, strip ` 00` / `/AA` suffixes), plus
  `normalize_model` / `canonicalize_symbols` helpers. Cache plate-read into `data.cache.plate_read` (decision #6).
- **✅ Verify (isolated):** `pytest tests/test_tools.py` — `validate_model` covers malformed, valid-but-wrong
  (transposition → membership reject), **O/0 and I/1 glyph** cases (the one spike miss) → all canonicalize and match;
  `read_spec_plate` runs against a **recorded fixture** image+response (no live call in CI). One manual `live` pass
  against `spikes/datasets/plates/` to confirm ≥7/8.
- **Quota:** fixture in CI; one live confirm.

### B5 — Agent gather-then-fix loop
- **Goal:** the three-phase loop — gather facts → iterate one ranked safe fix at a time → exit on resolved/escalate.
- **Depends on:** B1, B3, B4 (and B2's reopen entry).
- **Build:** `appliance_fixer/agent.py` — `LlmAgent` persona + gather-then-fix prompt; tool wiring
  (`read_spec_plate, validate_model, reopen_existing_case, initialize_new_case, lookup_fixes, record_step_result,
  generate_escalation_draft, generate_inspection_guide`). `record_step_result`: **deterministic** yes/no → `outcome`
  (no free-text LLM classification). Persist `next_step` on every `record_step_result`/`lookup_fixes` (3-tier
  derivation, DESIGN_COMPLETE §8). Set `awaiting_user` when a logged step's outcome is pending/`unsure`
  (resolves open question §17.2).
- **✅ Verify (isolated):** `pytest tests/evals/diagnosis_eval.py` — symptoms scored first-fix (2/1/0), target ≥16/20,
  **and** asserts the agent gathers appliance/brand/model/symptom **before** recommending a fix. Unit-assert `next_step`
  is written and `awaiting_user` is set on a pending step.
- **Quota:** live (run on fixtures in CI; one scored `flash` pass for the quality unit).

### B6 — SafetyGuard
- **Goal:** deterministic refusal of dangerous work (gas / mains electrical / water-on-electrics / refrigerant) →
  forces the escalate branch.
- **Depends on:** B5.
- **Build:** `appliance_fixer/safety.py` — `before_model_callback` scanning model output; prompt rules in the persona
  (defense in depth). On trip: force escalate **and** still run the escalation/packet path (B7).
- **✅ Verify (isolated):** `pytest tests/test_safety.py` (dangerous input → forced refusal, deterministic, no model
  needed) + `tests/evals/safety_eval.py` (dangerous prompts → **0 unsafe** = the gate). Assert a safety-forced
  escalation still produces the inspection packet.
- **Quota:** unit is fixture/none; eval is small and fixture-able.

### B7 — Escalation + inspection packet
- **Goal:** the service-ready handoff artifact.
- **Depends on:** B4 (curated `support_contact` + `inspection_shots`).
- **Build:** in `tools.py` — `generate_escalation_draft` (template + recipient: model + symptom + steps tried) and
  `generate_inspection_guide` (shot list derived from case + `inspection_shots`); assemble `data.escalation.packet`
  (summary + model + error_code + steps_tried + video_ref). **Draft/prepared only** (premise #3).
- **✅ Verify (isolated):** `pytest tests/test_escalation.py` — draft contains model/steps/contact and **never sends**;
  `generate_inspection_guide` covers **has-error-code vs no-code** and the **safety-forced** branch; packet shape is
  complete. Pure templating over case data → no model call.
- **Quota:** none.

---

## Phase C — REST layer + eval harness (the mobile contract)

### B8 — `/api/issues` REST + SSE + media
- **Goal:** the thin FastAPI layer the Flutter app talks to — **the one real gap** (FRONTEND_DESIGN §2).
- **Depends on:** B1–B7.
- **Build:** `app/fast_api_app.py` router over `CaseStore`:
  `GET /api/issues` (home list) · `GET /api/issues/{id}` (detail) · `POST /api/issues` (→ `initialize_new_case`,
  `status=intake`) · `POST /api/issues/{id}/media` (photo/video → `{ref}`) · `POST /api/issues/{id}/plate`
  (→ `read_spec_plate`) · `POST /api/issues/{id}/message` (agent turn, **SSE stream**) · `POST /api/issues/{id}/escalate`
  (→ draft + shot list + packet) · `POST /api/issues/{id}/resolve`. Media stored as blob/ref (video bytes not inlined).
  Reuse ADK's CORS.
- **✅ Verify (isolated):** `pytest tests/integration/test_api_issues.py` — full lifecycle over a temp DB: create →
  appears in list with derived `next_step` → upload media → escalate returns a complete packet → resolve hides it from
  the open list. SSE `/message` streams tokens (agent stubbed/fixture). `IssueSummary`/`IssueDetail` JSON shapes match
  FRONTEND_DESIGN §5.
- **Quota:** fixture (agent turns mocked in integration).

### B9 — Eval harness + fixtures
- **Goal:** one-command pre-record quality gate; recorded fixtures so a rate-limit never blocks a demo take.
- **Depends on:** B3, B5, B6.
- **Build:** `tests/evals/` — `diagnosis_eval`, `plate_read_eval`, `safety_eval` + a single runner; capture real
  Gemini responses as fixtures (carry the spike harness's 429 backoff + `--limit/--sleep/--no-grounding/--no-judge`).
- **✅ Verify (isolated):** one command runs all three; thresholds enforced — diagnosis ≥16/20, plate-read ≥7/8,
  safety **0 unsafe**. Re-runnable offline from fixtures.
- **Quota:** live to capture once, fixture thereafter.

---

## Phase D — Flutter mobile app

Thin client over B8. Build the API client first, then one screen per segment so each is demoable on its own with a
running backend. Each `F` segment ships **widget tests** (Flutter, offline against a mocked client) and a manual
**device smoke** check.

### F1 — Scaffold + API client + models
- **Goal:** a Flutter app that can call every B8 endpoint and parse the responses.
- **Depends on:** B8.
- **Build:** `mobile/` Flutter project; Dart models (`IssueSummary`, `IssueDetail`, `Step`, `Escalation`); REST client
  + an **SSE** client for `/message`; config for the backend base URL.
- **✅ Verify (isolated):** `flutter test` — model (de)serialization against captured JSON fixtures; client hits a mock
  server and maps each endpoint. `flutter run` launches against the real B8 server and prints a fetched issue list.
- **Quota:** none.

### F2 — Home / My Repairs list
- **Goal:** the at-a-glance dashboard (headline requirement #2).
- **Depends on:** F1.
- **Build:** scrollable cards (title, color-coded status badge + dot, muted `model · updated` line, truncated symptom,
  highlighted `Next →` strip, Continue/Review affordance); **+ New Repair** FAB; pull-to-refresh; "View resolved (n)".
- **✅ Verify (isolated):** `flutter test` widget tests — N issues render N cards; status→color mapping
  (intake grey · diagnosing amber · awaiting_user blue · escalated red · resolved green); resolved hidden behind the
  link; `next_step` strip shows. Device smoke: list scrolls, pull-to-refresh works.
- **Quota:** none.

### F3 — New Repair camera-first intake
- **Goal:** headline requirement #1 — **+** opens the camera immediately, then drops into chat (no form/modal).
- **Depends on:** F1, B8.
- **Build:** full-screen camera capture → `POST /api/issues/{id}/media` + `POST /api/issues/{id}/plate` (auto-fill
  brand/model/error code, user-correctable) → `POST /api/issues` → navigate into detail (F4). Camera-denied →
  type-in fallback (DESIGN_COMPLETE §11).
- **✅ Verify (isolated):** widget test — create flow posts the right payloads (mock client), plate auto-fill populates
  editable fields, permission-denied path shows the type-in fallback. Device smoke: real camera launches, plate scan
  pre-fills.
- **Quota:** fixture (plate endpoint mocked in widget tests).

### F4 — Repair detail / chat
- **Goal:** the working surface — glanceable case memory + live agent chat.
- **Depends on:** F1, B8.
- **Build:** collapsible top summary sheet (symptom, diagnosis, steps as green/amber checklist, next step,
  **Escalate to a pro**); SSE chat below via `reopen_existing_case(case_id)`; composer camera button;
  **safety refusal renders as a distinct warning bubble**.
- **✅ Verify (isolated):** widget test — summary sheet binds to `IssueDetail`; SSE tokens append to the transcript
  (fake stream); a safety-flagged message renders the warning-bubble style. Device smoke: reopen an existing case →
  recap + prior steps visible, chat continues.
- **Quota:** fixture.

### F5 — Escalation / Inspection screen
- **Goal:** the service-ready packet capture (headline requirement #3).
- **Depends on:** F1, B7, B8.
- **Build:** drafted message view + the agent's shot list as a checklist; **Record inspection video** opens the in-app
  camera overlaying each shot prompt ("Shot 2 of 4: show the display with the E1 code"); assemble packet → **Share**
  via the native share sheet. Per-shot length cap; refilm-a-shot prompt. Draft/prepared only.
- **✅ Verify (isolated):** widget test — `/escalate` response renders draft + shot checklist; completing shots enables
  Share; share invokes the OS sheet (mocked). Device smoke: guided capture overlays prompts, packet shares.
- **Quota:** none.

### F6 — Mobile cross-cutting
- **Goal:** the device concerns that make it a real phone app.
- **Depends on:** F1–F5.
- **Build:** in-context permission requests (camera/mic/notifications) with graceful denied states; **offline queue**
  for captures + outbound turns (server is authoritative; failed turn never corrupts state); media upload with retry
  on reconnect; push **registration** wired (notification feature itself is gated/out of baseline).
- **✅ Verify (isolated):** widget test — queued turn replays on reconnect; denied permission → fallback. Device smoke:
  airplane-mode capture → reconnect sync; share-sheet handoff.
- **Quota:** none.

---

## Phase E — End-to-end verification (the demo)

### X1 — E2E + mobile smoke
- **Goal:** prove the three demo beats on a real device before anything optional starts.
- **Depends on:** all B + all F.
- **Build/Run:** the three E2E scripts (reopen-the-case · happy repair path · escalation → inspection guide → packet)
  + the manual mobile smoke list (camera launch + plate capture; permission-denied → type-in; offline → reconnect;
  share-sheet handoff). Run all three evals (B9) green first.
- **✅ Verify:** on a phone — photo → correct model + error read → ≥1 correct safe fix from the loop → case persisted →
  **resumed in a fresh session** → escalation drafted **and** a guided inspection video captured into a packet; the
  safety refusal is visibly demoed. **Record this** — it unlocks the optionals gate.
- **Quota:** live (use captured fixtures as fallback so a take is never blocked).

---

## Gated optionals (DESIGN_COMPLETE §3 hard rule: at most ONE, only after X1 is recorded)

| Optional | What it adds | Effort | Why pick it |
|----------|-------------|--------|-------------|
| **MCP mock OEM server** (§16) | Standalone mock MCP server (`get_manual`, `get_pre_service_workflow`, `create_service_request`) wired as an ADK `MCPToolset` **behind `lookup_fixes`**; curated table stays as offline fallback. | ~1 day | Strongest "not just ChatGPT" rebuttal; demonstrates agent tool-use over a standard protocol (Kaggle agents track). |
| **Washer config** | One new `appliances/washer.py` (decision #4 — locality). | ~0.5 day | Shows the "add an appliance = one file" claim live. |
| **Before/after loop · annotated-photo-out** | Visual flourishes. | small | Cheapest visual win. |

Each, if chosen, is its own testable segment (e.g. the MCP mock ships with a `tests/test_mcp_mock.py` proving the
three tools return fixture data and the agent falls back to curated fixes when the server is unreachable).

---

## Dependency graph

```
B1 ──┬─ B2 (reopen skeleton, headline) ───────────────┐
     ├─ B3 (perception) ─┐                             │
     ├─ B4 (curated+fixes) ─┬─ B5 (agent loop) ─ B6 (safety) ┐
     │                      └─ B7 (escalation+packet) ────────┤
     └──────────────────────────────────────── B8 (REST/SSE) ─┴─ F1 ─┬─ F2 (home)
                                                                      ├─ F3 (new repair)
            B3 ─┐                                                     ├─ F4 (detail/chat)
            B5 ─┼─ B9 (eval harness)                                  ├─ F5 (escalation)
            B6 ─┘                                                     └─ F6 (cross-cutting)
                                                                              │
                                                              all B + all F ─ X1 (E2E/demo) ─ [gated optional ×1]
```

## Suggested order & parallel lanes (solo build)

1. **B1 → B2** first — the persistence + resume spine, zero quota risk, gives the headline early.
2. **B4** (pure data) can be authored **in parallel** with B2/B3 — no shared code.
3. **B3 → B5 → B6**, capturing fixtures (B9 groundwork) as you go so quota never blocks you.
4. **B7**, then **B8** closes the backend contract.
5. **F1 → F2 → F3 → F4 → F5 → F6** — one screen at a time, each demoable against the live backend.
6. **X1** — record the core. Only then start **one** gated optional.

## Quota strategy (carried from DESIGN_COMPLETE §4)

- Free-tier limits are **per-model**: dev on `gemini-2.5-flash-lite` (separate bucket), confirm once on `flash`.
- **Capture recorded-response fixtures before recording** (B9) — CI and demos replay them; a 429 never blocks a take.
- Backend-core segments (B1, B2, B4, B7) and all Flutter segments are **quota-free** — front-load them.

## Open questions to resolve before/while building (DESIGN_COMPLETE §17)

- **Terminology** — *Repair* vs *Issue* vs *case*: pick one user-facing word and align docs + mockups + the Flutter
  strings (the REST path stays `/api/issues`). Decide before F2.
- **`next_step` freshness** — persist-on-write (chosen here, snappier) vs compute-live. Revisit if the agent ever
  mutates state outside the tools.
- **Auth boundary** — single `user-default` for the capstone (recommended) vs stub a user id.
- **Demo target** — physical device (best camera moment) vs emulator (reproducible re-takes) for X1.
```
