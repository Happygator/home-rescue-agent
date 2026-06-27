# UI End-to-End Test — Refrigerator Escalation Flow

**Date:** 2026-06-25
**Tester:** Claude (computer-use driving the native Flutter Windows desktop build)
**Goal:** Create a ticket through the application's UI for a refrigerator running at 50 °F (sample
brand + model number), then repeatedly report that each proposed fix didn't work until the agent
prompts to escalate to a professional. Document every step; fix anything broken and rerun.

## Environment under test

- **Backend:** FastAPI server (`app.fast_api_app:app`) launched with the project `.venv`
  interpreter on `http://127.0.0.1:8000`, with `GOOGLE_API_KEY` exported from `GEMINI_KEY.txt`
  so the live Gemini agent (not the fallback) drives the chat.
- **Client:** Flutter **Windows desktop** build (`flutter run -d windows`, pointed at the local
  backend), driven through its real UI via computer-use (screenshots + clicks + typing).
- **Pre-flight check:** Created and deleted a throwaway case via `/start`; the live agent
  responded by asking for brand + model (the GATHER phase), confirming Gemini quota is live.

## Sample data used

- Symptom: "My refrigerator is running at 50°F — way too warm. Both the fridge and freezer
  compartments are warm and I can hear the compressor running."
- Brand: **Samsung**
- Model number: **RF28T5001SR** (a supported model in the grounding table)

---

## Summary of outcome

The escalation flow works end-to-end through the UI: a refrigerator-at-50 °F ticket, created in
the app, walked through three curated DIY fixes one at a time, and — after each was reported as not
working — the agent proactively prompted to escalate and drafted a service email to the correct
brand support address. **Two real defects were found during the first run, fixed, and the test was
re-run clean.**

### Defects found & fixed

