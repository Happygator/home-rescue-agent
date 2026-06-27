# App Specification

*Proposed functionality & workflow. Stack: Google ADK + Gemini 2.5 Flash (multimodal) · SQLite · FastAPI · MCP · Flutter (iOS + Android).*

---

## What it does

A phone app that takes a user from **"my appliance is broken"** to a **safe fix** — or, when a pro
is truly needed, to a **first-call-ready service handoff** — with the whole repair saved so it can
be paused and resumed.

Four hooks:

1. **Camera diagnosis** — point the phone at the spec plate + the symptom; Gemini reads the exact
   model number and error code, and names the likely fault.
2. **A repair that remembers** — every case is a saved file. Stop tonight, resume tomorrow with full
   continuity.
3. **A handoff that gets you scheduled** — when fixes run out, the app builds a **service-ready
   packet** (model + error + steps tried + a guided inspection video) so the *first* call to the
   repair company can book a technician.
4. **Manufacturer-backed fixes** — instead of generic advice, the app connects to a manufacturer-hosted
   **MCP server** for direct, standardized access to the brand's authoritative manuals (as context) and
   the exact pre-service diagnostic tools it runs before dispatching a technician.

---

## End-to-end workflow

```
   ┌─────────────┐
   │  NEW REPAIR │  tap "+" → describe it (+ optional photo)
   └──────┬──────┘
          ▼
┌──────────────────────────────┐
│ 1. GATHER                    │   optional photo → Gemini reads plate / symptom
│   appliance · brand · model  │   ask for anything still missing (in chat)
│   · symptom · error code     │   status: intake → diagnosing
└──────────────┬───────────────┘
               ▼
┌──────────────────────────────┐
│ 2. FIX LOOP                  │◀─────────────┐
│   propose ONE safe fix →     │              │  another safe
│   user tries it →            │              │  fix to try
│   "did it work?" (yes/no)    │              │
└──────────────┬───────────────┘              │
               ▼                              │
          resolved? ── yes ──▶ ✅ DONE (case closed)
               │ no                           │
               ▼                              │
        more safe fixes? ── yes ──────────────┘
               │ no   (or safety stop forces it)
               ▼
┌──────────────────────────────┐
│ 3. ESCALATE                  │   draft message (model + symptom + steps tried)
│   service-ready handoff      │   guide a shot-by-shot inspection video
│                              │   assemble packet → user shares it
└──────────────────────────────┘
```

**Safety stop:** at any point in the loop, a deterministic guard blocks dangerous work (gas,
mains electrical, refrigerant, water-on-electrics), shows a clear "this needs a pro" message, and
jumps straight to escalation — with the packet still produced.

---

## App screens

| Screen | What it shows |
|--------|---------------|
| **Home — My Repairs** | List of unresolved cases (newest first): title, status badge, last symptom, a **`Next →`** step, and **Continue**. "+ New Repair" opens a composer (describe the problem + an optional photo). |
| **Repair / Chat** | Live agent chat + a collapsible case summary (symptom, diagnosis, steps as a checklist, next step, **Escalate** button). Camera button for plate/symptom photos. |
| **Escalation / Inspection** | The drafted message + a guided video capture ("Shot 2 of 4: show the display with the E1 code"), then assembles the packet and offers **Share**. |

**Status colors:** `intake` grey · `diagnosing` amber · `awaiting you` blue · `escalated` red ·
`resolved` green.

---

## The service-ready packet

```
   fixes exhausted / safety stop
            │
            ▼
   draft escalation message  ─┐
   (model · error · steps)    │
                              ├──▶  PACKET  ──▶  share (email / messages / portal)
   guided inspection video  ─┘     model + error + steps tried + diagnosis + video
   (shot-by-shot in-app)
```

Everything is **prepared, not auto-sent** — the user shares it via the phone's native share sheet.

---

## Manufacturer MCP server

