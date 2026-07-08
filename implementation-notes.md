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

- **2026-07-08 — V2 merge tiers: two rules the PRD table leaves implicit.**
  (1) Only records from *different* feeds merge — the Mandalay M 7.7
  mainshock and M 6.7 aftershock are 11 min / ~35 km apart, inside the
  tier-2 thresholds, and must not collapse; a feed's own event ids are
  trusted as distinct physical events. (2) Cross-feed ambiguity resolves
  greedily by closest origin time then distance, one partner per feed per
  event, so the USGS mainshock (Δt 2 s) claims the GDACS mainshock before
  the aftershock can. Both forced by the real fixture; documented in
  `scripts/pipeline/merge.py`.

- **2026-07-08 — V2 model layer lives in `agent/`, injected as a callable.**
  CLAUDE.md keeps `scripts/` model-free, so the daily orchestration
  (`agent/daily.py`) sits outside it: deterministic cycle → abort check
  (both real-time feeds down, PRD §7) → model assessment *only if the gate
  said CHANGED* → deterministic render. Assessors are plain callables:
  `ClaudeAssessor` (live, official `anthropic` SDK, `claude-opus-4-8`,
  structured outputs against a fixed JSON schema), `RecordedAssessor`
  (replays committed `assessment.json` fixtures) and test spies — so
  `uv run pytest` is deterministic and offline. `validate_assessment`
  enforces PRD §5 deterministically: the model may add an editorial Green
  (from the gate's own candidate list, reason mandatory) but never invent
  events or notes for unknown ids.

- **2026-07-08 — V2 supersession semantics beyond the design table.**
  Escalated/downgraded read the GDACS alert levels (event or episode,
  whichever is higher); PAGER movement is a *revision*, per design §5
  ("REVISED (magnitude, PAGER, location)"). An event that falls below the
  gate but is still in the feed is a downgrade reported once (status
  `below-gate`), then dropped — distinct from aged-out (vanished) and
  withdrawn (vanished + detail endpoint confirms deletion; USGS only, since
  GDACS has no reliable deletion signal). When a feed was not fetched, its
  stored events are not aged out: blindness is not absence.

- **2026-07-08 — V2 sitrep window = the run's diff.** PRD §8 defines the
  sitrep window as "since the previous sitrep". With one `agent/daily.py`
  run per morning against the carried store, the diff *is* that window; a
  separate since-last-sitrep bookmark becomes necessary only in V3 when
  the monitor loop also writes the store between sitreps. Flagged for V3
  rather than built speculatively here.

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

- **2026-07-08 — the morning-1 fixture is derived, not captured.** SLICE-V2
  asks for "two consecutive mornings where an event escalates Orange→Red",
  but the GDACS/USGS query APIs return current state only — a historical
  episode-level snapshot cannot be re-captured. `tests/fixtures/morning-2/`
  is the real 2025-03-28 capture verbatim; `tests/fixtures/morning-1/` is
  derived from it by `derive_mornings.py`: cut at 06:30 UTC (after the
  M 7.7, before the M 6.7 aftershock) with three explicit rollbacks —
  Mandalay to Orange with PAGER pending (its real early state was lower
  than the final Red), and the DRC flood raised to Red so the real
  capture's Orange exercises ▽ DOWNGRADED. Reason: the escalation path
  must be replayable offline; every edit is explicit in the derivation
  script and the final morning stays fully real.

- **2026-07-08 — the ReliefWeb fixtures are hand-assembled, not captured.**
  The RSS feed carries only the ~20 latest disasters, so the 2025-03-28
  items cannot be re-fetched. `reliefweb.xml` files follow the live RSS
  shape recorded in `feeds/reliefweb.md` and use the real disaster records
  (titles, links, GLIDEs `EQ-2025-000043-MMR` / `FL-2025-000050-COD`,
  country tags). Reason: fixture parity with the production parser matters
  more than capture provenance the API cannot provide; noted in
  `tests/fixtures/README.md`.

- **2026-07-08 — recorded model assessments are committed fixtures.** The
  `assessment.json` files replayed by tests were authored with the fixtures
  (in the exact structured-output shape the live lane requests) rather than
  recorded from a paid live call. Reason: CLAUDE.md requires `uv run
  pytest` to be deterministic and offline; the live lane
  (`agent/daily.py --assess live`) regenerates them at any time.

- **2026-07-08 — the sitrep's map zone is a placeholder note in V2.** The
  design's zone 4 calls for a static map image linking to the live map
  page; both the map page and pre-rendered imagery are V3 scope (issue #4
  "out of scope: the map page"). The zone renders a bordered note saying
  so, keeping the six-zone anatomy and the no-network guarantee. Reason:
  honest placeholder over a broken link or an external tile request.
