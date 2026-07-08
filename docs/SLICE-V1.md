# SLICE-V1 — Quiet or not, replayable

## Goal

A deterministic pipeline that fetches GDACS + USGS (live or replayed from
fixtures), normalises to canonical events, applies the severity gate, diffs
against stored state, and renders a minimal sitrep skeleton — proving the
quiet-vs-eventful decision end to end.

## Why this cut

The gate is the product's spine (PRD §3: the model never decides whether to
wake up) and "stays quiet when nothing changed" is a headline feature that is
only demoable via replay (PLAN.md blindspot 7). This slice makes both real on
Day 2 morning, with the test suite the repo currently lacks.

## Build plan

1. Capture replay fixtures: one real historical Orange/Red morning (USGS
   `fdsnws-event` + GDACS search API) and one genuinely quiet morning →
   `tests/fixtures/eventful/`, `tests/fixtures/quiet/`.
2. `scripts/` fetchers for GDACS `EVENTS4APP` and USGS `4.5_day`, with
   `--replay <fixture-dir>` mode; polite single fetch per run.
3. Normalise: UTC everywhere (GDACS naive strings declared UTC, USGS
   epoch-ms), canonical event schema, USGS identity = union of `ids`.
4. Committed-JSON store under `data/`: one file per event + run manifest.
5. Severity gate per PRD §5: GDACS Orange+ (event or episode level),
   USGS PAGER ≥ yellow / `sig` ≥ 600 / M ≥ 5.5 & depth < 70 km;
   drop `istemporary == "true"`.
6. Diff against our own stored state (never yesterday's fetch) → verdict
   `CHANGED` or `QUIET`.
7. Minimal render: unstyled event-list page for `CHANGED`, all-quiet page
   for `QUIET` — placeholder for V2's real document.
8. pytest suite over the fixtures.

## Definition of done

Verifiable in two minutes:

- `uv run pytest` is green.
- `uv run scripts/run.py --replay tests/fixtures/eventful` → prints
  `CHANGED`, writes `data/`, emits a page listing the gated events.
- Re-running the same command → prints `QUIET` (state diff works).
- `uv run scripts/run.py --replay tests/fixtures/quiet` (fresh state) →
  prints `QUIET`, emits the all-quiet page.

## Out of scope

ReliefWeb (any lane), cross-feed merge/identity tiers, change-note
classification, the model call, real styling, the map, hosting/deploy,
GitHub Actions. No live-feed polling loop — live mode is a single manual run.

## Test plan

### End-to-end tests
- Eventful fixture replay produces CHANGED + event-list page; immediate
  re-run produces QUIET.
- Quiet fixture replay produces QUIET + all-quiet page.

### Integration tests
- GDACS fixture parses: string booleans, empty GLIDE, naive datetimes → UTC.
- USGS fixture parses: epoch-ms → UTC, `ids` union stored, depth captured.
- Gate admits Orange/Red and qualifying USGS events; rejects Greens,
  temporary events, sub-threshold quakes.
- Store round-trips: run manifest + per-event files re-load identically.

### Unit tests
- UTC normalisation for each timestamp format.
- `ids`-union dedup matches an event whose preferred id flipped networks.
- Gate threshold edge cases (M 5.5 at depth 69/71 km; sig 599/600).
- Diff verdict on: new event, unchanged event, vanished event (aged-out,
  not withdrawn).
