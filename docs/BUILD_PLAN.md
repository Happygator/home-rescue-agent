# Build Plan: Appliance Fixer (rebuild → Flutter mobile app)

Status: REVIEWED (eng + outside voice) · 2026-06-24
Stack: Google ADK + Gemini 3.5 Flash (multimodal) · SQLite · FastAPI (REST + SSE) · **Flutter mobile app (iOS + Android)**
Canonical design: [DESIGN_COMPLETE.md](./DESIGN_COMPLETE.md) (supersedes [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md), the older `adk web`-only build).

> **Scope decisions (locked 2026-06-24, confirmed in eng review):**
> 1. **Rebuild from scratch.** The backend committed in `04bb38b` (`appliance_fixer/`, `app/`, `tests/`)
>    is **reference only** — it matches the old `adk web` design. Recover snippets with `git show 04bb38b:<path>`;
>    the new tree is authored fresh.
> 2. **Full Flutter mobile app** is the committed client surface (screens F1–F5). The existing `frontend/`
>    vanilla-JS web app is a REST-contract reference / dev convenience only.
> 3. **Terminology:** the user-facing word is **"Issue"** (matches `/api/issues` + FRONTEND_DESIGN). Code stays
>    `case` / `case_id`; the REST path stays `/api/issues`. Align Dart strings, UI copy, and writeup to "Issue".
> 4. **ADK session lifecycle = reopen every turn** (stateless): each `/message` loads the case, injects the recap,
>    runs one turn, persists tool effects, closes. Robust to restarts; quota cost bounded by decision #6 caching.
> 5. **Media on the filesystem**, keyed by `case_id` (bytes never inlined in the case JSON; `media[]` holds refs).
> 6. **`next_step` is derived live** on read (pure 3-tier function, no LLM) — never persisted, so it can't go stale.
> 7. The **manufacturer MCP mock** (§16), washer config, the **offline queue + push (F7)**, and other optionals are
>    **gated** — at most one extra beyond the core, and only after the core demo is recorded (DESIGN_COMPLETE §3).

---

## How to read this plan

The work is split into **17 committed segments** plus **gated optionals**. Each segment is sized to be
**built and verified on its own** — single goal, explicit file set, one isolated test. A segment is "done"
only when its verification passes.

**Per-segment fields:** **Goal** · **Depends on** · **Build** · **✅ Verify (isolated)** · **Quota**
(`none` = no Gemini calls, never quota-blocked · `fixture` = recorded responses · `live` = real Gemini call,
gate behind cached fixtures per DESIGN_COMPLETE §4).

**Test taxonomy** (DESIGN_COMPLETE §12): **unit** · **eval** (LLM behavior, scored) · **integration** (REST/SSE
over a real store) · **widget/E2E** (Flutter) · **smoke** (manual, on device).

---

## Segment overview

