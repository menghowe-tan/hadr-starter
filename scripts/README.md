Deterministic checks live here — anything that must give the same answer twice does not belong in a prompt. Nothing under `scripts/` ever calls a model; the generative layer lives in `agent/` (see CLAUDE.md).

## Layout (slices V1–V3)

- `run.py` — CLI: one invocation = one **monitor** cycle, model-free.
  `--replay <fixture-dir>` replays captured feeds; without it, one polite
  live fetch per feed. Prints the verdict (`CHANGED`/`QUIET`) as its final
  line, and the machine-readable feed health (`scripts/health.py`) on the
  line before it, plus `GITHUB_OUTPUT` (`verdict`, `health`) for the
  monitor workflow. Exits 3 (`health.ABORT_EXIT_CODE`) when both real-time
  feeds are down. The daily sitrep CLI (the only place a model wakes) is
  `agent/daily.py` — same health/output/exit-code contract, plus the gated
  model assessment.
- `health.py` — PRD §7 truth table (ok/degraded/abort) shared by `run.py`,
  `agent/daily.py` and `render_dashboard.py`.
- `render_dashboard.py` — deterministic Leaflet dashboard over
  `data/manifest.json` + `data/events/*.json`: alert-coloured markers,
  current event list, per-feed freshness chips, degraded banner. Writes
  `out/dashboard/index.html`.
- `deploy.py` — pushes `out/` to Netlify, idempotent via a content hash
  kept in `data/manifest.json`'s `deploy_state` (carried forward by
  `pipeline.runner.run_cycle` across cycles).
- `pipeline/` — the model-free pipeline, in PRD §3 order:
  - `fetch` — raw payloads per feed, live or replayed; per-feed
    ok/down status (a down feed degrades, never crashes).
  - `normalise` — UTC, canonical events, USGS `ids` union.
  - `merge` — tiered cross-feed identity (PRD §6): GLIDE → spatiotemporal
    (30 min / 100 km, cross-feed only, greedy by Δt) → tier-3 `possible`
    cross-references. Confidence + evidence on every merged event.
  - `reliefweb` — the RSS lane behind the `ReliefWebSource` adapter
    (API slot awaits the appname); event↔umbrella links, many-to-many.
  - `gate` — PRD §5 severity gate over merged events (any lane admits);
    also pre-selects the Green candidates the model may promote.
  - `diff` — vs our own stored state, classified per the supersession
    policy: new / escalated / revised / updated / downgraded / aged-out /
    withdrawn (withdrawn only after `details` confirms deletion).
  - `details` — per-event detail lookups; the only proof of deletion.
  - `rank` — deterministic severity ordering (escalations → level →
    exposure). The script orders, the model writes.
  - `store` — committed JSON under `data/`.
  - `render` — the real sitrep document (design spec §§3–5): six zones,
    inline styles, self-contained, provenance-labelled figures. Writes
    into gitignored `reports/`; generated views are never committed.
