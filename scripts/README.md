Deterministic checks live here — anything that must give the same answer twice does not belong in a prompt.

## Layout (slice V1)

- `run.py` — CLI: one invocation = one fetch cycle. `--replay <fixture-dir>`
  replays captured feeds; without it, one polite live fetch per feed.
  Prints the verdict (`CHANGED`/`QUIET`) as its final line.
- `pipeline/` — the model-free pipeline, in PRD §3 order:
  `fetch` → `normalise` (UTC, canonical events) → `gate` (PRD §5) →
  `diff` (vs our own stored state) → `store` (committed JSON under `data/`)
  → `render` (dashboard skeleton into gitignored `reports/`).