| # | Segment | Layer | Depends on | Test kind | Quota |
|---|---------|-------|-----------|-----------|-------|
| **B1** | Scaffold + `CaseStore` + central status-transition fn | Backend core | — | unit | none |
| **B2** | Reopen walking skeleton (`load_case → recap → continue`) — **HEADLINE** | Backend core | B1 | unit + E2E | none |
| **B2.5** | `/api/issues` **contract stub** (FastAPI, stubbed responses, frozen schema) | Backend API | B2 | integration | none |
| **B3** | Perception tools: `read_spec_plate` + `validate_model` (O↔0 / I↔1) | Backend tools | B1 | unit | fixture/live |
| **B4** | Thin curated layer `appliances/fridge.py` + `get_fixes` + caching | Backend data | B1 | unit | none |
| **B5** | Agent gather-then-fix loop + `record_step_result` (+ `awaiting_user`) | Backend agent | B1–B4 | eval | live |
| **B6** | `SafetyGuard`: `after_model_callback` + `before_tool_callback` + prompt | Backend safety | B5 | unit + eval | fixture |
| **B7** | Escalation: draft + `generate_inspection_guide` + packet (+ media semantics) | Backend escalation | B4 | unit | none |
| **B8** | Flesh out `/api/issues`: live `derive_next_step`, SSE `/message`, fs media | Backend API | B2.5, B3–B7 | integration | fixture |
| **B9** | 3-eval harness + fixtures + deep state tests + one-command runner | Backend evals | B3,B5,B6 | eval | live→fixture |
| **F1** | Flutter scaffold + API client + models (REST/SSE) — builds on the **B2.5 stub** | Flutter | B2.5 | widget | none |
| **F2** | Home — My Issues list (cards, badges, next-step, FAB, resolved view) | Flutter | F1 | widget | none |
| **F3** | New Issue camera-first intake → create case **first**, then media/plate | Flutter | F1, B8 | widget + smoke | fixture |
| **F4** | Issue detail / chat (summary sheet + SSE chat + camera + safety bubble) | Flutter | F1, B8 | widget + smoke | fixture |
| **F5** | Escalation / Inspection screen (draft + guided video capture + share sheet) | Flutter | F1, B7, B8 | widget + smoke | none |
| **F6** | Mobile baseline: permissions + media upload + denied-state fallbacks | Flutter | F1–F5 | widget + smoke | none |
| **X1** | End-to-end demo verification (reopen · happy path · escalation packet) | Integration | all B + F1–F6 | E2E + smoke | live |
| — | **Gated optionals** (F7 offline+push · MCP mock · washer · before/after) | — | X1 recorded | — | — |

---

## Phase A — Backend core (no Gemini calls; never quota-blocked)

### B1 — Scaffold + CaseStore + status-transition function
- **Goal:** one DB row per repair; whole-case read/write; **one** place that owns status transitions.
- **Depends on:** —
- **Build:** scaffold (`pyproject.toml`, layout per DESIGN_COMPLETE §6); `appliance_fixer/case_store.py` —
  `new_case / load_case / save_case / recap`; SQLite `cases(case_id PK, user_id, appliance, brand, model_number,
  status, data JSON, created_at, updated_at)`. CaseFile blob: `symptom_text, error_code, media[], steps[], cache{},
  diagnosis{}, escalation|null` — **no `next_step` field** (derived live, §decision 6). A single
  `transition(case, event) -> status` function is the ONLY writer of `status`
  (`intake→diagnosing→awaiting_user→escalated|resolved`); every tool/endpoint goes through it (kills scattered
  status logic — eng-review C2).
- **✅ Verify (isolated):** `pytest tests/test_case_store.py` — JSON round-trip; unbounded `steps[]`/`media[]`
  survive save/load; `recap()` renders model + symptom + each step outcome; **`transition()` table** accepts legal
  moves and rejects illegal ones (e.g. `resolved→intake`). No server, no model.
- **Quota:** none.

### B2 — Reopen walking skeleton (HEADLINE, built early)
- **Goal:** the resume mechanism — `reopen_existing_case(case_id) → recap → continue` in a fresh session.
- **Depends on:** B1.
- **Build:** `appliance_fixer/reopen.py`; minimal ADK agent stub that accepts a reopen and replays the recap (full
  loop lands in B5). Subsumes the pending **resume-feasibility spike** (DESIGN_COMPLETE §4).
- **✅ Verify (isolated):** `pytest tests/test_reopen.py` — `new → save → close → load_case(case_id) → recap →
  continue`; missing/corrupt `case_id` → clear error. Headline E2E, **zero** API calls.
- **Quota:** none.

### B2.5 — `/api/issues` contract stub (pulled early — eng-review/Codex #11)
- **Goal:** freeze the REST/SSE contract the Flutter app depends on, before backend behavior is finished, so F1
  isn't blocked until B8 and the contract stops drifting.
