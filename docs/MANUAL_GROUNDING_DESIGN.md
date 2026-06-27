# Manual Troubleshooting Grounding — Design

Status: PROPOSED · 2026-06-25
Scope: how the per-model **error-code → fix** troubleshooting data behind the mock OEM MCP server
is **obtained**, **stored**, and **used**, so the user never has to open the paper/PDF manual.
Seed targets: **Samsung refrigerator RF28T5001SR** and **LG dishwasher LDFC2423V**.

Related: [DESIGN_COMPLETE.md §16](./DESIGN_COMPLETE.md) (the manufacturer-MCP mock + its tool contract) ·
[BUILD_PLAN.md](./BUILD_PLAN.md) (gated optionals) ·
[grounding.py](../home_rescue/grounding.py) · [appliances/fridge.py](../home_rescue/appliances/fridge.py).

---

## 0. TL;DR

1. **The "mock MCP server" already has a contract.** It is the gated mock OEM server from §16:
   `get_manual(model)`, `get_pre_service_workflow(model, symptom, error_code)`,
   `create_service_request(...)`, wired as an ADK `MCPToolset` *behind* `lookup_fixes` → `get_fixes`,
   with the curated `appliances/*.py` tables as the offline fallback. "Populating it with manuals"
   means authoring the **fixtures** those tools return for each model — it does **not** mean storing PDFs.
2. **What we actually store is a distilled, safety-graded error-code table + a manual *reference***
   (title, URL, revision, page), never the full manual text. The agent reads the table, not the manual.
3. **Obtain by build-time curation, not runtime scraping** — OEM manual / OEM support pages are the
   authoritative source for code *meanings*; reputable repair DBs (iFixit / RepairClinic) rank the
   *fixes*. Every row carries a `source` citation and a DIY-vs-pro `safe` flag, and is reviewed + eval-gated.
4. **Generalize the data layer beyond fridges.** Today everything lives in one fridge-only module.
   Add `appliances/dishwasher.py` and an **appliance registry**, keyed `appliance → brand → code`,
   so the LG dishwasher is "one new file" (decision #4) and `get_fixes` becomes appliance-aware.
5. **Never guess.** An out-of-table code resolves to a *cited manual reference* step
   (e.g. a Samsung fridge → "look this code up on p.65 of the service manual"), never an invented
   meaning — extending the existing rule in
   [fridge.py](../home_rescue/appliances/fridge.py) (`CORRECTIONS.out_of_table_code`).

---

## 1. Where this fits in the existing architecture

```
 user turn ──► ADK agent ──► lookup_fixes(appliance, brand, model, symptom, error_code)
                                   │            (tool surface — unchanged)
                                   ▼
                              get_fixes(...)        ◄── grounding.py: the single seam
                              ┌───────────────┐
                              │ 1 cache hit   │  case.data.cache.grounded_fixes
                              │ 2 MCP server  │  get_pre_service_workflow()  ← mock OEM server (§16)
                              │ 3 curated KB  │  appliances/<type>.py  ERROR_CODES / SYMPTOM_FIXES
                              │ 4 manual ref  │  out-of-table code → "see manual p.N" (no guess)
                              │ 5 safe trio   │  generic fallback
                              └───────────────┘
```

The **mock MCP server** is the productized face of layers 2–3: its `get_pre_service_workflow` *is*
the authoritative form of `SYMPTOM_FIXES`/`ERROR_CODES`, and `get_manual` *is* the manual reference.
Per §16 the curated KB stays as the offline fallback, so an unreachable server degrades gracefully
rather than hard-failing. **This design fills in the data that both the curated KB and the mock
server's fixtures serve** — they share one source of truth (§5), so we curate once.

> Note on appliance #2: the request said "Whirlpool Dishwasher, LFXS26973S," but that model number
> is an **LG** French-door fridge in our own `SUPPORTED_MODELS`. Confirmed with the user via the spec
> plate — the real target is an **LG dishwasher, model `LDFC2423V`** (S/N 409KWCF1Y587). This is the
> first **non-refrigerator** appliance, so the data layer must generalize (§5, §9).

---

## 2. Design principles (inherited + extended)

| Principle | Source in code | What it means for this data |
|---|---|---|
| **Never guess** an out-of-table code | `CORRECTIONS.out_of_table_code` | Unknown code → cited manual reference, never an invented meaning. |
| **Safety-gated** | `safety.py`, `SAFETY_RULES` | Every fix carries `safe: true/false`. `false` ⇒ not surfaced as a DIY step; escalate. |
| **Ranked easiest/safest first** | `SYMPTOM_FIXES` ordering | Fix lists are ordered; the agent walks them via `next_step`/`record_step_result`. |
| **Cited provenance** | *new* | Every code + fix row carries a `source`; every model carries a `manual` reference. |
| **Deterministic + cached** | decision #6, `cache.grounded_fixes` | Curation is build-time; lookups are pure-table; results cache per case. |
| **Degrade to curated** | §11 unhappy-path rule | MCP server down → curated table; table miss → manual ref → safe trio. |

---

## 3. How the troubleshooting info is best **obtained**

### 3.1 Source hierarchy (most authoritative first)

1. **OEM owner's + service manual** — the *authoritative* error-code table and DIY-vs-service split.
   - Samsung RF28T5001SR **user** manual (204 pp; troubleshooting p.57, abnormal sounds p.61) — note the
     consumer manual is symptom-based; the numeric **C-code table is in the separate service manual**
     (Self-Diagnostic p.63, codes from p.65).
   - LG LDFC2423V owner's manual (LG support hub `LDFC2423V.APZEEUS`) + the LG support **error-code
     list** and **per-code help-library** pages (IE, OE, FE, LE/CE, tE, HE, AE/E1, bE, CL, PF, nE),
     which give the official meaning and the first-line fix. (Verified 2026-06-25 — this is how the
     `bE`/`CL` correction below was caught: `bE` is a suds error, `CL` is the lock.)
2. **OEM support / help-library pages** — same authority as the manual, easier to cite per code, and
   often clearer on "what the user should try first."
3. **Reputable third-party repair DBs** (iFixit, RepairClinic, brand-independent appliance techs) —
   used **only to rank and phrase the DIY fixes**, never to invent a code's meaning. These mirror how
   `SYMPTOM_FIXES` is already "grounded in iFixit/RepairClinic" (see fridge.py comment).

### 3.2 Extraction method — build-time curation, **not** runtime scraping

We do **not** fetch or scrape manuals at request time. Each model is curated once, offline, into the
schema in §5. Reasons:

- **Licensing/ToS** — manuals are copyrighted; we store a *reference + our own distilled table*, not
  the manual text. Redistributing PDF text at runtime is a legal risk; a short factual code table +
  a link is defensible and is what a call-center agent would read out anyway.
- **Safety review** — every fix must pass a human/`SAFETY_RULES` check before a user sees it. A live
  scrape can't be vetted. (A scraped "replace the heating element" step must be downgraded to
  `safe:false` → escalate; only a review pass catches that.)
