# Implementation notes

Kept by the agent, reviewed by you. One entry per working block.

## Decisions

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