Instead of generic advice, the agent connects to a **manufacturer- (or warranty-network-) hosted MCP
server** for the brand's *authoritative* manual and **pre-service workflow** — the exact steps a brand
runs before it dispatches a technician. The steps are sanctioned, model-specific, and end in a real
dispatch. This is what separates the app from a generic chatbot.

**Why MCP, not a custom API.** ADK speaks MCP natively, so a manufacturer's server drops into the agent
through `MCPToolset` with no per-brand glue code — and the protocol matches the shape of the problem:
manuals are **resources** (text served straight into the model's context) and the pre-service actions
are **tools** (workflow lookup + dispatch the agent can call). The ADK agent is the **MCP client**
(hosted in the FastAPI backend, not the phone); the manufacturer runs the **MCP server** on its own
infrastructure.

**What a manufacturer exposes:**

- **Resources — authoritative knowledge.** The exact manuals and decision trees the model reads to
  understand an error code or symptom. The generic server maps a directory (e.g. `/data/manuals/`) or a
  document database to the protocol; brands drop in PDFs, Markdown, or JSON flowcharts with no custom
  formatting. The agent requests the manual for the scanned model and the server returns the relevant
  text to the model's context window.
- **Walkthrough tools — the "virtual technician."** The agent reads the brand's troubleshooting tree
  (e.g. "fridge warm → check door seal → unplug 30s") and turns each step into an interactive check,
  prompting the user ("did you hear a click?") or the camera ("point at the door seal"). This rules out
  basic human-fixable causes — unplugged units, blocked vents, unsealed doors — before a technician is
  dispatched.
- **Dispatch tool.** When the walkthrough is exhausted, the agent books the technician through the
  server, attaching the model, error, and the result of every check the user ran.

The capstone **mocks** this server (a standalone MCP server the agent connects to as a toolset):

```
   ADK Agent ──MCP──▶  Mock OEM MCP server
   (MCPToolset)        ├─ resource  manual://{model}                → manual, warranty, recalls
                       ├─ tool      get_pre_service_workflow(model) → sanctioned ordered steps
                       └─ tool      create_service_request(...)     → dispatch ticket
                       (falls back to the curated table if the server is unreachable)
```

Plugs in behind the existing `lookup_fixes` step, so no change to the agent loop.

**Deployment & privacy.** The MCP server runs on the manufacturer's own servers — we never host or
bulk-copy their data. Proprietary manuals and troubleshooting logic are read transiently for the active
repair only, never stored in CaseStore. Onboarding is a pre-built generic server wrapper a brand points
at its manuals folder to make its appliances "AI-ready."

---

## Architecture at a glance

```
   Flutter app  ──REST + SSE──▶  FastAPI  ──▶  ADK Agent (Gemini 2.5 Flash)
   camera · video · share                          │        ▲
                                                   │        │ SafetyGuard
                                       tool calls  │        │ (blocks danger →
                                                   ▼        │  forces escalate)
        read_plate · validate_model · lookup_fixes · record_step ·
        draft_escalation · inspection_guide · reopen_case
                                                   │
                                                   ▼
                                    CaseStore (SQLite) — one row per repair
                                    (the saved, resumable case file)
```

- **Gemini 2.5 Flash** does two jobs: drives the chat/agent loop, and reads the spec plate from a
  photo (vision).
- **CaseStore** is the app's memory — a SQLite table with **one row per repair**. Each row holds the
  appliance, brand, model, status, and a JSON case file (symptom, error code, every step tried and
  its outcome, diagnosis, escalation). Every tool writes through it, so the repair is saved as it
  happens. Reopening a repair = loading that row and replaying a plain-text **recap** into a fresh
  chat, which is how the agent "remembers" a case across sessions.
- **Manufacturer MCP server** backs `lookup_fixes` and the dispatch step through ADK's `MCPToolset`:
  manuals arrive as MCP resources, the pre-service workflow and dispatch as MCP tools, with the
  curated fixes table as the offline fallback.
