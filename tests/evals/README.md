# Appliance Fixer evals

Run the full eval suite live:

```bash
python tests/evals/run_evals.py
```

Live plate and diagnosis scoring need Gemini credits. As of 2026-06-24, the
configured key's credits are depleted, so live scoring is deferred.

Run offline with captured fixtures:

```bash
python tests/evals/run_evals.py --fixtures-dir tests/evals/fixtures
```

Expected fixture files are:

- `tests/evals/fixtures/plate.json`: mapping `filename` to the recorded plate
  read dict.
- `tests/evals/fixtures/diagnosis.json`: mapping symptom `id` to the recorded
  agent reply.
- `tests/evals/fixtures/safety.json`: mapping prompt text or 1-based prompt
  number to the recorded agent reply.

The deterministic CI gate is
`tests/integration/test_state_integrity.py`; it runs offline and makes no model
call.
