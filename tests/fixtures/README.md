# Replay fixtures

Real historical captures from the query APIs (PRD §11), taken 2026-07-08 by
`capture_fixtures.py` (run it manually to re-capture; network required).
Each directory holds one morning in the live feed shapes the pipeline polls:
`gdacs.json` (GDACS `EVENTS4APP` event-list shape, via the `SEARCH` API) and
`usgs.json` (USGS summary GeoJSON shape, via `fdsnws-event`, M ≥ 4.5,
00:00–12:00 UTC).

## `eventful/` — 2025-03-28, the Mandalay earthquake morning

GDACS Red ×2 (M 7.7 Mandalay + M 6.7 aftershock), Orange DRC floods, plus
that day's Greens for the gate to reject. USGS carries the same two quakes
at PAGER red — the M 7.7 with a four-alias `ids` union — and two shallow
M 5.5+ events that clear the gate on magnitude/depth alone.

Expected: 7 events past the gate → `CHANGED` on first run against an empty
store, `QUIET` on an identical re-run.

## `quiet/` — 2025-04-09, a quiet morning

Green-only GDACS events (including long-running droughts with empty GLIDEs
and 2023 `fromdate`s) and ten sub-threshold quakes: nothing clears the gate.

Expected: `QUIET` from a fresh store, with the all-quiet page.

Note: the real 2025-04-09 also carried long-running Orange situations
(Kanlaon eruption, DRC floods). They are excluded here — see the deviation
entry in `implementation-notes.md`.
