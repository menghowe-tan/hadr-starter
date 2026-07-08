# SLICE-V3 — The always-on agent (monitor loop + daily sitrep)

## Goal

**This is the slice that makes it run by itself.** Two schedules, no human:
a **monitor loop** (target every 5 min — cadence decided here, see PRD §12)
fetches the feeds, updates `data/` on change, and redeploys the live
dashboard with per-feed freshness; a **daily sitrep workflow** (cron 00:00
UTC → 08:30 SGT publish) gates on what changed since the previous sitrep,
wakes the model only then, and deploys the previous-day summary. Fails
loudly when it would be blind. V1 builds the fetching machinery and V2 the
sitrep itself — both human-triggered until this slice adds the schedules.

## Why this cut

Everything before this is a tool someone runs; this slice makes it an agent.
It carries the PRD's run semantics (§7 degraded/abort), the publishing
deviation (external host, nothing generated committed), and the map — the
one remaining reader surface.

## Build plan

1. Live dashboard: Leaflet + OSM tiles, markers coloured by alert level,
   current event list, per-feed freshness stamps (stale at 3× cadence),
   popups linking to sitrep card anchors, dashed forecast track for cyclones
   (track, not cone — design §6); tile-failure fallback to graticule ground.
2. Host decision (open PRD item: Netlify vs Vercel vs S3 — decide at slice
   start), deploy token in Actions secrets, deploy steps for both surfaces.
3. Monitor-loop workflow: scheduled fetch → normalise → merge → diff; on
   change, commit `data/` and redeploy the dashboard; no model calls.
   **Decide the cadence here** (PRD §12: 5-min target vs Actions jitter and
   minutes quota — accept paid minutes, relax to 15 min, or move off
   Actions).
4. Enable `sitrep.yml` (currently `.disabled`): cron 00:00 UTC targeting
   08:30 SGT publish; deterministic gate (changed since previous sitrep) →
   conditional headless model step → render previous-day summary → deploy.
5. Run semantics per PRD §7: sitrep — one feed down → degraded banner naming
   the lost hazards, publish anyway; GDACS **and** USGS down, or store
   unreadable → abort, no publish, workflow fails loudly; previous sitrep
   stays live with its own date stamped. Monitor loop — failed cycle skips;
   ≥1 h without a real-time-feed success → alert.
6. `goal.md`: the standing objective the unattended agent works toward.

## Definition of done

Verifiable in two minutes (given host + secrets configured):

- `workflow_dispatch` of the monitor loop: fetch → diff → dashboard
  redeployed with fresh per-feed stamps; a no-change cycle deploys nothing.
- `workflow_dispatch` of the sitrep run: gate → (model if changed) →
  previous-day summary live at the host URL, `data/` commit pushed.
- Replay with GDACS fetch forced to fail → published page shows the degraded
  banner and names the blind hazards.
- Replay with GDACS + USGS both failing → run fails, nothing deployed,
  previous sitrep still live.
- The workflow stays green and quiet on a no-change morning (model step
  skipped — visible in the run log).

## Out of scope

Intraday **sitreps** (the dashboard updates continuously; the model writes
once a day), prev/next history navigation (beyond linking the previous
morning), ReliefWeb API lane, push notifications, tsunami/conflict coverage,
map clustering. Monitor cadence tighter than 5 minutes.

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
