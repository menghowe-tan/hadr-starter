# CLAUDE.md

## Language & tooling

Python, managed with **uv** (`uv run`, `uv add`). Deterministic pipeline code
lives in `scripts/` and never calls a model.

## Test command

```
uv run pytest
```

(No tests exist yet; the first slice adds them alongside the replay fixtures.)

## Conventions

- **Committed JSON is the database.** Canonical merged events live under
  `data/` (one file per event + a run manifest); git history is the audit
  trail. Generated views (sitrep HTML, map page) are **never committed** —
  they deploy to an external host.
- All timestamps are normalised to UTC at fetch time; SGT appears only in
  rendered views. GDACS naive datetimes are UTC.
- USGS event identity is the union of the `ids` list, never the single `id`.
- Deterministic before generative: fetch/normalise/merge/diff/gate decide
  whether the model wakes up (see `docs/PRD.md` §3).
- **`docs/PRD.md` is the PRD source of truth.** `prd.html` is generated from
  it (regenerate on change, never edit directly); `PLAN.md` is the superseded
  pre-PRD briefing and interview record.

## Deviations policy

Anything built that departs from `docs/PRD.md` or this file is recorded in
`implementation-notes.md` with the reason, at the time it happens. An
undocumented deviation is a bug.
