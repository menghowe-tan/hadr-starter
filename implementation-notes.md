# Implementation notes

Kept by the agent, reviewed by you. One entry per working block.

## Decisions

- **2026-07-08 — PRD revised: contract-first slices (user request).** The
  user asked that the three vertical slices be implementable independently
  by establishing the schema and the interfaces up front. Added PRD §13
  (canonical event schema, run manifest, stage CLI interfaces, model
  assessment file, render/deploy layout, contract fixtures, per-slice
  consumes/produces table) and decision #20; Day-1 deliverables gain a
  contract freeze (`schemas/` + fixtures, §11 #4). `docs/SLICES.md` and the
  three `SLICE-V*.md` now state their contract dependencies instead of
  depending on each other: V2 builds from hand-authored store fixtures, V3
  from stage stubs; the V1→V2→V3 order is demo/integration order only. The
  one integration point kept: `sitrep.yml` ships `.disabled` and flips on
  only when the real gate (V1) and model step (V2) are wired in.
  `prd.html` regenerated.

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

## Open questions

## Deviations

<!-- Anything built that departs from the PRD or CLAUDE.md is recorded here,
     with the reason. An undocumented deviation is a bug. -->

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
