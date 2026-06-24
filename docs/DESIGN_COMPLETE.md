# Comprehensive Design Document

Status: CONSOLIDATED · 2026-06-23 (mobile-app revision)
Stack: Google ADK + Gemini (`gemini-2.5-flash`, multimodal) · SQLite · FastAPI · **Flutter mobile app (iOS + Android)**

> This document compiles every design decision made across the project into a single
> reference. It supersedes nothing — the source documents remain canonical for their
> domains — but it is the one place that holds the whole picture end to end.
>
> **Source documents consolidated here:**
> [DESIGN.md](./DESIGN.md) (the approved product design + 5 premises) ·
> [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md) (architecture, data model, 7 locked decisions) ·
> [SPIKE_RESULTS.md](./SPIKE_RESULTS.md) (Day-0/1 de-risking) ·
> [FRONTEND_DESIGN.md](./FRONTEND_DESIGN.md) (the mobile app) ·
> [TEST_PLAN.md](./TEST_PLAN.md) (verification).

---

## 1. Product summary

When a household appliance fails (fridge too warm, washer won't drain), a non-expert has two
bad options: pay for a service call they may not need, or self-diagnose by hunting
YouTube/forums. Most "broken" appliances are trivial fixes (dirty condenser coil, clogged
filter, wrong setting, tripped breaker). The agent takes a user from "X is broken"
to a safe fix — or, when that fails, to a clean escalation to the right repair contact **with a
service-ready inspection packet in hand** — with the entire repair persisted so they can stop and
resume later.

**Why a phone app, not a website:** the whole job happens at the appliance — you point the camera
at the spec plate and the symptom, in your kitchen or garage, often with one hand. A native app
opens the camera instantly, captures photos and (at escalation) a video walkthrough, survives a
flaky garage Wi-Fi connection, and can notify you when it's time to check whether a fix held. A
website is the wrong form factor for a camera-first, in-the-moment, multi-session task.

### The three fused hooks

1. **Camera-magic diagnosis** — point the phone at the model/spec plate and the symptom;
   Gemini reads the exact model number, decodes the error code, and names the likely fault.
2. **The repair that remembers** — a resumable case file. Stop at 9pm, resume at 8am, with full
   continuity, like a contractor managing your job across days.
3. **The escalation that gets you scheduled on the first call** — when the agent hands off to a
   pro, it doesn't just draft an email. It generates a **service-ready inspection packet**: the
   model + error code + every step already tried, *plus a guided in-app video walkthrough* shot to
   the exact spec a dispatcher's video inspection wants. Many service companies require a video
   inspection before they'll dispatch a tech — usually a second call hours later. This packet lets
   the **first** call schedule the repairman.

**Differentiation (the chain nobody does end-to-end today):** *photo of your specific unit →
exact model + error code → guided multi-session safe loop → close the loop to escalation with a
service-ready video inspection packet, with memory.* iFixit/YouTube, RepairClinic/PartSelect,
manufacturer bots, and raw Gemini each do a slice; none do the whole chain — and none prepare the
handoff artifact the service company actually asks for.

---

## 2. Constraints & premises (the ground rules)

### Constraints
- Stack: Google ADK + Gemini (multimodal) backend; **Flutter mobile client (iOS + Android)** over
  the existing FastAPI REST/SSE layer.
- Graded deliverables: working agent + Kaggle writeup + ~3-min video.
- Safety is non-negotiable: never advise dangerous gas / electrical / water / refrigerant work.

### The 5 premises (agreed in the /office-hours session)
1. **Narrow + deep** to ~3 appliance categories (fridge, washer, dishwasher), not "any appliance."
   Reliability and a tight story win a capstone; breadth loses it.
2. **Thin curated layer + grounding** — error-code→step table + safety rules + a few vetted
   corrections, with the model doing the heavy lifting. **RESOLVED 2026-06-21** by the Day-1 spike
   (see §4): keep the KB thin; no big hand-authored diagnosis KB.
3. **Draft/prepared outbound in v1.** Email/escalation **and the inspection packet/video** are
   prepare-only: the agent assembles them and the user sends/shares them via the native share sheet
   with explicit confirmation. Real auto-sending and video hosting are clearly-labeled stretches.
4. **Safety is a demo feature.** The agent refuses dangerous work and escalates to a pro — and
   the refusal is demoed on purpose.
5. **Memory is the headline.** The persistent, resumable case file is the spine of the writeup
   and video — built early and made visible.

---

## 3. The chosen approach

**Decision: Approach A — "The Tight Loop."** A single ADK agent + tools: photo → model/code read →
thin-KB lookup → ranked safe fixes in a guided loop → persisted case file → **escalation with a
service-ready inspection packet**, with the safety refusal demoed on purpose. The builder
prioritized certainty of finishing a clean demo over novelty — sound for a solo, graded, 2-week
build.

**Demo target:** fridge = committed · washer = gated stretch (one config file) · dishwasher =
descoped from the build (appears in problem framing for context only). "3 categories" is the
problem space, not the ship list.

**Client:** the **Flutter mobile app** is the committed surface. (Flutter was chosen over React
Native and a PWA for smoothest native rendering — AOT-compiled, own GPU engine, no webview/bridge —
plus first-class camera/video and a single iOS+Android codebase. A PWA was rejected as a
"website in disguise" for a camera-first task.) `adk web` remains a dev-only playground.

**Optionals are gated, not open.** The annotated-photo-out flourish, the before/after loop, real
video hosting/auto-send, and Cloud Run deployment are all OUT of the baseline. **Hard rule:** do
not start ANY optional until fridge end-to-end + the safety refusal + the resume moment + the
inspection-packet escalation are recorded on video — and then pick AT MOST ONE.

> The alternatives that were weighed (Approach B "The Crew", Approach C "The Instrument"), the
> rejection rationale, and the cross-model brainstorming have moved to
> [DESIGN_BRAINSTORM.md](./DESIGN_BRAINSTORM.md). This document keeps only the locked design.

---

## 4. De-risking: what the Day-0/1 spikes settled

Two headline features rested on unverified assumptions. Both were spiked before building on them
(full detail in [SPIKE_RESULTS.md](./SPIKE_RESULTS.md)).

| Spike | Result | Build input it produced |
|-------|--------|-------------------------|
| **Plate-read** (perception hook) | **PASS — 7/8 exact** on `gemini-2.5-flash`, incl. the two hardest (low-contrast HVAC foil, no-logo compact fridge). | The one miss was an **O↔0 glyph confusion**, not a misread → `validate_model` MUST canonicalize O↔0 and I↔1 (and strip ` 00` / `/AA` suffixes) before matching. With that, 8/8. |
| **Diagnosis quality** (premise #2) | **21/24 (~88%)** first-fix correct, **0 unsafe**, with NO knowledge base, on the *weaker* `flash-lite` (a conservative lower bound). | **Premise #2 RESOLVED → thin KB.** Don't author a big diagnosis KB. Keep only: error-code→meaning table + safety rules + ~3-5 targeted corrections (e.g. F2 coils-vs-seal, F8 evaporator-vs-condenser fan). |
| **Resume feasibility** | **PENDING** → built as the Day 1-2 walking skeleton (needs no API calls; not quota-blocked). | Deterministic reopen-by-`case_id` is the real mechanism (see §6, Decision 7). |

**Ops/quota learning (carried forward):** free-tier limits are **per-model** — `gemini-2.5-flash`
daily cap hit after ~22 calls; `gemini-2.5-flash-lite` is a separate fresh bucket. Adding billing
to the AI Studio key is currently blocked, so dev uses model-bucket switching + slim harness modes
(429 backoff, `--limit/--sleep/--no-grounding/--no-judge`). Before recording: capture real Gemini
responses as fixtures so a rate-limit never blocks a take.

**Mobile note:** the inspection-video-guide feature (§9 phase 3) needs **no new spike** — it is a
templated generation over data the case already holds (same pattern as the escalation draft, which
the diagnosis spike already exercised). The only new perception surface is in-device video
*capture*, which is a Flutter/OS concern, not a model concern.

---

## 5. The 7 locked architectural decisions

From the /plan-eng-review (the authoritative engineering decisions). All 7 are backend decisions and
are **unchanged by the mobile pivot** — the client swap touches only the presentation layer.

| # | Decision | Choice | What it actually means | Why |
|---|----------|--------|------------------------|-----|
| 1 | Case storage | **`cases` table + JSON `data` column** | Each repair is one DB row; everything variable-length (steps, photos/video, cache) lives in a single JSON blob, so reading or saving a whole case is one row read/write. | Whole-case access pattern; unbounded steps/media as JSON arrays; reopen = a plain `load_case(id)` DB read. No normalized multi-table schema. |
| 2 | Diagnosis flow | **Gather-info → iterate-fixes → escalate loop** (no rigid tree) | The agent first collects appliance, brand, model number, symptom and any error code; then repeatedly proposes one ranked safe fix and records whether it worked; it exits only when the problem is resolved or it escalates to a pro **with the inspection packet** (see §9). | Mirrors how a real technician works and matches the persisted step list; no brittle decision-tree traversal to author or test. Collapsed the originally-planned scripted tree. |
| 3 | Safety guardrail | **Prompt + `before_model_callback` backstop** | Two layers: the prompt tells the model to refuse dangerous work, and a deterministic code callback inspects every model response and forces escalation if a dangerous step slips through. | Defense in depth; the callback is the deterministic, unit-testable, demoable Day-4 artifact. |
| 4 | Curated data layout | **One config module per appliance** | All of a given appliance's data (error codes, safety rules, support contact, model patterns, **inspection-shot hints**) lives in one file; adding a new appliance means adding one new file and touching nothing else. | Locality; adding the washer stretch = one new file (`appliances/fridge.py` → `appliances/washer.py`). |
| 5 | Eval scope | **3 core evals** (diagnosis, plate-read, safety) | Automated quality checks cover only the three behaviors that can actually go wrong (diagnosis quality, plate reading, safety) instead of broad code coverage. | The three risky LLM behaviors; double as the Day-0/1 spikes and the quality-unit evidence. |
| 6 | Expensive reads | **Cache plate-read + grounding in case `data`** | The costly Gemini calls (plate read, grounded fixes) are saved into the case the first time they run, so reopening or re-rendering a case never re-calls the model. | Snappy/deterministic turns, lower quota burn. |
| 7 | Resume model | **"Reopen the case" via `load_case(case_id)`, built early** | Resuming a repair = loading the saved case by its id and replaying a recap into a fresh chat — the app's own mechanism, not ADK's session sidebar. | `adk web` resumes by *ADK session id*, not your `case_id` (ADK #781) → the deterministic reopen is the real feature, front-loaded as a Day-2 walking skeleton. |

---

## 6. System architecture

```
        Flutter mobile app (iOS + Android)  ── or ──  adk web (dev playground)
        camera · video capture · push · offline queue · native share sheet
                            │
                            ▼  REST + SSE (HTTPS)
                  ┌─────────────────────┐        before_model_callback
   user photo ───▶│   LlmAgent (Gemini) │◀────── SafetyGuard (deterministic)
   + video        │   persona +         │        scans output for gas/elec/
   + text         │   gather-then-fix   │        water/refrigerant → forces
                  │   loop prompt       │        escalate-to-pro
                  └──────────┬──────────┘
                             │ tool calls
   ┌──────────┬─────────┬────┼─────────┬───────────────┬───────────────┬──────────────┐
   ▼          ▼         ▼    ▼         ▼               ▼               ▼              ▼
 read_plate validate_ lookup record_  generate_       generate_       reopen_existing
 (Gemini mm) model    _fixes step_     escalation_     inspection_     _case
            (regex +  (curated result   draft           guide           (load_case →
            O↔0/I↔1)  +ground)         (template +     (shot list per   recap → continue)
   │                                   contact)        diagnosis)
   └──────────── load_case / save_case ──────────────────────────────────────────────┘
                             │
              ┌──────────────────────────┐   ┌──────────────────────────┐
              │  CaseStore (SQLite)      │   │ ADK DatabaseSessionService │
              │  cases(case_id, …, data) │   │ conversation events only   │
              │  + media blobs/refs      │   └──────────────────────────┘
              └──────────────────────────┘

   REOPEN (headline): fresh session → load_case(case_id) → recap → continue
   (deterministic, yours; NOT the adk web session sidebar)

   ESCALATE (handoff): generate_escalation_draft + generate_inspection_guide →
   user films guided video in-app → packet assembled → native share sheet
```

**Two stores, no overlap:** `CaseStore` = the structured case file; the ADK session = the live
conversation. Reopen reads `CaseStore`. This is the project's core architectural stance.

**Client/server split:** the Flutter app is a thin client over the FastAPI REST/SSE layer (§8).
It owns device concerns only — camera/video capture, local media buffering, push registration,
offline request queueing, and the native share sheet. All diagnosis logic, state, and persistence
stay on the server, so the app stays simple and the agent remains the single source of truth. This
split is also *forced* by the stack: ADK is a server-side Python framework, so the agent loop — and
the MCP/tool client co-located with it (§16) — runs on the backend, not the device; the model being
stateless enables a thin client but does not require one. Full rationale and the rejected
backendless alternative:
[DESIGN_BRAINSTORM.md §6](./DESIGN_BRAINSTORM.md#6-clientserver-split--thin-client-thick-server-recorded-2026-06-24).

### Module map (as built / planned)
```
appliance_fixer/
  agent.py        LlmAgent: persona + gather-then-fix loop prompt; tool wiring.
                  Tools: read_spec_plate, verify_model_number, reopen_existing_case,
                  initialize_new_case, lookup_fixes, record_step_result,
                  generate_escalation_draft, generate_inspection_guide
  tools.py        normalize_model, canonicalize_symbols, validate_model (regex + membership +
                  O↔0 / I↔1), read_plate (Gemini mm), draft_escalation, build_inspection_guide
  case_store.py   CaseStore: new/load/save/recap (SQLite + JSON data column) + media refs
  reopen.py       deterministic reopen entry point: load_case(case_id) → recap → continue
  safety.py       SafetyGuard: before_model_callback (deterministic refusal)
  appliances/
    fridge.py     THIN curated layer: error_codes + safety rules + ~3-5 corrections +
                  clarifying hints + model_patterns + support_contact + inspection_shots
  grounding.py    get_fixes: curated table first, iFixit/Search as optional bonus
app/
  fast_api_app.py FastAPI server: ADK chat routes + the /api/issues REST layer (§8)
                  + media upload + inspection/escalation packet endpoint
mobile/           Flutter app (lib/: screens, api client, camera/video, push, offline queue)
tests/            unit (case_store, reopen, tools, safety, inspection_guide) + integration + evals
```

---

## 7. Data model — the Case File (the persisted "memory")

One record per repair case, keyed by `case_id` (+ `user_id`). This is the object the resume UX
rehydrates — it was built first. The mobile pivot adds **video media** and the **inspection
packet** to the existing JSON blob; no schema change beyond the JSON.

```
cases  (SQLite)
  case_id TEXT PK | user_id | appliance | brand | model_number (validated)
  status  TEXT  -- intake | diagnosing | awaiting_user | resolved | escalated
  data    JSON  -- the CaseFile blob below | created_at | updated_at

CaseFile (the JSON `data` blob)
  symptom_text, error_code (nullable)
  media:     [ {kind: plate|symptom|inspection_video, ref, mime, taken_at} … ]   # unbounded
  steps:     [ {step_id, instruction, asked_at, user_result,
                outcome: resolved|not_resolved|unsure|skipped} … ]               # unbounded
  cache:     { plate_read:{…}, grounded_fixes:[…] }                              # decision 6
  diagnosis: { hypothesis, confidence }
  escalation:{ recipient, drafted_email,
               inspection_guide:[ {shot_no, what_to_film, where, narration} … ],  # the shot list
               packet:{ summary, model, error_code, steps_tried, video_ref },     # service-ready
               sent:false } | null
```

> **`media[]` replaces the old `photos[]`** — same unbounded-array pattern, now carrying the
> inspection video alongside plate/symptom photos. `kind` distinguishes them; `ref` points at a
> blob/file the FastAPI media layer stores (video bytes are not inlined in the JSON).

**Key design choice — deterministic outcome mapping.** `user_result` → `outcome` is mapped with a
simple yes/no confirmation prompt ("did that fix it?"), **NOT** free-text LLM classification. This
keeps state transitions deterministic and is the safer 2-week choice — it is the operational heart
of the loop.

**Inspection guide & packet are draft/prepared only (premise #3).** The agent assembles the shot
list and the packet; the *user* records the video in-app and shares the packet via the native
share sheet. The app does not auto-send or host the video in v1.

---

## 8. Mobile app — the Repair Console

The agent's only built-in surface is ADK's generic dev playground (`adk web`) — a single ephemeral
chat with no concept of "my open problems," and not a phone experience. The **Flutter app** is the
purpose-built client with three headline requirements:

1. A prominent **"+ New Repair"** action (a floating action button) that **opens the camera
   immediately** to capture the spec plate, then drops the user straight into the chat — there is
   **no intake form/modal**; the agent gathers the appliance, brand, model, and symptom in
   conversation (§9, phase 1).
2. An **at-a-glance list of all unresolved repairs**, each with a one-line **"next steps"** summary.
3. At escalation, a **guided video-capture screen** that walks the user shot-by-shot through the
   inspection video and assembles the service-ready packet.

**A "repair" is exactly the agent's existing case** — the app is a view over the `CaseStore` that
already exists; it invents no new data model.

| App concept | Backend reality |
|-------------|-----------------|
| Repair / Repair ID | a row in `cases` / `case_id` |
| Unresolved | `status` ≠ `resolved` |
| Title | `brand` + `appliance` |
| Symptom / Steps | `data.symptom_text` / `data.steps[]` |
| Next steps | derived (see below) |
| The chat | ADK conversation, reopened via `reopen_existing_case(case_id)` |
| Inspection video | `data.media[]` of kind `inspection_video` + `data.escalation.inspection_guide` |

### Screens (Flutter; stack navigation rooted at Home)
- **Home — My Repairs:** a scrollable list of unresolved repair cards (newest-updated first), each
  showing title + color-coded status badge, a muted meta line (`model · "updated" time`), the
  truncated symptom, a highlighted **`Next →`** strip, and a **Continue** affordance (Escalated
  cards show **Review**). Pull-to-refresh. Resolved repairs live behind a "View resolved (n)" link.
  A prominent **"+ New Repair"** FAB opens the camera (spec-plate capture) and navigates **straight
  into the chat** — no modal, no form.
- **Repair detail / chat:** a collapsible top sheet shows the structured case from `CaseStore`
  (symptom, diagnosis, steps as a green/amber checklist, the next step, an **Escalate to a pro**
  action). Below it, the live agent chat. The composer has a **camera button** for capturing the
  spec plate and symptom photos (`read_spec_plate` auto-fills brand/model/error-code, which the
  user can correct). For a brand-new repair this is where §9 phase 1 happens (in chat, not a form);
  for an existing repair the chat is reopened via `reopen_existing_case(case_id)`. Safety refusals
  render inline as a distinct warning bubble so "this needs a pro" is visible, not buried.
- **Escalation / Inspection screen** (new): when fixes are exhausted (or safety forces it), this
  screen shows (a) the **drafted escalation message** (model + symptom + steps tried), and (b) the
  **video capture guide** — the agent's shot list as a checklist. A **"Record inspection video"**
  button opens the in-app camera and overlays each shot's prompt ("Shot 2 of 4: show the display
  with the E1 code"). When recording is done, the app assembles the **service-ready packet** and
  offers **Share** (native share sheet → email/messages/portal upload). Draft/prepared only
  (premise #3): the user sends it.

### Status → color
| Status | Badge | Meaning |
|--------|-------|---------|
| `intake` | grey | Created, still gathering brand/model/symptom |
| `diagnosing` | amber | Actively working a fix |
| `awaiting_user` | blue | Waiting on the user to try something / report back |
| `escalated` | red | Handed to a pro; escalation + inspection packet prepared |
| `resolved` | green | Closed (hidden from the open list) |

### Computing "next steps" (the headline detail)
Three derivation tiers, cheapest first — **no extra LLM call on list load**:
1. **Escalated** → `"Pro service required — escalation email + inspection video guide ready to send."`
2. **Has a pending/last step** → surface the most recent not-yet-resolved step's instruction.
3. **Diagnosing with a hypothesis** → first un-tried fix from `get_fixes(…)`.

Persist this as a `next_step` string on the case (written when `record_step_result`/`lookup_fixes`
runs) so the list is a pure DB read — consistent with the cache-expensive-reads decision (#6).

### Mobile-specific concerns (new with the pivot)
- **Permissions:** camera (required for the core hook), microphone (for narrated inspection video),
  notifications (optional — used for future "did the fix hold?" follow-ups). Each is requested
  in-context, with a graceful denied-state (type-in fallback for camera; §11).
- **Media handling:** photos/video are captured locally, uploaded to the FastAPI media endpoint,
  and referenced from `media[]`. Video is kept short (guide caps each shot) to bound upload size.
- **Offline / flaky signal:** garages and laundry rooms have poor Wi-Fi. The app queues captures
  and outbound turns locally and syncs when connectivity returns; the case is server-authoritative,
  so a failed turn never corrupts state.
- **Native share sheet:** the escalation packet is shared through the OS share sheet rather than the
  app sending mail itself — keeps premise #3 (prepared, not sent) and needs no mail server.
- **Push (optional, gated):** registration is wired so a later "proactive follow-up" stretch can
  notify the user when it's time to check a fix. Not in the baseline build.

### The `/api/issues` REST layer
A thin FastAPI router in [fast_api_app.py](../app/fast_api_app.py) wrapping the existing `CaseStore`
— no new persistence model, now with media upload and the inspection packet:

```
GET  /api/issues                      → [ IssueSummary ]    # home list
GET  /api/issues/{case_id}            → IssueDetail         # detail sheet
POST /api/issues                      → { case_id }         # New Repair → initialize_new_case (intake; details gathered in chat)
POST /api/issues/{case_id}/media      → { ref }             # upload plate/symptom photo or inspection video
POST /api/issues/{case_id}/plate      → { brand, model, error_code }   # read_spec_plate
POST /api/issues/{case_id}/message    → agent turn (chat, SSE stream)
POST /api/issues/{case_id}/escalate   → { drafted_email, inspection_guide[], packet }  # draft + shot list
POST /api/issues/{case_id}/resolve    → mark resolved
```

The chat itself is **not** re-implemented on device — the detail screen drives the agent (reopened
with `reopen_existing_case(case_id)` so it loads the full recap and prior steps). The Flutter app
renders the SSE stream from `/message`.

> **⚠ Drift note (2026-06-23):** earlier docs proposed first a **React + Vite + TypeScript SPA**,
> then shipped a **vanilla HTML/CSS/JS** web app
> ([frontend/index.html](../frontend/index.html)). **This revision supersedes both:** the client
> is a **Flutter mobile app** (`mobile/`). The existing `frontend/` web app is retained only as a
> desktop/dev convenience and reference for the REST contract; it is no longer the primary surface.
> The data model, REST contract, and screen *design* carry over; only the client stack and form
> factor change. Update [FRONTEND_DESIGN.md](./FRONTEND_DESIGN.md) §9 to match.

---

## 9. Diagnosis flow & curated data

The agent runs a three-phase loop that mirrors how a real technician works: **gather the facts,
iterate on safe fixes, escalate if it can't be solved** (decision #2).

1. **Gather information.** Establish what the appliance and problem are — appliance type, brand,
   model number, the symptom in the user's words, and any error code. The camera path reads the
   spec plate (`read_spec_plate` → `validate_model`); the agent asks for anything still missing.
   This phase fills the Case File (§7) and moves `status` from `intake` → `diagnosing`.
2. **Try fixes (the loop).** The agent proposes the next ranked safe fix, the user performs it, and
   the outcome is recorded (`record_step_result`, yes/no confirmation → `outcome`). It keeps
   looping — one fix at a time — until the problem is **resolved** or there are no more safe fixes
   to try. **Ranking key:** safety-permitted first → most likely → least user effort.
3. **Escalate (with a service-ready inspection packet).** When fixes are exhausted (or the safety
   guard forces it), the agent:
   - looks up the relevant **support contact** — brand email and/or phone — and **drafts** an
     escalation message containing the model, the symptom, and the steps already tried; and
   - calls **`generate_inspection_guide`** to produce a **shot-by-shot video capture guide** so the
     user can satisfy the service company's video-inspection requirement on the **first** call.
     The guide is derived from the case (model, error code, symptom, suspected component) plus the
     appliance's curated `inspection_shots` hints — e.g. *"1. Film the spec plate (inside left
     wall). 2. Show the display with the E1 code lit. 3. Open the freezer, pan the frost pattern on
     the back panel. 4. Narrate the symptom and what you already tried."*
   - The app then lets the user record the guided video, assembles the **packet** (model + error +
     steps tried + diagnosis + the video), and shares it. **Draft/prepared only (premise #3):** the
     user sends/uploads it themselves.

The deterministic SafetyGuard (§10) can force the escalate branch at any point in the loop if the
model proposes dangerous work — in which case the inspection packet is generated just the same, so
the dangerous-DIY case still ends with a clean, scheduled handoff.

**Why this is feasible and cheap (see §4):** `generate_inspection_guide` is the same templated
pattern as the escalation draft, over data the case already holds. The agent-side work is low; the
genuinely hard parts are *external* — the agent cannot know every company's exact intake form, and
cannot force a company to accept an async video instead of a live call. So the honest claim is: the
agent **prepares the user to satisfy the video-inspection step in one pass and maximizes the odds
of immediate scheduling** — it does not control the company's workflow. The guide is therefore
*generic-industry-standard + brand-curated*, not per-dispatcher-exact.

### Flow diagram

```
   photo + text
        │
        ▼
┌─────────────────────────────────────────────┐
│ 1. GATHER INFO                              │
│    appliance · brand · model_number ·       │
│    symptom · error_code                     │
│    (read_spec_plate → validate_model;       │
│     ask for anything still missing)         │
└───────────────────────┬─────────────────────┘
                        │  status: intake → diagnosing
                        ▼
┌─────────────────────────────────────────────┐
│ 2. TRY THE NEXT SAFE FIX                    │◀────────────┐
│    propose ranked safe fix →                │             │
│    user performs it →                       │             │  yes — another
│    record_step_result ("did it work?")      │             │  safe fix to try
└───────────────────────┬─────────────────────┘             │
                        ▼                                    │
                  resolved? ───── yes ─────▶ RESOLVED (close the case)
                        │
                        │ no
                        ▼
              more safe fixes left? ───── yes ──────────────┘
                        │
                        │ no   (or SafetyGuard forces escalation at any time)
                        ▼
┌─────────────────────────────────────────────┐
│ 3. ESCALATE (service-ready handoff)         │
│    look up brand support email / phone →    │
│    draft message (model + symptom + steps)  │
│    generate_inspection_guide → shot list →  │
│    user films guided video in-app →         │
│    assemble packet → share (draft-only)     │
└─────────────────────────────────────────────┘
```

### Curated data
- **Thin curated layer** (`appliances/fridge.py`, premise #2 resolved): error-code→meaning table
  (brand-specific codes the model can't reliably know) + safety rules + ~3-5 targeted corrections +
  clarifying-question hints + model-number patterns + a per-brand support contact + **per-appliance
  `inspection_shots`** (where the plate is, where the code displays, the component to film for a
  given fault class). The model does the rest; iFixit/Search grounding is an optional bonus the live
  demo never depends on.
- **Error codes** are scoped to the demo unit's codes (a Whirlpool "E1" ≠ an LG "E1"); an
  out-of-table code is surfaced verbatim with a "check this in your manual" prompt, not guessed.
- **Escalation contact** = a per-brand support email/phone in the curated table, with a
  user-supplied override. The agent looks it up at escalation time (phase 3); no live "find the
  right place" web search in v1.

---

## 10. Safety design

- **Two layers (defense in depth):** the agent's persona/prompt rules + a deterministic
  `before_model_callback` `SafetyGuard` that scans output for gas/electrical/water/refrigerant work
  and forces escalate-to-pro. The callback is the unit-testable, demoable artifact.
- **Safety is demoed on purpose** — the agent visibly refuses a dangerous instruction and escalates
  to a professional. `safety_eval` gate = **0 unsafe answers**.
- **Safety + escalation compose:** a safety-forced escalation still runs phase 3, so even the "this
  is too dangerous to DIY" path ends with a clean, service-ready inspection packet rather than a
  dead end.

---

## 11. Perception & capture unhappy paths

| Codepath | Failure | Handling | User sees |
|----------|---------|----------|-----------|
| `read_plate` | blurry/unreadable | retry ×2, then type-in | "couldn't read it — retake or type the model" |
| `validate_model` | valid-but-wrong (transposition) | membership check → re-prompt | asked to confirm/retake |
| `validate_model` | O/0 or I/1 glyph confusion (observed in spike) | canonicalize before matching | transparent (still matches) |
| `read_plate` | no plate in frame | guide where it usually is (inside door, back, base) | location hint |
| camera | permission denied | fall back to type-in / file picker | "type your model number instead" |
| inspection video | clip too long / too dark / shot skipped | per-shot guide caps length; prompt to refilm a shot | "retake shot 2 — the code wasn't visible" |
| media upload | offline / flaky signal | queue locally, retry on reconnect | "saved — will upload when you're back online" |
| `lookup_fixes` | iFixit/grounding down at demo | fall back to curated table | seamless |
| safety guard | model emits dangerous step | callback overrides → escalate (+ packet) | "this needs a pro, here's why — and here's your inspection video" |
| reopen | `case_id` not found / corrupt JSON | guard + clear error | "couldn't find that repair" |
| Gemini call | rate-limit / quota | cache + recorded-response fixture | snappy; recording never blocked |

Validation layer = per-brand regex (catches malformed reads) + membership check against the
curated/grounded set (catches plausible-but-wrong reads) + O↔0 / I↔1 canonicalization.
**Critical-gap check:** no failure mode is both untested AND silent.

---

## 12. Test & eval plan

Greenfield discipline: every path ships with its test.

- **Unit (~12):** CaseStore round-trip (JSON persist/rehydrate, unbounded steps + media);
  reopen (load-by-id → recap; missing/corrupt id → clear error); `validate_model` (malformed,
  valid-but-wrong, O/0–I/1 glyph); `record_result` outcome mapping; `draft_escalation` template +
  recipient; **`generate_inspection_guide` (shot list derived from case + curated hints; covers
  has-error-code vs no-code, and safety-forced escalation)**; SafetyGuard (dangerous input →
  forced refusal + packet still generated); perception/capture unhappy paths.
- **Evals (3 core, run all before recording):**
  - `diagnosis_eval` — symptoms scored first-fix (2/1/0), target ≥16/20, AND asserts it gathers the
    required facts (appliance/brand/model/symptom) before recommending a fix. (Spike: ~88% on
    flash-lite floor.)
  - `plate_read_eval` — model-number read accuracy N/M across ~3 lighting conditions. (Spike: 7/8.)
  - `safety_eval` — dangerous prompts MUST refuse + escalate (0 unsafe = the gate).
- **E2E (~3):** reopen-the-case (THE HEADLINE); happy repair path; **escalation → inspection guide →
  packet assembled** (draft path).
- **Mobile smoke (manual, pre-record):** camera launch + plate capture on a real device; permission
  denied → type-in fallback; offline capture → reconnect sync; share-sheet handoff.

---

## 13. Build order

1. **Day 0-1 (THE ASSIGNMENT):** real fridge photos + the two gating spikes (diagnosis, plate-read)
   + the resume-feasibility spike. ✅ done except resume (folded into the walking skeleton).
2. **Day 1-2:** ADK scaffold; `case_store.py` + load/save tools; **the reopen-the-case WALKING
   SKELETON end to end** (new → save → close → load → recap → continue) before anything thickens.
3. **Day 2-3:** agent gather-then-fix loop prompt; `read_plate` + `validate_model`; `fridge.py`
   thin layer; `get_fixes` + caching; `diagnosis_eval`.
4. **Day 3-4:** `safety.py` callback + prompt rules; `safety_eval`; `plate_read_eval`.
5. **Day 4-5:** `draft_escalation` (draft-only) + **`generate_inspection_guide`** and the
   `inspection_shots` curated hints; thicken the recap; harden the fridge path.
6. **Day 5-6:** **Flutter app** — Home/My Repairs list, camera-first New Repair, chat (SSE),
   detail sheet, escalation/inspection screen with guided video capture + share. Wire to REST.
7. **Day 6-7:** demo reruns on a real device. Optionals GATED — at most one, only after the core
   (fridge E2E + safety refusal + resume + inspection-packet escalation) is recorded.
8. **Day 8+:** writeup + 3-min video; quota pre-flight; buffer.

---

## 14. Out of scope (explicitly deferred)

- **`adk web` session-sidebar resume** — superseded by the deterministic reopen path (ADK #781).
- **Rigid decision tree / adaptive re-planner** — replaced by the gather-then-fix loop.
- **Big hand-authored diagnosis KB** — spike-confirmed unnecessary; curation stays thin.
- **Real outbound** (auto-send email / place calls / **host or auto-upload the inspection video** /
  write calendar) — draft/prepared only in v1; the user shares via the native share sheet.
- **Live video-call inspection integration / per-company intake forms** — the guide is
  generic-industry-standard + brand-curated, not per-dispatcher-exact (see §9). The
  manufacturer-partnership MCP server (§16) is the productized future answer to this gap.
- **Real manufacturer/service-network MCP integration** — the live partner-hosted
  manual + pre-service-workflow + dispatch server is post-capstone product direction (§16); v1 ships
  the thin curated layer, and a *mock* of that server is at most one gated optional.
- **Push-driven proactive follow-up** ("did the fix hold?") — registration is wired; the feature is
  a gated stretch.
- **Washer + dishwasher build** — washer is a gated stretch (one config file); dishwasher descoped.
- **Multi-user accounts / auth** — single `user-default` today.
- **Editing/deleting repairs, search/filter beyond open-vs-resolved.**
- **Normalized multi-table schema** — JSON column chosen (decision 1).
- **App-store distribution / CI-CD / packaging** — capstone; distribution = writeup + public code +
  demo video (recorded from a real device or emulator).
- **Multi-agent crew** — single agent (Approach A).
- **Appliances beyond refrigerator**, the before/after photo-diff loop, annotated-photo-out, and
  Cloud Run — gated optionals, at most one, only after the core is recorded.

---

## 15. Success criteria

- End-to-end demoable on fridge **on a phone**: photo → correct model + error-code read → ≥1
  correct, safe fix from a guided loop → case persisted → resumed in a fresh session → **escalation
  drafted AND a guided inspection video captured into a service-ready packet** when fixes exhaust.
- Safety: the agent visibly refuses a dangerous instruction and escalates — with the packet still
  produced.
- The 3-min video shows the camera moment, the resume moment, the safety refusal, **and the
  inspection-packet escalation**.
- The writeup names the differentiation chain (now including the service-ready handoff) and cites
  the grounding source.

---

## 16. Forward direction: Manufacturer-partnership MCP server

> **Status: PROPOSED direction — not a locked v1 decision.** v1 ships the thin curated layer the
> spike validated (§4). This section records the productization path the design is built to grow
> into, and the demo mock that makes that path visible. Full exploratory treatment (moat analysis,
> partnership economics, mock surface) in
> [DESIGN_BRAINSTORM.md §5](./DESIGN_BRAINSTORM.md#5-the-manufacturer-partnership-mcp-integration-differentiation-direction).

**The problem it answers.** The diagnosis spike (Gemini-alone ≈88%, premise #2) is what keeps the KB
thin — but it also invites the question *"then how is this not just a ChatGPT chat with a camera?"*
The durable answer is **not** a bigger prompt; it is connecting to a **manufacturer-hosted (or
service-network-hosted) MCP server** for the brand's authoritative, model-specific manual and
**pre-service workflow** — the steps a brand runs *before* it will dispatch a technician.

**Why this is a moat and not a feature.** The "recommended pre-dispatch actions" for a specific model
have **no public source** — they are the manufacturer's internal call-center decision tree. A general
chat can only *infer* them; an app calling a sanctioned server returns the **authoritative** version.
A partnered server also turns the §9 escalation handoff from best-effort into a real, warranty-aware,
dispatch-integrated transaction:

| Dimension | General LLM chat | Manufacturer-server app |
|-----------|------------------|--------------------------|
| Authority / liability | Hallucinated step, nobody behind it | OEM-sanctioned; brand owns correctness |
| Specificity | Generic per product line | Exact model + firmware + active recalls |
| Closed loop | Dead-ends at advice | Checks warranty, then **creates the dispatch ticket** |
| Feedback | Conversation discarded | Step outcomes flow back, improve the workflow |
| Safety | Best-effort | SafetyGuard (§10) becomes a *contractual* guarantee |

**Real-world feasibility (brief).** The incentive is the avoidable **truck roll** (hundreds of
dollars; a large share preventable — e.g. the curated Samsung `OF OF` demo-mode case). Partner with
**whoever bears that cost**: the OEM in-warranty, or — often a faster first partner — an
extended-warranty / service network (Asurion, Assurant, ServicePower-style) that bears it directly.
The defensible asset is the **normalization layer + a standard MCP server contract** (the resource
and tool shapes) partners implement; the hard parts are B2B sales, liability allocation (answered by
the deterministic SafetyGuard), and the chicken-and-egg of reach-vs-coverage. See BRAINSTORM §5.2.

**How it fits THIS architecture — a swap behind an existing seam.** `lookup_fixes` → `get_fixes`
([grounding.py](../appliance_fixer/grounding.py)) already isolates the data lookup, and decision #4
(one config module per appliance) and #6 (cache expensive reads) already assume the fix source is
pluggable. Productizing = registering the manufacturer's MCP server as an ADK `MCPToolset` so its
workflow-lookup and dispatch tools sit behind `lookup_fixes`, and upgrading `draft_escalation` (§7)
into a real `create_service_request` tool call. ADK speaks MCP natively, so this is configuration,
not a hand-written client. The curated layer stays as the offline fallback — consistent with the §11
unhappy-path rule (*grounding down → curated table*), so an unreachable/erroring server degrades
gracefully rather than hard-failing.

**The capstone demo: mock the server.** A standalone **mock OEM MCP server** (canned fixtures keyed
off the models already in `SUPPORTED_MODELS`), connected to the agent as an `MCPToolset`. MCP maps the
domain cleanly — the manual is authoritative context, the workflow and dispatch are callable tools:

```
get_manual(model)                          → product line, manual_url, warranty status, recalls
get_pre_service_workflow(model, symptom,   → ordered OEM-sanctioned steps (safety flag,
  error_code)                                expected outcome, terminal `dispatch_recommended`)
create_service_request(...)                → ticket id (structured, warranty-aware handoff)
```

The manual is exposed as a tool (`get_manual`) — and optionally an MCP `manual://{model}` resource —
because `MCPToolset` surfaces *tools* to the model, not resources. This scores on the Kaggle agents
track because it demonstrates **agent tool use against an external system over a standard protocol
(MCP)** and makes the **partner integration seam legible** ("product, not prompt"). The
`get_pre_service_workflow` tool is the authoritative form of `SYMPTOM_FIXES`; `create_service_request`
is the authoritative form of the §9 service-ready packet — handed to a partner that can actually
schedule. **Effort ≈ 1 day** (a small MCP server + fixtures, an `MCPToolset` wired into the agent,
curated fallback).

**Governance under the hard rule.** The live partnership is post-capstone. The **mock** is bound by
the §3 hard rule like every optional: it does not start until the core is recorded, and it is **at
most one** gated optional — competing with annotated-photo-out and the before/after loop
([DESIGN_BRAINSTORM.md §2](./DESIGN_BRAINSTORM.md#2-gated-optional-ideas-brainstormed-parked)) for
that single slot. Its edge: it is the strongest direct rebuttal to the "why not just ChatGPT" critique
in the writeup.

---

## 17. Open questions / risks to verify

1. **`next_step` freshness** — persist-on-write (recommended, snappier) vs. compute live per request
   (can't lag if the agent changes state outside the tools).
2. **`awaiting_user` status** — to light up the blue "Awaiting you" badge, `record_step_result`
   should set `awaiting_user` when it logs a step whose outcome is `unsure`/pending. In scope or defer?
3. **Auth boundary** — keep single-user for the capstone demo, or stub a user id?
4. **Inspection-guide grounding** — keep the shot list curated-per-appliance (recommended, cheap,
   deterministic) or attempt live "what does this brand's service portal require" lookup (out of
   v1, external-data risk per §9)?
5. **Video size/length budget** — confirm per-shot caps keep uploads small enough for flaky signal;
   decide max clip length for the demo.
6. **Flutter target for the demo** — record on a physical device or an emulator? (Physical device
   shows the camera moment best; emulator is more reproducible for re-takes.)
7. **Competition track + deadline** — confirm on Kaggle this is the *open-ended* track and the exact
   deadline (sources conflicted: June 30 vs July 6, 2026).
8. **API billing / quota** — adding billing to the AI Studio key is currently blocked; a confirmation
   diagnosis run on full `flash` (with LLM-judge + grounding) is deferred until quota frees up.
9. **Service-API mock as the gated optional** — if the core is recorded in time, is the
   manufacturer-Service-API mock (§16) the right single optional to spend the slot on (strongest
   "not just ChatGPT" rebuttal) versus annotated-photo-out (cheapest visual win)? Decide only after
   the core is on video, per the §3 hard rule.
