# Appliance Fixer — Project Docs

An ADK + Gemini agent that helps a user fix a household appliance: photograph the model
plate, diagnose from the symptom, run a safe clarify-then-diagnose loop, and (if needed)
draft an escalation — all persisted in a resumable case file. Solo capstone for the
Google/Kaggle 5-Day AI Agents Intensive (Vibe Coding), open-ended track.

## Source of truth

**This `docs/` folder is canonical** — edit here. Copies under `~/.gstack/projects/appliance-fixer/`
are historical snapshots from the planning skills and may be stale; do not edit those.

## Index

| Doc | What it is |
|-----|-----------|
| [DESIGN_COMPLETE.md](./DESIGN_COMPLETE.md) | **The whole picture in one place.** Compiles every locked design decision (product, architecture, frontend, diagnosis flow, safety, data model, tests) into a single reference. |
| [BUILD_PLAN.md](./BUILD_PLAN.md) | **Start here to build (current).** Rebuild-from-scratch plan for the Flutter mobile app: 16 individually-testable segments (backend → REST → Flutter → E2E) with per-segment verification, a dependency graph, and the quota strategy. Supersedes IMPLEMENTATION_PLAN.md. |
| [DESIGN_BRAINSTORM.md](./DESIGN_BRAINSTORM.md) | Exploratory thinking behind the design — approaches weighed, alternatives rejected, cross-model brainstorming, parked optional ideas. |
| [DESIGN.md](./DESIGN.md) | Approved design: the camera+memory hook, the 5 premises (premise #2 RESOLVED), approaches considered |
| [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md) | **Start here to build.** Architecture, data model, module map, build order, tasks T1-T8, current status |
| [TEST_PLAN.md](./TEST_PLAN.md) | What to test and where (for /qa-style verification) |
| [SPIKE_RESULTS.md](./SPIKE_RESULTS.md) | Day-0/1 spike results: plate-read 7/8, diagnosis 21/24 -> thin KB, quota learnings |
| [../spikes/datasets/README.md](../spikes/datasets/README.md) | Test datasets (plate photos + 12 symptoms + answer keys) and their provenance |

## Where things stand (2026-06-21)

- Plate-read spike **PASS** (7/8) — perception hook validated; `validate_model` needs O<->0 / I<->1.
- Diagnosis spike **RESOLVED** premise #2 — Gemini-alone ~88% (lite floor), 0 unsafe -> **thin KB**.
- Resume-feasibility spike **pending** — built as the Day 1-2 walking skeleton.
- **Next step:** build the reopen walking skeleton (`case_store.py` + `reopen.py` + minimal agent);
  prove new -> save -> close -> reopen-by-case_id -> recap -> continue end to end.

## Open risks to verify (not yet confirmed)

- **Competition track + deadline.** Confirm on the Kaggle page that this capstone is the
  **open-ended** "build an agent" track (some sources reference a separate fixed "Kaggriculture"
  leaderboard) and the exact deadline (sources conflicted: June 30 vs July 6, 2026). An
  appliance-fixer only counts on the open-ended track.
- **API billing / quota.** Adding billing to the AI Studio key is currently blocked; dev runs use
  free-tier model-bucket switching (e.g. `gemini-2.5-flash-lite`) + the harness's slim modes.
  A confirmation diagnosis run on full `flash` is deferred until quota/billing frees up.
