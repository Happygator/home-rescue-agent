# Day-0/1 Spike Results

Date: 2026-06-21
Harness: `spikes/` (throwaway). Model: Gemini via AI Studio API key (free tier).
Datasets: `spikes/datasets/` (8 labeled plate photos + 12 symptoms, sourced from
iFixit Answers + repair guides; Reddit was blocked to automated fetching).

## Spike 1 — Plate-read (perception hook): PASS

Ran `plate_read_spike.py` over 8 labeled real data-plate photos on `gemini-2.5-flash`.

| Difficulty | Result | Notes |
|---|---|---|
| easy | 3/3 exact | Samsung RF28T5001SR, Whirlpool WRFF3336SZ, LG LDFC2423V |
| medium | 2/3 exact | Whirlpool fridge + dryer exact; washer `WFW95HEDWO` vs `WFW95HEDW0` |
| hard | 2/2 exact | no-logo compact `BC-70-62H-US(E)`, low-contrast Trane foil `4TTR6048J1000AA` |

**Score: 7/8 exact (8/8 modulo one glyph).** The two hardest cases (silver-on-silver
HVAC foil, ambiguous no-logo compact fridge with two candidate strings) both passed.

**Conclusions / build inputs:**
- The camera-magic diagnosis hook is validated on real photos. Keep it as the demo hook.
- The single miss is an **O / 0 OCR confusion** on the final character, not a misread.
  `validate_model` MUST canonicalize O<->0 and I<->1 before matching. With that, 8/8.
- Gemini returns suffixed codes (`WRFF3336SZ 00`, `RF28T5001SR/AA`); the normalize step
  (strip whitespace, trailing ` 00`, `/AA` region suffix) matched them correctly.

## Spike 2 — Diagnosis quality (settles premise #2): thin KB confirmed

`gemini-2.5-flash` daily free quota was exhausted, so this ran on **`gemini-2.5-flash-lite`**
(a separate free-tier bucket) in slim mode (`--no-grounding --no-judge`): alone vs curated,
12 symptoms, hand-scored against ground truth. flash-lite is WEAKER than the `flash` the
product ships on, so this is a **conservative lower bound**.

"alone" = Gemini with no KB and no grounding (the real question). Score 2 = correct+safe
first fix matching ground truth; 1 = right family, wrong specific; 0 = wrong or unsafe.

| ID | alone first-fix | score |
|----|-----------------|-------|
| F1 fridge warm/freezer fine | defrost timer/heater | 2 |
| F2 both warm, running | door seals (miss: GT=coils) | 1 |
| F3 runs constantly | thermostat stuck on | 1 |
| F4 water under crisper | clear defrost drain | 2 |
| F5 ice maker stopped | water supply valve open? | 2 |
| F6 frost buildup | door sealing / ajar | 2 |
| F7 "PF" after storm | unplug 1 min to reset | 2 |
| F8 warm + buzzing freezer | condenser fan (GT=evaporator) | 1 |
| D1 dishwasher won't drain | drain filter/pump clogged | 2 |
| D2 dishes gritty | clean filter | 2 |
| W1 washer won't drain (OE) | clean drain-pump filter | 2 |
| W2 washer shakes (UE) | balance load | 2 |

**Score: 21/24 (~88%). 9/12 exact, 3/12 partial, 0/12 wrong-or-unsafe.**

**VERDICT — premise #2 RESOLVED: do NOT author a big diagnosis KB.** Even the weaker lite
model gets the right first-line fix ~88% of the time with zero knowledge base and is never
unsafe; the production `flash` model will do at least as well. Keep curation **thin**:
- **error-code -> meaning table** (brand-specific codes the model can't reliably know),
- **safety rules** (the deterministic guardrail),
- **~3-5 targeted corrections** for the cases the model gets *almost* right (F2 coils-vs-seal,
  F8 evaporator-vs-condenser fan).
Then let the model do the rest. This saves days of KB authoring.

**Caveats:** flash-lite is a lower bound; hand-scored (spot-check the 3 partials); n=12.
A confirmation run on full `flash` with the LLM-judge + grounding would tighten it once
quota/billing frees up, but the direction is conservative and clear.

## Spike 3 — Resume feasibility: NOT YET RUN (pending)

The deterministic reopen-by-`case_id` path (the headline) was not spiked yet. It needs no
API calls (pure SQLite + ADK runner), so it is NOT quota-blocked. It will be built and
verified as the Day-2 walking skeleton (see Next Step in IMPLEMENTATION_PLAN.md).

## Ops / quota learnings (carry forward)

- **Free-tier limits are per-model.** `gemini-2.5-flash` daily cap was hit after ~22 calls;
  `gemini-2.5-flash-lite` had a separate fresh bucket. Switch `--model` to find quota.
- Adding billing to the AI Studio key is currently blocked (technical difficulty), so dev
  runs use free-tier model-bucket switching + slim modes.
- The harness has 429 backoff (honors retryDelay; bails only on genuinely depleted credits),
  plus `--limit`, `--sleep`, `--no-grounding`, `--no-judge` to fit free-tier limits.
- Before recording the demo: capture a few real Gemini responses as fixtures so a rate-limit
  never blocks a take.