- **Depends on:** B2.
- **Build:** `app/fast_api_app.py` — all `/api/issues` routes returning **stubbed/in-memory** responses with the
  final JSON shapes (`IssueSummary`, `IssueDetail`, `Step`, `Escalation`; FRONTEND_DESIGN §5). Generate the OpenAPI
  schema. Endpoints (final contract):
  ```
  POST /api/issues                  → { case_id }   # creates the intake case FIRST (status=intake)
  GET  /api/issues                  → [ IssueSummary ]   # next_step derived live (B8)
  GET  /api/issues/{id}             → IssueDetail
  POST /api/issues/{id}/media       → { ref }        # photo/video → filesystem, ref into media[]
  POST /api/issues/{id}/plate       → { brand, model, error_code }
  POST /api/issues/{id}/message     → SSE agent turn (reopen-every-turn invariant, B8)
  POST /api/issues/{id}/escalate    → { drafted_email, inspection_guide[], packet }
  POST /api/issues/{id}/resolve     → marks resolved
  ```
- **✅ Verify (isolated):** `pytest tests/integration/test_api_contract.py` — every endpoint returns the documented
  shape; OpenAPI snapshot is committed so contract changes are reviewable diffs. No real CaseStore wiring yet.
- **Quota:** none.

### B4 — Thin curated layer + `get_fixes` + caching
- **Goal:** the spike-confirmed thin KB and the pluggable fix source.
- **Depends on:** B1.
- **Build:** `appliance_fixer/appliances/fridge.py` — `error_codes`, `safety_rules`, ~3–5 corrections (F2
  coils-vs-seal, F8 evap-vs-condenser, Samsung `OF OF` demo-mode), clarifying hints, `model_patterns`,
  `support_contact`, **`inspection_shots`**. `appliance_fixer/grounding.py` — `get_fixes`: curated first,
  iFixit/Search optional; cached into `data.cache.grounded_fixes` (decision #6).
- **✅ Verify (isolated):** `pytest tests/test_grounding.py` — known code → meaning; out-of-table code → verbatim
  "check your manual" (never guessed); ranked curated fixes with grounding off; second call hits cache; validate
  `inspection_shots` shape.
- **Quota:** none.

---

## Phase B — Perception, agent, safety (Gemini calls; gate behind fixtures)

Capture recorded-response fixtures FIRST (DESIGN_COMPLETE §4). Production model is **Gemini 3.5 Flash**; dev on a lighter `-lite` bucket to stretch free-tier quota, confirm once on `gemini-3.5-flash`.

### B3 — Perception tools
- **Goal:** read the spec plate; canonicalize the model number.
- **Depends on:** B1.
- **Build:** `appliance_fixer/tools.py` — `read_spec_plate` (Gemini mm), `validate_model` (per-brand regex +
  membership + **O↔0 / I↔1**, strip ` 00` / `/AA`), `normalize_model` / `canonicalize_symbols`. Cache plate-read
  into `data.cache.plate_read` (decision #6).
- **✅ Verify (isolated):** `pytest tests/test_tools.py` — `validate_model` malformed / valid-but-wrong / **O-0,
  I-1 glyph**; `read_spec_plate` against a **recorded fixture** (no live CI call). One manual `live` pass on
  `spikes/datasets/plates/` to confirm ≥7/8.
- **Quota:** fixture in CI; one live confirm.

### B5 — Agent gather-then-fix loop
- **Goal:** gather facts → iterate one ranked safe fix → exit on resolved/escalate.
- **Depends on:** B1, B3, B4 (and B2's reopen entry).
- **Build:** `appliance_fixer/agent.py` — `LlmAgent` persona + gather-then-fix prompt; tool wiring
  (`read_spec_plate, validate_model, reopen_existing_case, initialize_new_case, lookup_fixes, record_step_result,
  generate_escalation_draft, generate_inspection_guide`). `record_step_result`: **deterministic** yes/no →
  `outcome`, and it drives status only through `transition()` (B1) — sets `awaiting_user` on a pending/`unsure`
  step (DESIGN_COMPLETE §17.2). **No `next_step` writes** (derived live in B8).
- **✅ Verify (isolated):** `pytest tests/evals/diagnosis_eval.py` — first-fix scored 2/1/0, target ≥16/20, **and**
  asserts facts (appliance/brand/model/symptom) are gathered **before** any fix. Unit-assert `awaiting_user` is set
  via `transition()` on a pending step.
- **Quota:** live (fixtures in CI; one scored `gemini-3.5-flash` pass).

### B6 — SafetyGuard (corrected mechanism — eng-review/Codex #8)
- **Goal:** deterministic refusal of dangerous work (gas / mains electrical / water-on-electrics / refrigerant) →
  force the escalate branch, with a backstop that can actually see what it's guarding.
- **Depends on:** B5.
- **Build:** `appliance_fixer/safety.py` — **`after_model_callback`** scans the model's *response* for dangerous
  steps (a `before_model_callback` fires before generation and can't see output), **plus `before_tool_callback`**
  to block a dangerous tool invocation (e.g. a step instruction that slips past text scanning). Prompt rules in the
  persona (defense in depth). On trip: force escalate **and** still run B7 (packet). Note streaming: the guard
  evaluates the assembled turn, and the client renders the safety bubble only after the guard clears/forces.
- **✅ Verify (isolated):** `pytest tests/test_safety.py` — dangerous text → `after_model_callback` forces refusal;
  dangerous tool args → `before_tool_callback` blocks; deterministic, no model. `tests/evals/safety_eval.py` →
  **0 unsafe** (the gate). Assert a safety-forced escalation still produces the packet.
- **Quota:** unit none; eval small/fixture-able.

### B7 — Escalation + inspection packet (+ media semantics — Codex #6)
- **Goal:** the inspection handoff artifact, with the file/media questions answered up front, not deferred.
- **Depends on:** B4.
- **Build:** in `tools.py` — `generate_escalation_draft` (template + recipient: model + symptom + steps) and
  `generate_inspection_guide` (shot list from case + `inspection_shots`); assemble `data.escalation.packet`
  (summary + model + error_code + steps_tried + **`video_ref`**). **The backend owns `video_ref`** (filesystem,
  §decision 5); the packet references it, never inlines bytes. Specify now: per-shot length cap → bounded total
  size; target container/MIME (`video/mp4`, H.264) for share-sheet compatibility; the shared artifact is
  **structured text (the draft) + the video file** so the OS share sheet handles both. **Draft/prepared only**
  (premise #3).
- **✅ Verify (isolated):** `pytest tests/test_escalation.py` — draft has model/steps/contact and **never sends**;
  `generate_inspection_guide` covers **has-error-code vs no-code** and the **safety-forced** branch; packet shape
  complete incl. `video_ref`; size/MIME constraints asserted. Pure templating, no model call.
- **Quota:** none.

---

## Phase C — REST behavior + eval harness

### B8 — Flesh out `/api/issues` (behavior behind the B2.5 contract)
- **Goal:** wire the frozen contract to real CaseStore + agent behavior.
- **Depends on:** B2.5, B3–B7.
- **Build:** replace the B2.5 stubs with real logic:
  - `POST /api/issues` **creates the intake case first** and returns `case_id`; **only then** can the client
    `POST /{id}/media` and `/{id}/plate` (fixes the F3 impossible order — Codex #2).
  - `GET /api/issues` computes **`derive_next_step(case)`** live — one shared pure function (3-tier: escalated →
    last pending step → first un-tried fix), no LLM, no persisted field (kills the DRY split + staleness —
    eng-review C1/A3).
  - `POST /{id}/message` enforces the **reopen-every-turn invariant** (Codex #3): load case → inject recap/state →
    run one turn → persist tool effects via CaseStore → close; stream tokens over **SSE**.
  - Media: bytes written to `media/{case_id}/{ref}` on the **filesystem** (§decision 5); `media[]` holds the ref +
    mime + kind. Reuse ADK CORS.
- **✅ Verify (isolated):** `pytest tests/integration/test_api_issues.py` — create → list shows **derived**
  `next_step` → upload media (lands on fs) → escalate returns a complete packet → resolve hides it. SSE `/message`
  streams; **a second `/message` re-injects the recap** (reopen-every-turn asserted). Responses still match the
  B2.5 OpenAPI snapshot.
- **Quota:** fixture (agent turns mocked).

### B9 — Eval harness + deep state tests + fixtures
- **Goal:** one-command quality gate + the state-integrity tests Codex #9 flagged.
- **Depends on:** B3, B5, B6.
- **Build:** `tests/evals/` — `diagnosis_eval`, `plate_read_eval`, `safety_eval` + single runner; capture Gemini
  fixtures (429 backoff + `--limit/--sleep/--no-grounding/--no-judge`). **Add integration tests for:** multi-turn
  state corruption (10+ turns, case JSON stays valid), **repeated reopen** (reopen ×3 → recap stable, no dup
  steps), **media upload failure mid-escalation** (packet assembles with a missing `video_ref` → clear "retake"
  state, not a crash), and **derived-state consistency** (`derive_next_step` matches the real case after an
  in-chat advance).
- **✅ Verify (isolated):** one command runs all three evals (diagnosis ≥16/20, plate ≥7/8, safety 0 unsafe) +
  the state tests; re-runnable offline from fixtures.
- **Quota:** live to capture once, fixture thereafter.

---

## Phase D — Flutter mobile app

Thin client over the **B2.5 contract** (F1 can start before B8 behavior lands). Each F segment ships **widget
tests** (offline, mocked client) + a manual **device smoke**.

### F1 — Scaffold + API client + models
- **Depends on:** B2.5 (the frozen contract — not B8).
- **Build:** `mobile/` Flutter project; Dart models (`IssueSummary`, `IssueDetail`, `Step`, `Escalation`); REST
  client + **SSE** client for `/message`; backend base-URL config. User-facing strings say **"Issue"**.
- **✅ Verify:** `flutter test` — (de)serialization against captured JSON fixtures; client maps each endpoint
  against a mock server. `flutter run` against the B2.5 stub prints a fetched issue list.
- **Quota:** none.

### F2 — Home / My Issues list
- **Depends on:** F1.
- **Build:** cards (title, color-coded status badge + dot, `model · updated` meta, truncated symptom, highlighted
  `Next →` strip from the API's derived `next_step`, Continue/Review affordance); **+ New Issue** FAB;
  pull-to-refresh; "View resolved (n)".
- **✅ Verify:** `flutter test` — N issues → N cards; status→color (intake grey · diagnosing amber · awaiting_user
  blue · escalated red · resolved green); resolved hidden; `Next →` renders. Smoke: scroll + pull-to-refresh.
- **Quota:** none.

### F3 — New Issue camera-first intake (corrected order — Codex #2)
- **Depends on:** F1, B8.
- **Build:** **+** opens the camera immediately → **`POST /api/issues` first (get `case_id`)** → then
  `POST /{case_id}/media` + `POST /{case_id}/plate` (auto-fill brand/model/error, user-correctable) → navigate
  into detail (F4). No intake form/modal. Camera-denied → type-in fallback (DESIGN_COMPLETE §11).
- **✅ Verify:** widget test — create posts case first, then media/plate to the returned id (mock client); plate
  auto-fill populates editable fields; permission-denied → type-in fallback. Smoke: real camera + plate pre-fill.
- **Quota:** fixture.

### F4 — Issue detail / chat
- **Depends on:** F1, B8.
- **Build:** collapsible summary sheet (symptom, diagnosis, steps as green/amber checklist, next step, **Escalate
  to a pro**); SSE chat below (server runs reopen-every-turn); composer camera button; **safety refusal as a
  distinct warning bubble**.
- **✅ Verify:** widget test — sheet binds to `IssueDetail`; SSE tokens append (fake stream); safety message →
  warning-bubble style. Smoke: reopen → recap + prior steps visible, chat continues.
- **Quota:** fixture.

### F5 — Escalation / Inspection screen
- **Depends on:** F1, B7, B8.
- **Build:** drafted message + shot-list checklist; **Record inspection video** opens the in-app camera overlaying
  each shot prompt; on completion assemble packet → **Share** via native share sheet (text draft + mp4). Per-shot
  cap (B7 size budget); refilm-a-shot prompt. Draft/prepared only.
- **✅ Verify:** widget test — `/escalate` renders draft + checklist; completing shots enables Share; share invokes
  the OS sheet (mocked) with both artifacts. Smoke: guided capture overlays prompts, packet shares.
- **Quota:** none.

### F6 — Mobile baseline (trimmed — eng review)
- **Goal:** the device concerns the three demo beats actually need. **Offline queue + push moved to gated F7.**
- **Depends on:** F1–F5.
- **Build:** in-context permission requests (camera / mic) with graceful denied states; media upload (capture →
  `POST /{id}/media`) with a simple inline retry; the type-in / file-picker fallbacks for denied camera.
- **✅ Verify:** widget test — denied permission → fallback path; upload retry on a transient failure. Smoke:
  capture + upload on a real device; share-sheet handoff.
- **Quota:** none.

---

## Phase E — End-to-end verification (the demo)

### X1 — E2E + mobile smoke
- **Depends on:** all B + F1–F6.
- **Build/Run:** three E2E scripts (reopen · happy path · escalation → inspection guide → packet) + the manual
  smoke list (camera + plate capture; permission-denied → type-in; share-sheet handoff). Run all three evals (B9)
  green first. **Decide the live-vs-fixture demo path explicitly** (Codex #10): the recorded take may run on
  captured fixtures so a 429 never blocks it; if claiming a *live* camera moment, pre-flight quota that morning.
- **✅ Verify:** on a phone — photo → correct model + error read → ≥1 correct safe fix → case persisted → **resumed
  in a fresh session** → escalation drafted **and** a guided inspection video captured into a packet; safety refusal
  visibly demoed. **Record this** — it unlocks the optionals gate.
- **Quota:** live (fixtures as fallback).

---

## Gated optionals (DESIGN_COMPLETE §3 hard rule: at most ONE beyond the core, only after X1 is recorded)

| Optional | What it adds | Effort | Why pick it / risk |
|----------|-------------|--------|--------------------|
| **F7 — Offline queue + push** | Queue captures/turns offline, sync on reconnect; push **registration** for "did the fix hold?" | ~1–1.5 day | The flaky-garage-wifi resilience the design pitched. **Cut from baseline** per eng review — state-reconciliation + native-setup risk, not a demo beat. |
| **MCP mock OEM server** (§16) | Mock MCP server (`get_manual`, `get_pre_service_workflow`, `create_service_request`) as an ADK `MCPToolset` behind `lookup_fixes`; curated fallback. | ~1 day | Strongest "not just ChatGPT" rebuttal (Kaggle agents track). Risk: if the core slips it gets rushed — the writeup must not *depend* on it (Codex #13). |
| **Washer config** | One `appliances/washer.py` (decision #4 locality). | ~0.5 day | Proves "add an appliance = one file" live. |
| **Before/after · annotated-photo-out** | Visual flourishes. | small | Cheapest visual win. |

Each, if chosen, is its own testable segment (the MCP mock ships `tests/test_mcp_mock.py`: three tools return
fixtures + the agent falls back to curated fixes when the server is unreachable).

---

## Dependency graph

```
B1 ──┬─ B2 (reopen, HEADLINE) ─ B2.5 (REST contract stub) ─────────────── F1 ─┬─ F2 (home)
     ├─ B3 (perception) ─┐                                  ▲                  ├─ F3 (new issue)
     ├─ B4 (curated) ─┬─ B5 (agent) ─ B6 (safety) ┐         │ (frozen contract)├─ F4 (detail/chat)
     │                └─ B7 (escalation+packet) ───┤         │                 ├─ F5 (escalation)
     │                                             └─ B8 (REST behavior) ──────┴─ F6 (baseline)
     └───────────────────────────────────────────────                          │
        B3,B5,B6 ─ B9 (evals + state tests)              all B + F1–F6 ─ X1 (demo) ─ [gated ×1]
```

## Suggested order & parallel lanes (solo build)
1. **B1 → B2 → B2.5** — persistence + resume + the frozen contract. Zero quota; unblocks Flutter immediately.
2. **B4** (pure data) in parallel with B3.
3. **F1 + F2** can start against the B2.5 stub while backend Phase B proceeds (real parallel lane now).
4. **B3 → B5 → B6 → B7 → B8**, capturing fixtures (B9 groundwork) as you go.
5. **F3 → F4 → F5 → F6** once B8 behavior lands.
6. **X1** — record the core. Then **one** gated optional.

## Quota strategy (DESIGN_COMPLETE §4)
- Production model is **Gemini 3.5 Flash** (`gemini-3.5-flash`). Per-model free-tier: dev on a lighter `-lite` bucket, confirm once on `gemini-3.5-flash`. Capture fixtures before recording.
- Quota-free, front-loadable: B1, B2, B2.5, B4, B7, and all of F1–F6.

---

## What already exists (reuse / reference, don't rebuild)
- **Old backend `04bb38b`** (`case_store.py`, `tools.py`, `safety.py`, `reopen.py`, `agent.py`, `grounding.py`):
  reference for CaseStore shape, `validate_model` regex, the recap format. Rebuilt fresh (old design: `photos[]`,
  no inspection guide, no REST, `before_model_callback`).
- **`frontend/` vanilla-JS web app:** working reference for the REST contract + screen behavior; not a deliverable.
- **`spikes/`:** plate datasets + diagnosis symptoms + answer keys feed `plate_read_eval` / `diagnosis_eval`
  directly. Reuse, don't recollect.
- **ADK runtime, `DatabaseSessionService`, callbacks, Gemini 3.5 Flash multimodal, SQLite+JSON1:** framework primitives —
  configure, don't reimplement.

## NOT in scope (explicitly deferred, with rationale)
- **Offline queue + push (F7)** — gated; reconciliation/native risk, not a demo beat.
- **Real outbound** (auto-send email, host/upload video) — draft/prepared only (premise #3).
- **Live manufacturer MCP / per-company intake** — mock is at most one gated optional (§16).
- **Washer + dishwasher build** — washer gated (one file); dishwasher descoped.
- **Multi-user auth** — single `user-default`; web + mobile share that list (accepted for the capstone).
- **Edit/delete issues, search/filter beyond open-vs-resolved** — out.
- **App-store distribution / CI-CD** — distribution = writeup + public code + demo video (real device or emulator).

---

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Codex Review | `/codex review` | Independent 2nd opinion | 1 | issues_found | 13 findings; 5 folded, 4 surfaced as tensions, 4 noted |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | clean | 8 issues (A1–A4, C1–C2, test gaps); 0 critical gaps; all resolved |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | — |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | — |

- **CODEX (outside voice):** ran via `codex exec` (gpt-5.5, high effort). 13 findings. Folded without dispute:
  next_step-still-persisted, F3 impossible endpoint order, reopen-every-turn unspecified, packet-media semantics,
  weak/shallow tests. Noted (writeup/demo risks, not plan changes): "service-ready" overmarketing, fixtures≠live,
  MCP-mock-as-differentiator danger.
- **CROSS-MODEL:** 4 tensions surfaced to the user; all decided — **F6 trimmed** to baseline (offline+push→gated
  F7) against the prior "keep F6"; **SafetyGuard** corrected to `after_model_callback` + `before_tool_callback`;
  **REST contract pulled early** (new B2.5); **terminology = "Issue"**. The full Flutter scope was reconsidered and
  held (F1–F5), with F6 trimmed as the compromise.
- **VERDICT:** ENG CLEARED — ready to implement. CEO + Design reviews optional (significant UI surface exists; a
  design review could be worthwhile before F2–F5 if desired).

**UNRESOLVED DECISIONS:**
- **Demo target for X1** — physical device (best camera moment) vs emulator (reproducible re-takes). Decide before X1.
