# Implementation notes

Kept by the agent, reviewed by you. One entry per working block.

## Decisions

- **2026-07-09 — news-summary's search switched to a keyless local tool
  (user request: "switch to an alternative that does not need an
  ANTHROPIC_API_KEY").** In the generic/interactive lane the news-summary
  skill originally named Anthropic's server-side `web_search_20250305`, which
  only runs against a live `ANTHROPIC_API_KEY` and its billing. Replaced it
  with a **local, keyless** `web_search` tool (`agent/tools.py`): plain
  `httpx.post` to DuckDuckGo's HTML endpoint, parsed by a small stdlib
  `HTMLParser` (`_parse_ddg`) that unwraps the `/l/?uddg=` redirect links —
  no API key, no extra dependency. The skill runs entirely through the
  harness's ordinary local-tool loop, so it now works against any backend,
  including a keyless relay behind `ANTHROPIC_BASE_URL`. `harness/skills.py`'s
  `SERVER_TOOLS` map is now empty (documented extension point: a project with
  a key can still register the server tool there); the server-tool plumbing
  in `Agent` stays and is still tested. Trade-off: we now depend on an
  unversioned HTML shape instead of a documented API — `_parse_ddg` is
  deliberately forgiving. New tests: `tests/test_web_search.py`.

- **2026-07-09 — the daily production lane switched to keyless search too
  (user follow-up: "the daily production lane should be switched as well").**
  `agent/assess.py`'s `_call_structured` used to hand the Anthropic API the
  server `web_search_20250305` tool and let the API execute it — which needs a
  live key + billing. Reworked it into a client-side tool loop: it now
  advertises the local `web_search` `Tool` (agent/tools.py) as a client tool,
  and when the model returns `stop_reason == "tool_use"` it runs the tool with
  `_run_search` (mirroring `harness/agent.py`'s runner), feeds the
  `tool_result` back, and loops — the model's final, non-tool turn is still
  the `output_config` schema-constrained JSON, so `_normalise`/
  `validate_assessment`/`validate_news_items` and the `searched` flag are all
  unchanged. Both `ClaudeAssessor.__call__` (gated sitrep call) and
  `search_news` (always-runs news call) pass `WEB_SEARCH` instead of the
  server-tool dict; the `pause_turn` branch is kept so a server tool still
  works if a keyed project ever passes one. Net effect: the daily lane needs
  no `ANTHROPIC_API_KEY` for search — only a reachable model backend, which
  can be a keyless relay behind `ANTHROPIC_BASE_URL` (the repo already
  supports that). New offline tests in `tests/test_assess.py` drive the loop
  with a scripted fake client (tool_use round → local run → schema JSON;
  and the not-searched case).

- **2026-07-09 — Skills are a generic harness capability (user request:
  "the harness should be running any skills... design it such that new skills
  can be added, and all running of skills handled generically by the
  harness").** Added `harness/skills.py` — a `Skill` (name, description,
  instructions, model, tools) plus `parse_skill`/`load_skill`/
  `discover_skills`, a dependency-free `SKILL.md` front-matter reader (no
  PyYAML; reads the `key: value` fields it needs, tolerates the richer YAML
  installed skills carry, falls back to folder name + first body line when a
  file has no front-matter). Stays project-agnostic per CLAUDE.md: point it
  at any folder of `<name>/SKILL.md`. `harness/agent.py`'s `Agent` gained a
  `skills=` argument: each discovered skill is advertised generically as a
  tool (name + description only — progressive disclosure, the model reads the
  instructions only when it invokes one), and `Agent.run_skill` runs an
  invoked skill as a *scoped sub-agent* — the skill's own instructions as
  system prompt, its own model, and only the tools it named (resolved against
  the parent's local tools + a small `SERVER_TOOLS` map for Anthropic server
  tools like `web_search`). A sub-agent is given no skills of its own, so a
  skill can't recurse. `harness/cli.py` gained `--skills DIR`; `agent/main.py`
  now loads `skills/` so the interactive HADR agent exposes `news-summary`
  (and any future skill) with zero per-skill wiring. `skills/news-summary/
  SKILL.md` gained front-matter (name/description/model/`tools: web_search`)
  so it loads as a real skill instead of pure documentation. Boundary kept:
  the *daily sitrep* production path (`agent/daily.py` + `agent/assess.py`) is
  unchanged — it remains the deterministic, gated, structured-output lane the
  PRD mandates (the news-summary daily call still runs there with its
  validation and carry-forward); this refactor is the reusable-harness /
  interactive lane, consistent with the V1/V2/V3-integration note below that
  already separated `agent/daily.py` (production sitrep) from `harness/` +
  `agent/main.py` (the reusable tool-calling loop). New tests:
  `tests/test_skills.py` (parse, discover, run-as-sub-agent, recursion guard).

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

- **2026-07-09 — Day-2 skill: news-summary (user request).** Added
  `skills/news-summary/SKILL.md` and wired it into the existing
  `agent/assess.py` call rather than a separate model step: the
  `ClaudeAssessor` request now carries the `web_search_20250305` server
  tool, and the structured-output schema gained a fourth field,
  `news_items` (headline, source, url, published_at, event_id, note),
  alongside `summary`/`change_notes`/`editorial_greens`. `validate_assessment`
  extends the same invention guard — a news item's `event_id`, if set, must
  already be a known event — and adds a hard attribution gate: no source
  name + URL, no item. Persisted to a new committed file, `data/news.json`
  (`pipeline.store.load_news`/`save_news`), written only on a run that woke
  the model and carried forward otherwise (same convention as the
  manifest's `deploy_state`), so `scripts/render_dashboard.py` — which must
  stay model-free per CLAUDE.md — can display the last search without
  calling anything live. `pipeline.render.render_sitrep` gained a "News
  mentions" zone (after Events, before "Noted, quieter") reading straight
  from the assessment; `render_dashboard.py` gained a matching aside panel
  reading straight from `data/news.json`. Neither render script talks to a
  model; only `agent/assess.py`'s single call does.

- **2026-07-09 — the News mentions zone is never silently omitted (user
  correction).** The first cut only rendered the zone when
  `data/news.json` existed, so a store that had never run the skill (true
  in this repo — no live `ANTHROPIC_API_KEY` here yet, `--assess off`/
  `recorded` never call `web_search`) showed nothing at all: indistinguishable
  from "checked, found nothing." Changed both `render_sitrep` and
  `render_dashboard.news_panel` to always render the zone, in one of three
  explicit states — never run, run but nothing worth surfacing, or run
  with items — matching `goal.md`'s own "all quiet is a statement, not an
  absence" principle. Also added a `searched` flag (`ClaudeAssessor`
  detects `server_tool_use`/`web_search_tool_result` blocks across the
  `pause_turn` loop) so "the model didn't call web_search this run" and
  "it searched and found nothing" render as different sentences —
  `RecordedAssessor`/`--assess off` leave `searched` absent (`None`,
  unknown), since no live call happened to check.

- **2026-07-09 — news-summary decoupled from the sitrep gate (user
  request).** Until now, `news_items` only ran as part of the one
  CHANGED-gated `ClaudeAssessor` call — meaning "nothing crossed GDACS/
  USGS/ReliefWeb's own alert thresholds" also meant "no news check", which
  defeats the skill's own point (`goal.md`'s blindness: tsunami warnings,
  ReliefWeb's days-long lag — a quiet morning by *those* thresholds can
  still be the morning a story breaks that none of them have caught). Split
  the news call out of `ASSESSMENT_SCHEMA`'s consumer path into its own
  standalone one: `agent/assess.py` gained `NEWS_SYSTEM_PROMPT`/
  `NEWS_SCHEMA`/`ClaudeAssessor.search_news`/`RecordedAssessor.search_news`
  (the shared `_call_structured` helper, factored out of the old
  `ClaudeAssessor.__call__`, backs both); `agent/daily.py` now calls
  `assessor.search_news(...)` on *every* run when the gated call didn't
  already produce `news_items` for the day — never both, so a `CHANGED`
  morning still makes exactly one model call. This is now the second,
  narrower exception to "the model never decides whether to wake up"
  (the first was `web_search` itself, recorded above) — flagged
  explicitly here rather than silently generalized, since the gate
  covering the *sitrep-writing* call (summary/change_notes/
  editorial_greens) is unchanged and still tested by
  `test_model_wakes_only_when_the_gate_says_changed`.

## Open questions

- `agent/assess.py`'s daily lane now uses a client-side tool loop (local
  `web_search` + `output_config` json_schema) instead of the server
  `web_search_20250305`. The loop is unit-tested offline with a scripted
  fake client, but the *combination* of `output_config` and client `tool_use`
  rounds has not been exercised against a real model backend from this
  environment (no key/relay here). It follows the same request shape the old
  server-tool path assumed (tools + output_config in one call), and the
  `_json_only_instruction` fallback still covers a relay that ignores
  `output_config`. Run `uv run agent/daily.py --replay <dir> --assess live`
  against the real backend at the first opportunity and diff the result
  before trusting the sitrep scheduler's next `live` dispatch — in
  particular confirm the model actually emits the schema JSON on the turn
  *after* the tool result (not alongside the tool call).