1. **Brand/model given in chat were never persisted to an existing case.** The agent had
   `initialize_new_case` (new cases only) and `verify_model_number` (validates, doesn't save), but
   no way to write brand/model/error-code onto a case that already exists. Result: the case stayed
   `brand=null, model=null`, the system prompt's authoritative "Current case state" kept showing
   `Unknown`, and the agent **re-asked for the model number it had just been given**.
   - **Fix:** added an `update_case_facts(brand, model_number, error_code, tool_context)` tool in
     [agent.py](../home_rescue/agent.py) that persists the facts onto the existing case and
     refreshes session state, and amended system-prompt rule 2 to call it (and to never re-ask for a
     fact already provided). Tool registered in `build_agent()`.

2. **Home list showed a stale status badge after escalating.** `NewIssueScreen._start()` opens the
   chat with `Navigator.pushReplacement`, which completes Home's `await push(NewIssueScreen)` future
   *immediately* (while the case is still `intake`). So Home's one `_load()` ran too early and never
   re-fetched when the user returned from the chat where escalation happened — the card kept the
   stale `INTAKE / "New"` badge until an app restart.
   - **Fix:** added an app-wide `RouteObserver` ([nav.dart](../mobile/lib/nav.dart), wired into
     `MaterialApp.navigatorObservers` in [main.dart](../mobile/lib/main.dart)) and made
     `HomeScreen` `RouteAware` so `didPopNext()` re-fetches whenever Home becomes visible again —
     robust across the pushReplacement flow and the card-tap flow.

Codex was tried first per the global "use Codex for code generation" rule; it stalled (replied
"which file should I change?" despite the file being named — a known failure mode for this repo), so
the edits were applied directly.

### Verification after fixes
- Backend pytest suite: **81 passed**.
- Flutter widget tests: **36 passed**.
- `flutter analyze` on changed files: no issues.
- Clean UI re-run (`case-71d05db5`): persisted `Samsung · RF28T5001SR`, agent never re-asked,
  proposed 3 fixes one at a time, escalated after they were exhausted, and the Home card updated to
  **ESCALATED** immediately on return — no restart needed.

---

## Steps (detailed)

### Run 1 — first attempt (exposed defect #1)

1. Launched the FastAPI backend with the `.venv` interpreter and `GOOGLE_API_KEY` from
   `GEMINI_KEY.txt`; launched the Flutter **Windows desktop** build pointed at it.
2. Pre-flight: created+deleted a throwaway case via `/start`; the live agent asked for brand/model,
   confirming Gemini quota is live (not the offline fallback).
3. In the app: **Home → + (New Issue)**. Typed the symptom (refrigerator at 50 °F, both
   compartments warm, compressor running). **Start diagnosis** → case `case-2d8953a0` created,
   status DIAGNOSING; agent auto-asked for brand + model.
4. Replied "It's a Samsung, model number RF28T5001SR. There's no error code on the display."
5. Agent proposed Fix #1 (vacuum the condenser coils).
6. Replied that it didn't work. **BUG:** agent responded "Please tell me the brand and model number
   of your refrigerator" — re-asking for facts already given. Backend showed `brand=null,
   model_number=null` despite step 4. → Root-caused and fixed (defect #1). Backend restarted.

### Run 2 — after defect #1 fix (exposed defect #2)

7. **Home → + (New Issue)** → same symptom → **Start diagnosis** → case `case-5b21ff37`, DIAGNOSING;
   agent asked for brand/model.
8. Replied with Samsung / RF28T5001SR. Verified backend now persisted `brand=Samsung,
   model=RF28T5001SR` (the new `update_case_facts` tool fired). Agent proposed Fix #1 (condenser
   coils) instead of re-asking.
9. Reported Fix #1 didn't work → agent proposed Fix #2 (check the condenser fan spins freely).
10. Reported Fix #2 didn't work → agent proposed Fix #3 (inspect the compressor start relay).
11. Reported Fix #3 didn't work / "none of these worked" → **agent prompted escalation:** *"It looks
    like we've exhausted all the safe fixes. I've drafted an escalation email to support@samsung.com
    for your Samsung RF28T5001SR refrigerator, along with an inspection video guide…"* Backend
    confirmed `status=escalated`, 3 steps recorded `not_resolved`, escalation drafted to
    `support@samsung.com`.
12. Returned to Home. **BUG:** the escalated case still showed an `INTAKE / "New"` badge and did not
    refresh even after waiting. → Root-caused and fixed (defect #2). App rebuilt/restarted.

### Run 3 — after both fixes (clean pass)

13. **Home → + (New Issue)** → same symptom → **Start diagnosis** → case `case-71d05db5`,
    DIAGNOSING; agent asked for brand/model.
14. Replied with Samsung / RF28T5001SR → agent proposed Fix #1 (condenser coils).
15. "didn't work" → Fix #2 (condenser fan).
16. "didn't work either" → Fix #3 (compressor start relay).
17. "none of these fixes have worked" → **agent prompted escalation:** *"I have drafted an escalation
    email to support@samsung.com and prepared an inspection video guide… Please share these with
    Samsung support."*
18. Returned to Home → the case immediately showed **"Samsung · Refrigerator — RF28T5001SR —
    ESCALATED — updated just now"** with the "Pro service required" next-step. No restart needed.
    ✅ Both fixes validated; full requested flow works end-to-end through the UI.

### Follow-up enhancement — escalation messaging + hand-off (2026-06-25)

Feedback: at escalation the agent just said "I've prepared an escalation draft…", the draft wasn't
visible from the chat, and there was no clear path to it. Changed:

1. **Prompt** ([agent.py](../home_rescue/agent.py) rule 4): on escalation the agent now (a)
   states *why* it is escalating — naming the specific safe fixes tried and that they didn't resolve
   it (or the safety reason) — and (b) offers to set up professional service. It no longer pastes the
   draft or claims it is shown in the chat.
2. **In-chat hand-off CTA** ([issue_detail_screen.dart](../mobile/lib/screens/issue_detail_screen.dart)):
   once a case is `escalated`, a "Ready for a professional" card with a **"Set up professional
   service →"** button renders in the chat and opens the Service-packet screen (the info-gathering
   screen: drafted message + guided inspection video + Contact). 
3. **Live status refresh**: `_send()` / photo turns now re-fetch the case after the agent turn, so
   the status badge flips to ESCALATED and the CTA appears immediately (previously the detail screen
   kept the stale pre-escalation status until reopened).

Verified in the UI (`case-43088eea`): the agent's reason-stating message, the inline CTA, the live
ESCALATED badge, and the CTA opening the Service-packet screen with the fully-rendered drafted email
(symptom + all 3 steps-tried). Backend pytest **81 passed**, Flutter **36 passed**.

### Follow-up enhancement — schema-based symptom router (option 2, reversible) (2026-06-25)

Feedback: routing the symptom to a curated fix bucket via pure keyword matching
(`grounding._match_symptom_key`) is brittle — e.g. "running at 50F" contains no keyword and falls
through to the generic fallback list. Prototyped and implemented **option 2: an LLM extracts a
structured feature schema, then a pure deterministic table routes that to a bucket.** The curated,
safety-reviewed fix lists are untouched — only the *router* changed.

- **New module** [symptom_router.py](../home_rescue/symptom_router.py):
  - `SymptomFeatures` (enum schema: warm_compartment, abnormal_noise, compressor_running,
    runs_constantly, water_pooling, ice_maker_problem, frost_buildup).
  - `extract_features()` — the only non-deterministic part: a Gemini structured-output call
    (`response_schema`); returns `{}` on any error so the caller can fall back.
  - `route_features()` — PURE, unit-tested decision table → bucket key or `None`.
  - `classify_symptom()` — toggle + extract + route, with a **graceful keyword fallback** (so the
    schema router is never *worse* than keyword on coverage) and per-(symptom,code) caching.
- **Seam:** `get_fixes()` gained an optional `symptom_key` override (default sentinel = unchanged
  keyword behavior, so every existing test and pure caller is byte-for-byte identical);
  `agent.lookup_fixes` resolves the bucket via the router when active.
- **Reversible toggle:** env `SYMPTOM_ROUTER` — `schema` (default, new) or `keyword` (legacy).
  Flip to `keyword` to revert instantly with no code change.

**Verification:**
- 7 new unit tests (pure table, toggle, keyword-fallback, `get_fixes` override) + full backend
  suite: **88 passed**.
- **Live Gemini A/B** on keyword-free symptoms — schema router strictly beats keyword:
  - "fridge sits at 50 degrees, food spoiling" → schema `fresh_food_warm_freezer_fine` / keyword `None`
  - "never shuts off, hums all day" → schema `runs_constantly` / keyword `None`
  - "puddle at the bottom shelf" / "no ice from the dispenser" → both routers agree.

### Notes / observations
- The in-chat **Case summary** card (model + Next-step) is rendered from the snapshot loaded when
  the chat screen opened, so during a single chat session it can lag behind (e.g. still says "Model:
  not identified yet" after the model is saved mid-conversation). The underlying data is correct and
  the card is accurate on the next open. This is cosmetic and was left as-is; only the Home-list
  staleness (defect #2), which persisted across navigation, was fixed.
- Test artifacts left in the dev DB from this exercise: `case-2d8953a0` (Run 1, diagnosing),
  `case-5b21ff37` and `case-71d05db5` (escalated). They can be deleted from the Home list (⋮ →
  Delete) if a clean slate is wanted.
