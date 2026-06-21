# Spike Datasets

Starter test data for the two spikes that need real-world material:
- **Diagnosis spike** → `diagnosis_symptoms.md` / `.jsonl`
- **Plate-read spike** → `plates/` (images) + `plate_sources.md`

## Provenance (read this)

- **Reddit (r/appliancerepair) is blocked to automated fetching**, so nothing here is scraped from Reddit. Sources used instead:
  - **iFixit Answers** — a genuine community repair forum. Two threads were fetched directly and are cited inline (dishwasher #14915, Samsung fridge #960542).
  - **Reputable repair authorities** — iFixit, RepairClinic, Whirlpool, Bob Vila — for corroborated ground-truth fixes.
  - **iFixit model-number wiki CDN** — for the plate images in `plates/`.
- The **symptom text** is written in realistic end-user voice. The **ground-truth fixes** are the standard, well-corroborated first-line causes for each symptom. **Verify each entry against the cited source before trusting the score** — this is a starter set, not gospel.

## How the spikes consume this

- `diagnosis_spike.py`: feed each `symptom` (+ `error_code`) to Gemini under 3 conditions (alone / grounding / curated), compare the model's #1 fix to `ground_truth_first_fixes`, score 2/1/0 -> /20.
- `plate_read_spike.py`: feed each image in `plates/` to Gemini, compare the extracted model number to the known answer (where known), score N/M.

## Licensing / use

iFixit content is CC BY-NC-SA. Using these images + text as a **private educational eval set** is fine. For the **public demo video and writeup, use your own photos** (a plate you shot, a self-staged warm-fridge symptom) and cite sources for any third-party material. Don't republish others' photos in the public deliverable.

## Bonus: safety-eval seeds

The diagnosis entries are all DIY-safe (`unsafe: false`). The **safety eval needs the opposite** — prompts the agent MUST refuse. A few seeds are at the bottom of `diagnosis_symptoms.md` under "Safety-eval seeds." Expand before building `safety_eval.py`.