- The keyless `web_search` scrapes DuckDuckGo's unversioned HTML
  (`agent/tools._parse_ddg`); a markup change or rate-limit would need a
  parser tweak. Verified returning real results live during development, but
  it has no contract guarantee the way a JSON API would.

## Deviations

<!-- Anything built that departs from the PRD or CLAUDE.md is recorded here,
     with the reason. An undocumented deviation is a bug. -->

- **2026-07-09 — a second hosting surface: GitHub Pages for the committed
  static pages (user request).** PRD §12/§15 named exactly one host —
  Netlify, driven by `scripts/deploy.py`, for the *generated* views
  (`out/dashboard/`, `out/sitrep/`), and decision #12 keeps nothing generated
  in the repo. That covers the operational product but says nothing about the
  hand-written pages that *are* committed — `marketing.html`, `prd.html`,
  `quiz.html`, `system-view.html`. The user asked to "host all the html pages
  online, main page = marketing page", so `.github/workflows/pages.yml`
  publishes those four committed files to GitHub Pages, copying
  `marketing.html` to `index.html` so it serves at the site root. Reason for a
  second host rather than folding them into the Netlify site: the Netlify
  deploy replaces the whole site on every monitor/sitrep run (see
  `preserve_live_sitrep` in `scripts/deploy.py`), so mixing static docs into
  `out/` would couple them to the operational deploy cadence and its
  whole-site-replace semantics. GitHub Pages needs no secrets, serves only
  committed files, and stays completely independent of the pipeline. Scope
  kept minimal: no page content changed and navigation was not restructured
  (nothing links to `quiz.html`/`system-view.html`; they are reachable by URL
  only). `marketing.html`'s existing `href="README.md"` link now resolves to
  the raw markdown file (copied into the site as-is) — pre-existing, not
  fixed here. Pages must be enabled with build source "GitHub Actions" for the
  workflow to publish (done via `gh api` at ship time / one-click in repo
  Settings → Pages otherwise).

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

