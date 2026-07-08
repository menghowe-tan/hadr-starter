# Implementation notes

Kept by the agent, reviewed by you. One entry per working block.

## Decisions

- **2026-07-08 — Slice V3 built on a reusable 5-level harness (user request).**
  The agent is a hand-rolled harness in five working checkpoints (chat loop →
  standing orders → fetch_feed → agent loop → write_dashboard), one commit
  each. `harness/` is generic and reusable in other projects (zero repo
  imports); `agent/` is the HADR wiring (tools + goal.md). Model default
  `claude-opus-4-8` (configurable via `ANTHROPIC_MODEL` / `--model`),
  adaptive thinking, manual tool-use loop — owning the loop is the point.

- **2026-07-08 — V3 stands on §13 stubs.** V1/V2 don't exist;
  `scripts/stub_pipeline.py` honours the §13.3 stage contract (scenarios
  eventful/quiet/gdacs-down/both-down, schema-validated `data/`, verdict
  line + `GITHUB_OUTPUT`, exit 3 abort-blind), and `schemas/` + hand-authored
  store fixtures are the contract freeze (§11 #4). One additive contract
  change: optional `geo.track` on the canonical event, needed for the
  cyclone forecast track (design §6).

- **2026-07-08 — Host: Netlify (PRD §12 recommendation).** Isolated in
  `scripts/deploy.py` (the single swap point), idempotent via a content
  hash in the manifest's `deploy_state`. Requires Actions secrets
  `NETLIFY_AUTH_TOKEN` + `NETLIFY_SITE_ID` (+ optional `NETLIFY_SITE_URL`
  for sitrep preservation); without them the deploy step skips loudly.

- **2026-07-08 — Monitor cadence: 15 minutes (PRD §12 decision owed by V3).**
  A 5-min cron is Actions' floor, jitters badly, and burns the free-tier
  quota (~288 runs/day); 15 min is sustainable (~96). Both workflows'
  cron lines are written but **commented** until the real V1/V2 stages
  replace the stubs — scheduling fixture replays would publish fake data
  and waste minutes. `workflow_dispatch` (with a scenario input) is live
  and is what the slice DoD exercises.

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

- **2026-07-08 — The V3 sitrep page is model-written, not deterministically
  rendered.** PRD §3/decision #18 put rendering in deterministic code; the
  user's harness spec has the model save the page itself via the
  `write_dashboard` tool. Scope of the deviation: the *sitrep document*
  only — the live Leaflet dashboard stays deterministic
  (`scripts/render_dashboard.py`), the template/escaping live in the tool
  function, and the model-free stand-ins (`render_canned_sitrep.py`) use
  the same function. V2's real renderer supersedes this when it lands.

- **2026-07-08 — `sitrep.yml` is enabled (dispatch-only), not `.disabled`.**
  The README says keep it disabled until both steps exist — both now do
  (deterministic stub gate + gated model step), so the file is active for
  `workflow_dispatch`; the cron stays commented (see cadence decision), so
  nothing scheduled runs against stubs. Note: GitHub only registers
  workflows from the default branch, so dispatching these needs the PR
  merged (or the workflow files cherry-picked to main).

- **2026-07-08 — Single-site deploys mirror the live sitrep.** A Netlify
  deploy replaces the whole site, and the monitor loop's out/ contains
  only the dashboard; `deploy.py` therefore fetches the currently-live
  `sitrep/index.html` into out/ before deploying, so a dashboard redeploy
  never drops the morning report. Not in the PRD; recorded here.

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