- **Determinism + offline** — the spike showed a thin, curated KB is enough (Gemini-alone ≈88%);
  build-time data keeps lookups pure, cacheable, and demo-safe with no live dependency or quota.
- **Latency/quota** — no network or model call on the hot path for a known code.

### 3.3 Curation pipeline (per model)

```
collect ─► extract ─► classify safety ─► rank ─► cite ─► review ─► load ─► eval
  │          │            │               │       │        │         │       │
 OEM       code →       DIY-safe vs      easiest  source   human/   into    plate+
 manual    meaning      pro-only         /safest  URL +    SAFETY_  appliance diagnosis
 + LG       + first     (maps to         first    manual   RULES    module   eval
 support    fix         SAFETY_RULES)             page     pass              fixtures
```

- **classify safety** is the load-bearing step. Map each fix to `SAFETY_RULES`: anything touching
  mains voltage, the sealed refrigerant system, gas, the heating element, or water-on-live-parts ⇒
  `safe:false` ⇒ it becomes an *escalation*, not a step. (E.g., LG **HE** = heater error ⇒ heating-element
  territory ⇒ pro.)
- **cite** — record the exact source per row so the writeup, the `get_manual` fixture, and any future
  audit can trace it. An uncitable "fix from a forum" does not go in.
- **eval** — extend the existing fixtures (`tests/evals/fixtures/`) with diagnosis cases for the new
  codes/symptoms so a regression in the table is caught (matches the project's eval discipline).

### 3.4 What is "the manual" in storage terms

Not the PDF. For each model we store a **`MANUAL` reference record** — `{title, source_url, revision,
retrieved_at, pages:{...}}` — plus the distilled `ERROR_CODES`/`SYMPTOM_FIXES`
rows. This is exactly what `get_manual(model)` returns (§16: *product line, manual_url, warranty,
recalls*), and it lets the out-of-table fallback say "see this code on p.65 of your service manual"
(Samsung) or "see the LG support page for this code" without ever shipping manual text.

---

## 4. How the information should be **stored**

### 4.1 Generalize the layer: one module per appliance + a registry

Today: a single `appliances/fridge.py` with module-level dicts and `APPLIANCE = "refrigerator"`.
`grounding.py` imports it directly. To add a dishwasher we introduce an **appliance registry** so
`get_fixes` can resolve by appliance type (decision #4: "add an appliance = one file").

```
home_rescue/appliances/
  __init__.py        # REGISTRY = {"refrigerator": fridge, "dishwasher": dishwasher}
  fridge.py          # existing tables (unchanged shape)
  dishwasher.py      # NEW — same shape, dishwasher data
  schema.py          # NEW — dataclasses/validation for the record types below
```

`grounding.py` changes from `from .appliances import fridge` to a registry lookup:
`module = REGISTRY.get(normalize_appliance(appliance), fridge)` — fridge stays the default so every
existing fridge caller is unaffected (backward compatible).

### 4.2 Record schemas (provenance-bearing)

These formalize the shapes already in `fridge.py` and add `source`/`manual` provenance. Storage stays
as Python module constants (matches the codebase + decision #4); `schema.py` validates them at import.

```python
# Error code record  (ERROR_CODES[brand][code])
{
  "meaning": str,            # authoritative, from OEM manual/support — never invented
  "safe": bool,             # True ⇒ DIY steps may be surfaced; False ⇒ escalate (pro)
  "fixes": [str, ...],      # ranked easiest/safest first; only DIY-safe steps
  "fault_class": str,       # routes inspection shots: "airflow_defrost" | "sealed_system"
                            #   | "drain" | "fill" | "motor" | "heater" | "leak" | "default"
  "source": str,            # citation URL/section — REQUIRED
}

# Symptom record  (SYMPTOM_FIXES[symptom_key])  — unchanged shape, + parallel SOURCES map
"symptom_key": [str, ...]    # ranked DIY fixes

# Manual reference record  (MANUALS[brand][model])  → backs get_manual(model)
{
  "product_line": str, "manual_url": str, "revision": str, "retrieved_at": str,
  "manual_url_variant": str | None,        # optional second copy (e.g. Samsung /AA)
  "warranty_note": str | None, "recalls": [str, ...],
  # pages is a free-form {section_label: page_number} map — labels differ by source:
  #   Samsung user manual → {"user_troubleshooting": 57, "user_abnormal_sounds": 61}
  #   Samsung service manual → {"service_self_diagnostic": 63, "service_error_codes": 65}
  #   LG (codes live on support pages, not a page number) → {} / all None
  "pages": {str: int},
}
```

Plus the existing per-appliance constants, now authored per module:
`SUPPORTED_MODELS`, `MODEL_PATTERNS`, `SUPPORT_CONTACTS`, `INSPECTION_SHOTS`, `SAFETY_RULES`,
`CORRECTIONS`, `CLARIFYING_HINTS`, `APPLIANCE`.

### 4.3 One source of truth for both the curated KB and the MCP fixtures

The mock MCP server does **not** get a second copy of the data. Its fixtures are **projections** of
the appliance modules:

| MCP tool | Returns | Built from |
|---|---|---|
| `get_manual(model)` | product line, manual_url, warranty, recalls | `MANUALS[brand][model]` |
| `get_pre_service_workflow(model, symptom, error_code)` | ordered steps, `safe` flag, terminal `dispatch_recommended` | `ERROR_CODES` / `SYMPTOM_FIXES` (+ `safe:false` ⇒ `dispatch_recommended`) |
| `create_service_request(...)` | ticket id | `SUPPORT_CONTACTS` + the §9 packet |

So "populating the MCP server" = authoring the appliance modules; the fixture file is a thin adapter
(`tests/fixtures/mcp/<model>.json` generated from the modules), keeping curated + mock in lockstep.

---

## 5. How the information should be **used** at runtime

The agent **never reads the manual**. It calls `lookup_fixes`, and `get_fixes` resolves to vetted,
ranked, safety-graded steps via the ladder in §1:

1. **Cache** — `case.data.cache.grounded_fixes` (decision #6).
2. **MCP `get_pre_service_workflow`** (when the mock/real server is wired) — authoritative OEM steps.
3. **Curated `ERROR_CODES[brand][code]`** — when there's an error code in the table.
4. **Out-of-table code → manual reference** — `error_code_meaning` returns `None`, so `get_fixes`
   emits a single safe step citing the manual reference from `MANUALS[...]` (a Samsung fridge cites the
   service-manual code page p.65; an LG dishwasher cites the LG support code page). **No guessed
   meaning** — this is the `CORRECTIONS.out_of_table_code` rule.
5. **Symptom path** — keyword/`symptom_router` → `SYMPTOM_FIXES[key]`.
6. **Generic safe trio** — last-resort fallback.

Cross-cutting:

- **Safety gate.** A `safe:false` code (e.g. LG **HE**) never yields a DIY step; `get_fixes` returns
  the escalation path and `safety.py` remains the defense-in-depth backstop. `next_step.py` surfaces
  "pro service required."
- **Per-appliance inspection shots.** Escalation video guidance comes from the module's
  `INSPECTION_SHOTS` keyed by `fault_class` (e.g. a dishwasher **OE** drain fault → a `drain` shot
  list: filter/coin-trap, drain hose, disposal knockout), so the §9 packet is appliance-correct.
- **Caching.** First successful resolution writes `grounded_fixes` so subsequent turns are free.
- **The agent's job is narration, not lookup.** It explains and sequences the vetted steps; it must
  not author repair facts — that keeps liability inside the curated/cited layer (the §16 governance point).

---

## 6. Worked seed data

### 6.1 Samsung refrigerator `RF28T5001SR` (already a supported model)

`RF28T5001SR` is already in `SUPPORTED_MODELS["SAMSUNG"]`. We add its manual reference and keep the
existing curated Samsung codes; numeric `C`-codes are added **only where a source confirms meaning +
safety**, otherwise they ride the out-of-table → manual-reference path.

```python
# appliances/fridge.py  (additions)
MANUALS["SAMSUNG"]["RF28T5001SR"] = {
    "product_line": "36\" French-Door Refrigerator (28 cu. ft.)",
    # Verified User Manual (204 pp, EN/ES/FR) on ManualsLib; /AA is the US-variant copy.
    "manual_url": "https://www.manualslib.com/manual/2671356/Samsung-Rf28t5001.html",
    "manual_url_variant": "https://www.manualslib.com/manual/2725689/Samsung-Rf28t5001sr-Aa.html",
    "revision": "User Manual (ManualsLib doc 2671356), verified 2026-06-25", "retrieved_at": "2026-06-25",
    "warranty_note": "1 yr parts/labor; 10 yr digital inverter compressor (verify per unit).",
    "recalls": [],
    # The CONSUMER user manual is symptom-based: general troubleshooting p.57, abnormal sounds p.61.
    # The numeric C-code TABLE lives in the separate SERVICE manual (Self-Diagnostic p.63, codes p.65).
    "pages": {"user_troubleshooting": 57, "user_abnormal_sounds": 61,
              "service_self_diagnostic": 63, "service_error_codes": 65},
}

# ERROR_CODES["SAMSUNG"] — KEEP existing demo-mode rows (authoritative, safe):
#   "OF OF"/"OFF" → Demo/Showroom mode → hold Power-Freeze + Freezer 3-5 s.  (safe: True)
# Add the well-sourced service-only example:
ERROR_CODES["SAMSUNG"]["C26"] = {
    "meaning": "Defrost thermal fuse fault (defrost circuit open).",
    "safe": False,                       # part replacement (DA47-00301B) — NOT DIY
    "fixes": [],                          # no DIY steps → escalate
    "fault_class": "airflow_defrost",
    "source": "Samsung service manual error-code table (p.65); iFixit RF28T5001SR.",
}
# Any code NOT added here (e.g. transient "21 C", "C8") → error_code_meaning() = None
#   → get_fixes emits: "Look up code <X> on p.65 of your manual." (no guessed meaning)
```

The point this illustrates: **demo-mode = DIY-safe and resolved in one step; a defrost-fuse code =
pro**, and *unknown* numeric codes are sent to the manual page rather than guessed — three distinct
handlings from one table.

### 6.2 LG dishwasher `LDFC2423V` — **new appliance module**

This is the generalization. New file, same shapes; `APPLIANCE = "dishwasher"`; codes from the LG
support help-library (one page per code) with safety classification applied.

```python
# appliances/dishwasher.py  (new)
APPLIANCE = "dishwasher"

SUPPORTED_MODELS = {"LG": ["LDFC2423V", "LDFN4542", "LDP6810"]}      # seed; extend as curated
MODEL_PATTERNS   = {"LG": r"^L[DT][A-Z0-9]{3,}"}                     # LDF.., LDP.., LDT..
SUPPORT_CONTACTS = {"LG": {"name": "LG", "email": "support@lg.com", "phone": "1-800-243-0000"}}

MANUALS = {"LG": {"LDFC2423V": {
    "product_line": "LG Front-Control Dishwasher w/ QuadWash (LDFC2423V.APZEEUS)",
    # Support hub for this exact model (plate suffix APZEEUS); Owner's Manual PDF (EN, 8.4 MB,
    # dated 2023-09-11) + Online Manual (2025-05-15) + spec sheet are the download buttons here.
    "manual_url": "https://www.lg.com/us/support/product-help/LDFC2423V.APZEEUS",
    "revision": "Owner's Manual 2023-09-11 (LG support, verified 2026-06-25)", "retrieved_at": "2026-06-25",
    "warranty_note": "1 yr parts/labor; 10 yr direct-drive motor (verify per unit).",
    "recalls": [],
    # The error-code table is documented across LG's per-code support pages, not a manual page number.
    "pages": {"self_diagnostic": None, "error_codes": None},
}}}

# error code -> meaning + safety class + ranked DIY fixes + fault_class + source
# Meanings + steps verified against LG US support on 2026-06-25 (see SOURCES, URLs below).
_LG_LIST = "https://www.lg.com/us/support/help-library/lg-dishwasher-error-code-list-CT10000009-20150933422943"
ERROR_CODES = {"LG": {
    # --- not faults (DIY, one step) ---
    "CL": {"meaning": "Child Lock / Control Lock is ON (not a fault).", "safe": True,
           "fixes": ["Open the door, press POWER, select a cycle, then hold RINSE and SPRAY together "
                     "for 3 seconds to turn Control Lock off."],
           "fault_class": "default", "source": _LG_LIST},
    "bE": {"meaning": "Suds/detergent error — wrong detergent or the unit is not level (NOT a lock code).",
           "safe": True,
           "fixes": ["Use ONLY dishwasher detergent (never dish-washing liquid), filled to the line.",
                     "Confirm the dishwasher is level.",
                     "To clear existing suds, place 4-7 oz of milk in a bowl on the upper rack and run AUTO."],
           "fault_class": "default", "source": _LG_LIST},
    "PF": {"meaning": "Power-failure protection after an outage/interruption (not a fault).", "safe": True,
           "fixes": ["Press any control-panel key to clear PF after power is restored.",
                     "Confirm the unit is on a dedicated grounded 120V/60Hz/15A+ circuit, no extension cord."],
           "fault_class": "default", "source": _LG_LIST},
    # --- DIY-fixable water-path faults ---
    "IE": {"meaning": "Fill error - water did not reach level after ~10 minutes of filling.", "safe": True,
           "fixes": ["Confirm the water-supply valve under the sink is fully ON.",
                     "Straighten any kinked fill line; confirm house water pressure (20-120 PSI).",
                     "Make sure the drain-hose outlet is 10+ inches above the dishwasher base.",
                     "In cold weather, check for frozen supply components; level the unit; "
                     "remove flood-safe hoses if present."],
           "fault_class": "fill", "source": _LG_LIST},
    "OE": {"meaning": "Drain error - the dishwasher is not draining properly.", "safe": True,
           "fixes": ["Clean the bottom filter / coin trap.",
                     "Check the drain hose for kinks or blockages; confirm a tight seal at the connection.",
                     "If newly installed, confirm the garbage-disposal knockout plug was removed; "
                     "clear sink-disposal clogs."],
           "fault_class": "drain",
           "source": "https://www.lg.com/us/support/help-library/oe-error-code-dishwasher--20150986144736"},
    # --- leak family (LG steps are partly DIY, escalate if it recurs) ---
    "AE": {"meaning": "Leak detected - water reached the base and tripped the float switch (also shows as E1).",
           "safe": False,
           "fixes": ["Confirm the unit is level (water pools to one side if not).",
                     "Clean the door gasket; inspect for damage; clear/inspect the spray arms.",
                     "Use only dishwasher detergent, correct amount (excess suds can trip the float).",
                     "Turn the breaker OFF, remove the kick plate, dry the drain pan, allow 24-48h to "
                     "evaporate, then reset. If the leak recurs, book service."],
           "fault_class": "leak",
           "source": "https://www.lg.com/us/support/help-library/ae-e1-error-code-dish-washer--20150140935066"},
    "E1": {"meaning": "Leak detected (same float-switch trip as AE).", "safe": False,
           "fixes": ["Follow the AE steps: level, gasket/spray-arm check, correct detergent, "
                     "dry the drain pan 24-48h, then reset. If it recurs, book service."],
           "fault_class": "leak",
           "source": "https://www.lg.com/us/support/help-library/ae-e1-error-code-dish-washer--20150140935066"},
    "FE": {"meaning": "Overfill - too much water detected; the drain pump turns on automatically.",
           "safe": False,
           "fixes": ["Power OFF, switch the circuit breaker OFF for 10 seconds, restore power, restart.",
                     "If FE returns, the inlet valve is likely stuck open - book service."],
           "fault_class": "fill", "source": _LG_LIST},
    # --- pro-only electrical/thermal/motor faults (reset once, then escalate) ---
    "tE": {"meaning": "Thermal error - water temperature above ~194 F, or a thermistor problem.",
           "safe": False,
           "fixes": ["Power OFF, breaker OFF 10 s, restore power, restart once.",
                     "If tE returns, book service (thermistor/heater)."],
           "fault_class": "heater", "source": _LG_LIST},
    "HE": {"meaning": "Heater error - unable to heat the water, or water overheated above 149 F.",
           "safe": False,
           "fixes": ["Power OFF, breaker OFF 10 s, restore power, restart once - do NOT open the heater circuit.",
                     "If HE returns, book service (heating element - not a DIY repair)."],
           "fault_class": "heater",
           "source": _LG_LIST + " ; maps to SAFETY_RULES heating-element rule."},
    "LE": {"meaning": "Motor error - possible motor or wiring-harness issue.", "safe": False,
           "fixes": ["Power OFF, breaker OFF 10 s, restore power, restart once (a transient glitch can clear).",
                     "If LE returns, book service (motor/wiring)."],
           "fault_class": "motor", "source": _LG_LIST},
    "CE": {"meaning": "Motor error - same motor/wiring family as LE.", "safe": False,
           "fixes": ["Power OFF, breaker OFF 10 s, restore power, restart once.",
                     "If CE returns, book service (motor/control)."],
           "fault_class": "motor", "source": _LG_LIST},
    "nE": {"meaning": "Vario motor error - the motor that controls the spray arms.", "safe": False,
           "fixes": ["Disconnect power for a few minutes and retry once.",
                     "If nE returns, book service (vario motor)."],
           "fault_class": "motor", "source": _LG_LIST},
}}
# Non-error indicators that must NOT be treated as faults: 2H (time-remaining < 2h),
# delay-start counters (01-24, n:xx/u:xx/d:xx), P1-P4 / download-cycle / version codes, "---" (cancel).

# symptom (no code on display) -> ranked DIY fixes
SYMPTOM_FIXES = {
    "not_draining": ["Clean the bottom filter / coin trap.",
                     "Check the drain hose for kinks and the disposal knockout plug.",
                     "Run the sink disposal to clear shared-line clogs."],
    "dishes_not_clean": ["Clear and rinse the spray-arm nozzles.",
                         "Use fresh detergent + rinse aid; don't overload or block the arms.",
                         "Run a hot cycle with a dishwasher cleaner to clear scale/grease."],
    "wont_start": ["Confirm the door latches fully and Control Lock (CL) is off.",
                  "Check the cycle isn't in Delay Start; confirm the breaker.",
                  "Confirm the water supply valve is on."],
    "leaking": ["Stop the cycle and turn off the water supply.",   # safety-first; mostly escalate
               "Check the door gasket for food debris; if it recurs, book service."],
    "not_drying": ["Add/refill rinse aid.",
                  "Select the heat-dry / extra-dry option; open the door at cycle end."],
}

SAFETY_RULES = [
    "Never advise opening the heating element / heater circuit (HE/tE) — escalate.",
    "Never advise mains-voltage, motor-winding, or control-board electrical work (LE/CE/nE).",
    "Never advise working on water lines under pressure — have the user shut the supply off first.",
    "Treat any standing-water + electrical situation as escalate-now (AE/E1/FE).",
    "Never advise defeating the door interlock to run the unit with the door open.",
]

INSPECTION_SHOTS = {
    "default": [ ... spec plate, control panel/code, the symptom, narrate steps tried ... ],
    "drain":  [ spec plate, "the bottom filter / coin trap", "the drain hose path under the sink", narrate ],
    "leak":   [ spec plate, "the base/floor under the unit (water source)", "the door gasket", narrate ],
    "motor":  [ spec plate, "the sump / spray arms", "the control panel code", narrate ],
}

CORRECTIONS = [
    {"id": "lg_cl_not_fault", "when": "an LG dishwasher shows CL",
     "correct": "CL is Child/Control Lock, not a fault - hold RINSE+SPRAY 3 s to unlock."},
    {"id": "lg_bE_is_suds", "when": "an LG dishwasher shows bE",
     "correct": "bE is a suds/detergent (or not-level) error, NOT a lock code - switch to dishwasher "
                "detergent and level the unit. (Common LG-specific confusion.)"},
    {"id": "lg_oe_install", "when": "OE appears on the first cycle after install",
     "correct": "Suspect the drain-hose height/kink or a left-in disposal knockout plug, not a pump failure."},
    {"id": "out_of_table_code", "when": "a code is not in this table",
     "correct": "Do NOT guess; point the user to that exact code on the LG support page / manual."},
]

CLARIFYING_HINTS = {
    "appliance": "Is it a dishwasher? Front-control or top-control?",
    "brand": "What brand is on the door or the inner-door spec plate?",
    "model_number": "Read the model number off the plate on the inner door edge (e.g. LDFC2423V).",
    "symptom": "What is it doing — not draining, not cleaning, not starting, or leaking?",
    "error_code": "Is a code blinking on the panel (IE, OE, FE, LE/CE, tE, HE, AE/E1, nE, bE, CL, PF)?",
}
```

> **Verification status (2026-06-25).** The LG codes, meanings, steps, and the `source` URLs above were
> fetched and verified against LG US support (the error-code list page and the AE/E1 + OE per-code
> pages) — they are real URLs, not placeholders. The Samsung manual URLs are verified ManualsLib copies.
> Still to pin during a final curation pass: the exact Samsung **service-manual** PDF for the C-code
> table (the C26 row's meaning currently leans on the service-manual table + iFixit), the LG owner's-
> manual **direct PDF** link (LG only exposes a download button, so we cite the model support hub), and
> the per-unit `warranty_note`/`revision`. `meaning` values are taken verbatim-in-substance from the
> source and must not be paraphrased into something stronger than the source states.

---

## 7. Beyond troubleshooting: non-diagnostic manual information

Everything above is troubleshooting-shaped (`ERROR_CODES`, `SYMPTOM_FIXES`). But the project goal —
*the user does not consult the manual themselves* — is broader than faults. Users also ask
non-diagnostic questions whose answers live in **other parts of the manual**: consumables ("what water
filter?"), specs ("cabinet clearance?"; the LG plate already gives 120V / 11.5A), control procedures
("exit Sabbath/demo mode", "reset the filter light"), maintenance intervals, and warranty terms.

We handle this in **three tiers**. **Tier 1 is the one we plan to implement; Tiers 2 and 3 are the
fallback floor and an explicitly out-of-scope future option.**

### 7.1 Tier 1 (planned) — a curated `REFERENCE` table, same contract as the code table

Most non-diagnostic questions are a small, finite, factual set — exactly what build-time curation
already does well. We add a **fourth record type** per appliance module, under the *same* rules as
`ERROR_CODES`: cited (`source` required), validated at import by `schema.py`, and safety-graded.

```python
# REFERENCE[brand][model] — non-diagnostic facts; every leaf carries a source (REQUIRED)
{
  "consumables": {"water_filter": "DA29-00020B", "bulb": "LED (service part)"},
  "specs":       {"width_in": 35.75, "amps": 11.5, "clearance_in": "see manual p.12"},
  "procedures":  {                       # short, DIY-safe, step-listed
    "exit_demo_mode": ["Hold Power-Freeze + Freezer (or Energy Saver) 3-5 s."],
    "control_lock":   ["Hold the lock button ~3 s to toggle."],
    "reset_filter":   ["Hold the filter-reset button ~3 s after changing the filter."],
  },
  "maintenance": {"clean_condenser_coils": "every 6-12 months",
                  "replace_water_filter": "every 6 months"},
  "warranty":    "1 yr parts/labor; 10 yr sealed system (verify per unit).",
  # ...plus a `source` per group/leaf during curation.
}
```

Notes:

- **Reuses, not reinvents.** It inherits the §4.2 provenance contract and the §3.3 curation pipeline
  unchanged — the only new thing is the record *shape*. Some content already half-exists as
  `CORRECTIONS`/`ERROR_CODES` (Samsung demo-mode exit, LG `CL` unlock); Tier 1 gives those facts a
  proper *reference* home instead of overloading the fault table.
- **Safety still applies.** Non-diagnostic ≠ automatically safe. "Transport/move the unit", "remove
  transport bolts", "replace the water line" carry real risk → the `safe` flag and `SAFETY_RULES`
  gate them exactly as for codes; a risky procedure becomes a reference-only pointer, never steps.
- **Bounded scope.** Tier 1 deliberately covers only the high-value, frequently-asked set — not the
  whole manual. Anything outside it degrades to Tier 2.

### 7.2 Runtime + MCP wiring for Tier 1

- **Intent routing.** Intake is fault-centric today; a reference question ("what filter?") is not a
  symptom. The classifier / `symptom_router` gains an **informational intent** branch: fault →
  `ERROR_CODES`/`SYMPTOM_FIXES` (the §5 ladder); info request → `REFERENCE[brand][model]` → else the
  Tier-2 cited-page fallback. `CLARIFYING_HINTS` is extended with an info-vs-fault disambiguator.
- **MCP projection.** Add `get_spec(model, key)` / `get_manual_section(model, topic)` as projections
  of `REFERENCE`, parallel to `get_pre_service_workflow` (§4.3) — one source of truth, no second copy.
- **Caching + determinism** are identical to the code path: a known reference key is a pure dict
  lookup, no network or model call.

### 7.3 Tier 2 (already in the design) — cited-page fallback for the long tail

The out-of-table → cited-manual-page mechanism built for unknown *codes* (§3.4, §5) generalizes
directly to unknown *topics*. `MANUALS.pages` is already a free-form `{section_label: page}` map, so we
extend it past troubleshooting (`installation`, `operation`, `warranty`, ...) plus a small
topic→section index. For anything Tier 1 doesn't curate, the agent does what it does for an unknown
code — **cite, don't guess**: *"That's in the Installation section, p.12 — here's the link."* This is
the floor that keeps "never hunt through the manual yourself" true even for uncurated questions, at
zero hallucination risk. It requires no new storage type — only more `pages` labels.

### 7.4 Tier 3 (out of scope) — retrieval/RAG over full manual text

Only needed to *answer arbitrary manual questions in the agent's own words* rather than cite a page.
This is a deliberate departure from the build-time / no-PDF-text stance and is **not planned**, because
it reverses three design properties at once:

- **Licensing flips** — you would now store/serve manual text; only ingest manuals you have rights to.
- **Safety vetting** — a retrieved passage can describe a dangerous procedure; every answer must still
  pass `SAFETY_RULES` and be downgraded to reference-only for risky actions (RAG must not bypass the
  safety layer the curated tables enforce by construction).
- **Determinism/latency/quota** — it puts embedding + generation back on the hot path; answers must be
  answer-*with-citation*, never authoritative prose.

Recorded here as the future extension if full-manual free-text Q&A is ever required; **Tier 1 + Tier 2
is the intended coverage** for this project.

---

## 8. Generalization / migration plan

1. **`appliances/schema.py`** — dataclasses + a validator for the record types (§4.2) **and the Tier-1
   `REFERENCE` shape (§7.1)**; fail import on a missing `source`, an unknown `fault_class`, or a
   `safe:true` row whose fix text trips `SAFETY_RULES`. (Cheap guardrail against bad curation.)
2. **`appliances/__init__.py`** — `REGISTRY = {"refrigerator": fridge, "dishwasher": dishwasher}` +
   `normalize_appliance()` (synonyms: "fridge"→refrigerator, "dish washer"→dishwasher).
3. **`grounding.py`** — resolve the module via the registry (default = fridge for back-compat); thread
   `appliance` through `get_fixes`, `error_code_meaning`, `get_inspection_shots`, `_match_symptom_key`.
4. **`appliances/fridge.py`** — add `MANUALS`, add `fault_class`/`source` to existing rows (data-only;
   no behavior change), add the RF28T5001SR manual + C26 example.
5. **`appliances/dishwasher.py`** — the §6.2 module.
6. **Tier-1 non-diagnostic (planned, §7.1–7.2)** — add the `REFERENCE` table to each module, an
   informational-intent branch in the router, and `get_spec` / `get_manual_section` lookups.
7. **Mock MCP fixtures** — generator that projects the modules into `get_manual` /
   `get_pre_service_workflow` (and `get_spec`) fixture JSON (§4.3), so curated + mock can't drift.
8. **Evals/tests** — `tests/test_grounding.py` cases for: dishwasher OE happy path, HE → escalate,
   CL → unlock, bE → suds/detergent (not a lock), out-of-table → manual ref, and a `REFERENCE` lookup
   (e.g. water-filter part number); extend `tests/evals/fixtures/` diagnosis cases.

Backward compatibility: every existing fridge caller that omits `appliance` still resolves to the
fridge module, so this is additive.

---

## 9. Open questions / risks

1. **Liability of giving repair steps** — mitigated by `safe` gating + `SAFETY_RULES` + cited sources;
   keep DIY strictly to non-electrical/non-pressurized/non-heater actions. Confirm the bar with the user.
2. **Source freshness** — `retrieved_at` + `revision` per manual; codes/fixes should be re-verified on
   a cadence. Out-of-date data silently misleads; the manual-ref fallback is the safety net.
3. **Model → manual mapping** — `LDFC2423V` vs trim variants (e.g. `/00`, region suffixes); store the
   base model and match on the normalized prefix, like `MODEL_PATTERNS` already does for fridges.
4. **Plate brand vs request brand** — the original "Whirlpool" label disagreed with the plate; the
   spec-plate read (`read_spec_plate`) is the source of truth, and `verify_model_number` should flag a
   brand/model mismatch rather than trust the typed brand.
5. **Storage format** — Python modules (chosen, matches decision #4) vs JSON data files. JSON eases
   non-engineer curation but loses the import-time validation and the "one file per appliance" locality;
   if curation volume grows, revisit JSON-with-schema.
6. **MCP fixture authority** — for the capstone the `get_pre_service_workflow` fixture is a projection
   of our curated table (not a real OEM tree); the writeup must not overclaim it as the manufacturer's
   actual call-center decision tree (the §16 governance caveat).

---

## 10. Sources (fetched + verified 2026-06-25)

**The manuals (the documents themselves):**
- **LG LDFC2423V — model support hub** (Owner's Manual PDF EN, 8.4 MB, dated 2023-09-11; Online Manual 2025-05-15; spec sheet): [lg.com/us/support/product-help/LDFC2423V.APZEEUS](https://www.lg.com/us/support/product-help/LDFC2423V.APZEEUS) — plate suffix `APZEEUS` matches the unit.
- **Samsung RF28T5001SR — User Manual** (204 pp, EN/ES/FR; troubleshooting p.57, abnormal sounds p.61): [manualslib.com/manual/2671356](https://www.manualslib.com/manual/2671356/Samsung-Rf28t5001.html)
- **Samsung RF28T5001SR/AA — User Manual** (US variant copy): [manualslib.com/manual/2725689](https://www.manualslib.com/manual/2725689/Samsung-Rf28t5001sr-Aa.html)
- **Samsung RF28T5001SR — all manuals index**: [manualslib.com/products/Samsung-Rf28t5001sr-12581290](https://www.manualslib.com/products/Samsung-Rf28t5001sr-12581290.html)

**Error-code references (used for code meanings + first-line fixes):**
- [LG Dishwasher — Error Code List | LG US Support](https://www.lg.com/us/support/help-library/lg-dishwasher-error-code-list-CT10000009-20150933422943) (the master code table; LG also serves it under other IDs)
- [LG — AE & E1 Error Code (leak) | LG US Support](https://www.lg.com/us/support/help-library/ae-e1-error-code-dish-washer--20150140935066)
- [LG — OE Error Code (drain) | LG US Support](https://www.lg.com/us/support/help-library/oe-error-code-dishwasher--20150986144736)
- [Samsung refrigerator error codes | Samsung US Support](https://www.samsung.com/us/support/troubleshooting/TSG01003409/)
- [Samsung RF28T5001SR Repair — C26/defrost-fuse (part DA47-00301B) | iFixit](https://www.ifixit.com/Device/Samsung_RF28T5001SR_Refrigerator)

> Still to retrieve in a final pass (see §6.2 verification note): the Samsung **service-manual** PDF
> (numeric C-code table) and the LG owner's-manual **direct PDF** link (LG exposes a download button,
> not a static URL).
