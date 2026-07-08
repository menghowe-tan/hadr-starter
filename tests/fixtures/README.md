# Replay fixtures

Real historical captures from the query APIs (PRD §11), taken 2026-07-08 by
`capture_fixtures.py` (run it manually to re-capture; network required).
Each directory holds one morning in the live feed shapes the pipeline polls:
`gdacs.json` (GDACS `EVENTS4APP` event-list shape, via the `SEARCH` API),
`usgs.json` (USGS summary GeoJSON shape, via `fdsnws-event`, M ≥ 4.5,
00:00–12:00 UTC) and, since V2, `reliefweb.xml` (the disasters RSS shape).

The `reliefweb.xml` files are hand-assembled in the live RSS shape
(`feeds/reliefweb.md`) from the real ReliefWeb disaster records of those
mornings — the RSS feed only carries the ~20 *latest* disasters, so a
historical morning cannot be re-captured from it. GLIDEs, links and country
tags are the real ones (`EQ-2025-000043-MMR`, `FL-2025-000050-COD`).

## `eventful/` — 2025-03-28, the Mandalay earthquake morning

GDACS Red ×2 (M 7.7 Mandalay + M 6.7 aftershock), Orange DRC floods, plus
that day's Greens for the gate to reject. USGS carries the same two quakes
at PAGER red — the M 7.7 with a four-alias `ids` union — and two shallow
M 5.5+ events that clear the gate on magnitude/depth alone.

Expected: with the V2 merge, 5 canonical events past the gate (both Myanmar
quakes carry a GDACS+USGS pair; the Vanuatu and mid-Atlantic quakes merge
with their GDACS Green counterparts) → `CHANGED` on first run against an
empty store, `QUIET` on an identical re-run.

## `quiet/` — 2025-04-09, a quiet morning

Green-only GDACS events (including long-running droughts with empty GLIDEs
and 2023 `fromdate`s) and ten sub-threshold quakes: nothing clears the gate.

Expected: `QUIET` from a fresh store, with the all-quiet page.

Note: the real 2025-04-09 also carried long-running Orange situations
(Kanlaon eruption, DRC floods). They are excluded here — see the deviation
entry in `implementation-notes.md`.

## `morning-1/` + `morning-2/` — two consecutive replays of 2025-03-28

The V2 supersession fixtures, derived by `derive_mornings.py` (run it to
regenerate). `morning-2/` is the eventful capture **verbatim**; `morning-1/`
is an earlier snapshot of the same morning cut at 06:30 UTC — after the
M 7.7 mainshock, before the M 6.7 aftershock — with three records rolled
back to plausible first-report states (Mandalay at Orange with PAGER
pending; the DRC flood at Red). The rollback states are constructed, not
captured — recorded as a deviation in `implementation-notes.md`.

Replaying morning-1 then morning-2 exercises: ▲ ESCALATED (Mandalay
Orange→Red), ▽ DOWNGRADED (flood Red→Orange), a new Red (the aftershock),
GLIDE-confirmed and possible umbrella links, and the tier-3 mainshock ↔
aftershock cross-reference.

`assessment.json` in each morning directory is the **recorded model
output** for that replay (the structured-output shape `agent/assess.py`
requests). The committed recordings were authored alongside the fixtures so
the test suite stays deterministic and offline; regenerate against the live
lane with `uv run agent/daily.py --replay <dir> --assess live`.
