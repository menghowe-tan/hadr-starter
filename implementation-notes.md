# Implementation notes

Kept by the agent, reviewed by you. One entry per working block.

## Decisions

- **2026-07-08 — PRD revised: two cadences (user clarification).** The user
  clarified that fetching should be regular ("maybe every 5 minutes") with
  the dashboard reflecting it, and that the sitrep is only the daily summary
  of the previous day. PRD updated (decisions #17–19, §§1 3 7 8 9 10 12),
  product design and slices to match: the monitor loop is deterministic and
  model-free; the model still writes exactly once a day. Flagged in PRD §12:
  a 5-minute Actions cron jitters and ~288 runs/day exhausts free-tier
  minutes — final cadence (paid minutes vs 15 min vs off-Actions runner) is
  a V3 decision; the PRD commits to "regular, with visible freshness", not
  to a number.

- **2026-07-08 — Slicing via build-agent-skills, adapted inline.** The PRD
  was cut into three vertical slices using the slicing step (F) of
  bguiz/build-agent-skills `build-2-plan-specs` ("vertical implementation
  increments, each ending in demo-able UI"). Adaptations: the shaping
  sub-skills are not installed, so no SHAPING.md/BREADBOARD.md were produced
  — the PRD §3 pipeline is the already-selected shape and
  `docs/product-design.md` stands in for the breadboard; slice detail files
  follow the skill's F1–F3 outputs (`docs/SLICES.md`, `docs/SLICE-V*.md`
  with test plans), but issues were filed directly with `gh` using the
  repo's own slice template (the skill's step I writes issue files instead;
  the user asked for GitHub issues).

- **2026-07-08 — V1 fixtures captured from the query APIs (slice V1).**
  Eventful = 2025-03-28 (Mandalay M 7.7, GDACS Red / PAGER red); quiet =
  2025-04-09. Captured by `tests/fixtures/capture_fixtures.py` from GDACS
  `SEARCH` and USGS `fdsnws-event`, both of which return the same feature
  shapes as the live feeds (`EVENTS4APP`, summary GeoJSON), so the fixtures
  replay through the production parsers unmodified. Two curation choices:
  (1) GDACS `SEARCH` returns only Orange/Red by default, so the same day's
  Greens were fetched with `alertlevel=Green` and merged in — the gate needs
  real records to reject; (2) USGS windows are 00:00–12:00 UTC ("the
  morning") at M ≥ 4.5, matching the `4.5_day` feed's floor.

- **2026-07-08 — V1 change detection = fingerprint over updatable fields.**
  The diff (scripts/pipeline/diff.py) hashes alert level, episode
  level/id, magnitude, location, depth, title, gate reason and
  `datemodified`/`updated` — per PRD §5 "diff on episodeid/datemodified,
  not fromdate". The alias union is excluded: a USGS preferred-id flip is
  identity housekeeping, not news. Full change-note classification
  (▲△▽✕) is V2; V1 records only new / updated / aged-out.

## Open questions

## Deviations

<!-- Anything built that departs from the PRD or CLAUDE.md is recorded here,
     with the reason. An undocumented deviation is a bug. -->

- **2026-07-08 — the quiet fixture excludes that day's long-running Orange
  situations.** SLICE-V1 asks for "a genuinely quiet morning", but on any
  real morning GDACS carries months-old Orange situations (on 2025-04-09:
  the Kanlaon eruption and DRC floods). Against V1's *fresh* store those
  would be "new" and the demo could never print `QUIET` — the PRD's answer
  ("never re-report an unchanged long-running event", §5) is a property of
  the *diff against stored state*, not of the gate, and only V2/V3's
  continuously-carried store exhibits it. So `tests/fixtures/quiet/` is the
  real 2025-04-09 capture filtered to its Green events. Reason: V1's
  quiet-morning demo must demonstrate the gate + diff verdict from a fresh
  state; the unfiltered morning is still exercised via the eventful fixture
  re-run, which proves the same "quiet = nothing changed" behaviour with
  Oranges in store.

- **2026-07-08 — `dashboard.html` is not committed to the repo.** The README
  assumes the agent "publishes a morning situation report to
  `dashboard.html`" in-repo. Per the PRD interview (answers #12–15), the user
  rejected committing regenerated views daily: committed JSON under `data/`
  is the system of record, and the sitrep document + Leaflet map page are
  generated views deployed to an external host (Netlify/Vercel class, deploy
  token in Actions secrets). The self-contained sitrep HTML still serves as
  the course's `dashboard.html` artefact — it just lives at the host, not in
  main. Reason: daily generated-file commits add noise without audit value;
  the data commits already provide the history.