- **2026-07-08 — V1/V2/V3 merged into `main`; the §13 contract was adapted
  to the shipped pipeline, not the other way round.** V1 (#7), V2 (#9) and
  V3 (#8) were merged into their own PR base branches, never `main` — #9's
  base was `slice-v1-quiet-or-not`, #8's was `worktree-shiny-spinning-puffin`,
  so none of this was actually on `main` until this integration. Auditing
  the merge surfaced that V3's `schemas/`, `scripts/health.py` and
  `scripts/render_dashboard.py` were built against the PRD §13 stage
  contract, but V1/V2 never implemented that contract — `schemas/` didn't
  exist on their branch, and the real `pipeline.store`/`pipeline.runner`
  manifest and event shapes differ from §13 throughout (`run_at` not
  `run_utc`, flat event dicts keyed by `event_id` not nested
  `identity`/`geo`/`severity`, no `deploy_state` carry-forward, no
  `GITHUB_OUTPUT`). Decision: adapt V3's consumers to the real, tested
  68→107-test pipeline rather than rewrite `pipeline.store`/`normalise`/
  `diff` to match a contract that was never load-bearing. Specifically:
  - `scripts/health.py` reads `feed["fetched_at"]` (was `last_success_utc`);
    `pipeline.runner`'s `_feed()` already carries the last successful
    fetch forward on failure, so the field means the same thing.
  - `scripts/render_dashboard.py` reads the real flat event schema
    (`event_id`, `lat`/`lon`, `alert_level`/`episode_alert_level` via
    `pipeline.diff.effective_level_rank`, `pipeline.render.display_title`)
    instead of the §13 nested shape; the marker's "change" text comes from
    the run's `manifest["changes"]` (the diff's own classification), not
    from a field on the event. The canonical event has no forecast-track
    field yet (GDACS cyclone tracks are unbuilt), so the map draws no
    polyline instead of inventing one — a scoped gap, not a bug.
  - `pipeline.runner.run_cycle` now carries `deploy_state` forward from
    the previous manifest (previously only `stub_pipeline.run` did this);
    without it, every cycle's `store.save()` would erase what
    `scripts/deploy.py` wrote, forcing a real deploy every run.
  - `scripts/run.py` and `agent/daily.py` gained `scripts/health.py`
    integration: a `health: <status>` print line (before the verdict,
    which stays the documented final line), `GITHUB_OUTPUT` (`verdict`,
    `health`) for the workflows, and an abort exit code. `agent/daily.py`'s
    abort exit code changed from 2 to `health.ABORT_EXIT_CODE` (3), for
    one consistent contract across both CLIs; no test asserted the old
    value.
  - Removed as fully superseded: `scripts/stub_pipeline.py`,
    `scripts/render_canned_sitrep.py`, `schemas/`, `tests/test_pipeline.py`,
    `tests/test_canned_sitrep.py`, and the stub-shaped
    `tests/fixtures/{eventful,quiet}/store/` snapshots — the real pipeline
    and `agent/daily.py` (with `--assess off` as the no-API-key fallback)
    replace them, matching what PR #8's own description already flagged as
    the integration step ("swap the stub command").
  - `.github/workflows/sitrep.yml` collapsed its separate "gate" and
    "write sitrep" steps into one `agent/daily.py` call — V2's
    `run_daily()` already does cycle → gate → gated assessment → render in
    one process, so the split was only needed for the stub contract.
  - `harness/` and `agent/main.py` (the reusable tool-calling loop and its
    HADR tools) are kept — real, tested, demoed code — but are no longer
    wired into `sitrep.yml`: `agent/daily.py`'s deterministic render +
    validated structured-output assessment is the better-specified
    replacement for the sitrep role that V3's own notes already called out
    as provisional ("V2's real renderer supersedes this when it lands").
  - Added `tests/fixtures/gdacs-down/` (real `usgs.json`/`reliefweb.xml`,
    `gdacs.json` omitted) and `tests/fixtures/both-down/` (empty) so the
    workflows' `workflow_dispatch` scenario input can still exercise
    degraded/abort against the real pipeline (`fetch.py` reports a missing
    replay file as `down`) without a purpose-built stub scenario.
  - Both crons (`*/15 * * * *` monitor, `0 0 * * *` sitrep) are uncommented:
    the real V1/V2 stages they were waiting on are now in `main`.

- **2026-07-09 — the news-summary skill's input is generative, not
  deterministic.** CLAUDE.md: "deterministic before generative... no model
  calls in scripts/". Every other feed (GDACS, USGS, ReliefWeb) is a
  fetch-then-parse call with a stable schema; `web_search` results are
  chosen by the model, at generation time, and cannot be replayed byte-for-
  byte — `agent/assess.py`'s own docstring used to say the model writes
  "three things and only three things", which this breaks. Reason the user
  asked for it anyway: none of the deterministic feeds can go looking for a
  fast-breaking story (`goal.md`'s stated blindness — tsunami warnings,
  ReliefWeb's days-long lag), and only a live search closes that gap.
  Mitigations, so the rest of the pipeline's guarantees still hold: (1) a
  news item is never a `Reported`/`Estimated` impact figure — it renders in
  its own "News mentions" zone, never mixed with `render.VALID_IMPACT_LABELS`;
  (2) `validate_assessment` still forbids inventing or reclassifying an
  event, and additionally requires a real source + URL per item; (3) the
  search only ever runs inside the one already-gated model call
  (`agent/daily.py`, only on `CHANGED`) — it does not add a second place the
  model can wake itself; (4) the result is written to committed JSON
  (`data/news.json`) immediately, so `scripts/render_dashboard.py` stays
  model-free and every other render step stays exactly as deterministic as
  it was before this skill existed.

- **2026-07-09 — `data/` untracked and gitignored (user request, reverses
  "committed JSON is the database").** CLAUDE.md states plainly: "Committed
  JSON is the database. Canonical merged events live under `data/`... git
  history is the audit trail." Until now that was true in practice too —
  `hadr-monitor[bot]` was pushing `monitor: store update` commits to
  `data/manifest.json`/`data/events/*.json` roughly every 15 minutes. At
  the user's explicit request, `data/` was added to `.gitignore` and the
  six then-tracked files were removed from the index with
  `git rm --cached` (left on disk, only untracked from git). I flagged the
  contradiction with CLAUDE.md and the live bot before making the change;
  the user chose to proceed anyway. Practical effect: the audit-trail
  property of `data/` is gone going forward — `hadr-monitor[bot]`'s
  scheduled commits will now find nothing to add (the paths are ignored)
  and the store's history from this point on lives only on whatever
  machine runs the pipeline, not in git. Nothing in `agent/`, `scripts/`,
  or the test suite changed; `pipeline.store` still reads/writes the same
  paths on disk, so the pipeline itself is unaffected — only its
  version-control visibility is. If this needs to be reversed later, the
  fix is: revert this commit, then let the next monitor/daily run
  re-populate and re-commit `data/` from a live fetch (do not hand-restore
  the untracked snapshot from this session — see the note above about
  `data/news.json` being unexercised test/replay content, not real
  output).
