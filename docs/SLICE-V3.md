# SLICE-V3 — Unattended at 08:30

## Goal

The agent runs without a human: a scheduled Actions workflow lets the
deterministic gate decide, wakes the model only on change, deploys the sitrep
document and the Leaflet map page to the external host, and fails loudly
when it would be blind.

## Why this cut

Everything before this is a tool someone runs; this slice makes it an agent.
It carries the PRD's run semantics (§7 degraded/abort), the publishing
deviation (external host, nothing generated committed), and the map — the
one remaining reader surface.

## Build plan

1. Map page: Leaflet + OSM tiles, markers coloured by alert level, popups
   linking to sitrep card anchors, dashed forecast track for cyclones
   (track, not cone — design §6); tile-failure fallback to graticule ground.
2. Host decision (open PRD item: Netlify vs Vercel vs S3 — decide at slice
   start), deploy token in Actions secrets, deploy step for both pages.
3. Enable `sitrep.yml` (currently `.disabled`): cron 00:00 UTC targeting
   08:30 SGT publish; deterministic gate step → conditional headless model
   step → render → deploy; commit `data/` store back to the repo as the
   run's audit trail.
4. Run semantics per PRD §7: one feed down → degraded banner naming the
   lost hazards + red feed chip, publish anyway; GDACS **and** USGS down, or
   store unreadable → abort, no publish, workflow fails loudly; previous
   sitrep stays live with its own date stamped.
5. `goal.md`: the standing objective the unattended agent works toward.

## Definition of done

Verifiable in two minutes (given host + secrets configured):

- `workflow_dispatch` run completes: gate → (model if changed) → both pages
  live at the host URL, `data/` commit pushed.
- Replay with GDACS fetch forced to fail → published page shows the degraded
  banner and names the blind hazards.
- Replay with GDACS + USGS both failing → run fails, nothing deployed,
  previous sitrep still live.
- The workflow stays green and quiet on a no-change morning (model step
  skipped — visible in the run log).

## Out of scope

Intraday runs, prev/next history navigation (beyond linking the previous
morning), ReliefWeb API lane, push notifications, tsunami/conflict coverage,
map clustering. No schedule tighter than daily.

## Test plan

### End-to-end tests
- Dispatch on fixtures: changed morning deploys both pages; quiet morning
  skips the model and publishes all-quiet.
- Forced dual-feed failure: workflow exits non-zero, deploy step never runs.

### Integration tests
- Gate step writes a machine-readable verdict the workflow conditions on.
- Deploy step is idempotent (re-deploy of same content is a no-op).
- Degraded run: feed-health chip red, banner present, hazards named.
- Map data derives from the same `data/` store as the document (no drift).

### Unit tests
- Degraded-vs-abort threshold logic per PRD §7 truth table.
- Marker colour/level mapping and popup anchor generation.
- Cron margin: run started at 00:00–00:20 UTC still stamps the 08:30 SGT
  report date correctly across the SGT/UTC day boundary.
