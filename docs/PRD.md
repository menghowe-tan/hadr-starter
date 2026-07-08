# PRD — HADR Morning Sitrep Agent

**Status:** Draft for review · **Date:** 2026-07-08 · **Owner:** menghowe
**Sources:** repo README, `feeds/*.md` dossiers, PRD interview (16 answers, `PLAN.md`)

> This file is the **source of truth** for product decisions. `prd.html` is a
> rendered view generated from it; `PLAN.md` is the superseded pre-PRD record.

## 1. Problem

Disaster information on day zero is fragmented, noisy, and constantly revised.
GDACS, USGS and ReliefWeb each tell a partial story at a different latency —
raw physics in minutes, modeled impact in hours, human confirmation in days —
and none of them is a morning briefing. People who need to know "what happened
overnight, how bad is it, and what changed since yesterday" currently have to
read three feeds, mentally dedupe them, and remember what was already known.

This product is an unattended agent that does that reading, on two cadences
*(revised 2026-07-08 — see decisions #17–19)*:

- a **monitor loop** fetches the feeds regularly (target: every 5 minutes)
  and keeps a **live dashboard** current — the map and event list always
  reflect the latest fetch, with its freshness visible;
- a **daily sitrep** at **08:30 Singapore time** summarises the previous
  day's events and changes in a mailable report that filters the noise,
  merges the feeds into single events, distinguishes estimates from
  confirmed reports, and says explicitly what changed — including when the
  honest answer is "nothing".

## 2. Audience & user stories

The sitrep is layered for three readers at once (interview #1):

| Reader | Story |
|---|---|
| **Lay reader** | "I read the top of the report and understand in plain language what happened in the world overnight, without knowing what GDACS is." |
| **Humanitarian analyst** | "Below the summary I get severity-ranked events with sources, alert levels, estimated-vs-reported impact labels, merge confidence, and links to the raw records — enough to act on or verify." |
| **Leadership** | "I can glance at the map or the summary and know whether anything needs attention today, and I can trust silence: a quiet report means the pipeline ran and found nothing, not that it broke." |

## 3. Solution overview

One pipeline, two cadences — deterministic first, generative second (the
repo's one architectural rule). The **monitor loop** (every ~5 min) runs
fetch → normalise → merge → diff and, on change, updates `data/` and
redeploys the dashboard — it **never** calls a model. The **daily sitrep
run** (08:30 SGT) gates on what changed since the previous sitrep and wakes
the model only then:

```
fetch → normalise → merge → diff → gate ──(anything changed?)──> model assessment → render
  │         │         │       │      │                                │
GDACS     UTC,      tiered  vs own  per-hazard                 sitrep document
USGS      typed     identity stored severity                   + map data
ReliefWeb schema    merge    state  thresholds                 (both deployed
                                                                externally)
```

- **Fetch/normalise/merge/diff/gate** live in `scripts/`, are pure Python, and
  never call a model. They decide *whether* the model wakes up.
- **Model assessment** runs headless only when the gate says something changed:
  it writes the plain-language summary, ranks events, applies editorial
  judgment on notable Greens, and drafts the "changed since last report" notes.
- **Render** produces two artefacts from the same event store:
  1. a **self-contained HTML sitrep document** — the daily 08:30 SGT summary
     of the previous day (inline styles, no external requests, mailable —
     doubles as the course's `dashboard.html` artefact);
  2. a **live dashboard** — interactive Leaflet map plus current event list,
     markers coloured by alert level, click for event detail, OSM tiles
     (external dependency at view time accepted); redeployed by the monitor
     loop whenever the store changes, always showing last-fetch time per
     feed.
- **System of record:** committed JSON in the repo (`data/`) — one file per
  canonical merged event plus a run manifest. Documents and the map are
  generated *views* over it and are **not committed**; they deploy to an
  external host (Netlify/Vercel class) via a token in Actions secrets.
- **Contracts:** every seam in the diagram above — the event schema, the
  manifest, the stage CLIs, the assessment file, the `out/` layout — is
  frozen in §13 so the three slices can be built independently.

## 4. Decisions

Each row is an interview answer; the *Blindspot* column traces it to the
briefing in `PLAN.md` where applicable.

| # | Decision | Detail | Blindspot |
|---|---|---|---|
| 1 | Audience: all three layers | Plain-language summary up top; severity-ranked sourced detail beneath | — |
| 2 | Geography: global | No regional weighting | — |
| 3 | Hazards: all six GDACS types | EQ, TC, FL, VO, DR, WF — accepts per-hazard diff semantics work | §3 hazard types break "event" |
| 4 | Severity bar: Orange+ always, editorial Greens | See §5 gate table | §4 noise economics |
| 5 | Supersession: changelog + prominence | Every reported event carries a "changed since last report" note; escalations get top prominence; downgrades/withdrawals noted but quieter. Requires stored prior state. **Interpretation of "options 1+3" — confirm in review.** | §§2, 6, 8 |
| 6 | Quiet morning: explicit "all quiet" sitrep | Includes feed-health banner | §7 replay/quiet demoable |
| 7 | Feed down: fail loudly | No sitrep; alert instead. Missing data is worse than no report. See §7 for the degraded-vs-abort threshold | §10 blindness |
| 8 | Identity: tiered deterministic merge | GLIDE when present, else hazard type + time window + distance; confidence tag surfaced in the report | §5 many-to-many identity |
| 9 | Stack: Python + uv | Gates everything; recorded in `CLAUDE.md` | — |
| 10 | State: committed JSON | In-repo store under `data/` | §6 no backfill |
| 11 | ReliefWeb: RSS-first behind an adapter | appname requested Day 1; API drops in on approval | §6 RSS = last ~20 items |
| 12 | Publishing: no committed dashboard | Generated views deploy externally; event data is the committed artefact | — (deviation from README assumption, recorded in `implementation-notes.md`) |
| 13 | Committed JSON **is** the database | Git history is the audit trail; views are derived | — |
| 14 | Sendable document: self-contained HTML | Inline styles, no external requests, mailable | — |
| 15 | Hosting: external (Netlify/Vercel/S3 class) | Nothing generated committed to main; host choice + deploy token = Day-1 task | — |
| 16 | Map: interactive Leaflet | Alert-level colours, click-through detail, OSM tiles | — |
| 17 | Fetch cadence: regular, ~5 min target *(2026-07-08 clarification)* | GDACS + USGS polled by the monitor loop; ReliefWeb hourly (days-latency by design). Final cadence decided in slice V3 against Actions cron jitter and minutes quota — see §12 | §4 noise economics |
| 18 | Dashboard is the live surface *(2026-07-08 clarification)* | Deterministic render redeployed on every store change with per-feed freshness stamps; no model in the monitor loop | — |
| 19 | Sitrep is the daily summary *(2026-07-08 clarification)* | One report at 08:30 SGT covering events and changes since the previous sitrep (the previous day); the only place the model writes | — |
| 20 | Contract-first slices *(2026-07-08)* | Schemas + stage interfaces frozen in §13; slices V1–V3 build against contracts and shared fixtures, not against each other; the scheduled sitrep is enabled only at integration | — |

## 5. Severity gate (per hazard)

The gate is deterministic and runs in `scripts/`; the model may *add* (promote
a notable Green with an explicit "editorial" label) but never remove.

| Hazard | Always in | Never in (deterministically) |
|---|---|---|
| All six GDACS types | `alertlevel` **or** `episodealertlevel` ≥ Orange | `istemporary == "true"` events |
| Earthquake (USGS lane) | PAGER `alert` ≥ yellow, or `sig` ≥ 600, or M ≥ 5.5 with depth < 70 km | Below M 4.5 (poll `4.5_day`, not `all_day` — the filter is the feed choice) |
| Tropical cyclone | Orange+ **episode** on an already-reported storm re-enters the report | — |
| Drought / flood | Orange+; diff on `episodeid`/`datemodified`, **not** `fromdate` | Re-reporting an unchanged long-running event |

Severity fields are **model outputs, not observations** (GDACS `alertscore`,
USGS PAGER both forecast impact). The sitrep labels every impact number as
**Estimated** (model) or **Reported** (ReliefWeb / textual confirmation) —
never bare.

## 6. Identity & merge rule

Two records merge into one canonical event by the first tier that matches:

| Tier | Rule | Confidence tag |
|---|---|---|
| 1 | GLIDE numbers equal (non-empty) | `confirmed` |
| 2 | Same hazard type, origin times within 30 min, epicentres within 100 km | `high` |
| 3 | Same hazard type + country, within 24 h | `possible` — shown, not merged silently |

- The mapping is **many-to-many**: one ReliefWeb "disaster" (country-level
  umbrella) may cover several physical events; the store models
  event↔umbrella links, not a foreign key.
- USGS identity is the **union of `ids`** (network prefix can flip); dedup
  runs against the union, never the single `id`.
- A script decides merges; the model only *explains* them.

## 7. Run semantics: quiet, degraded, down

**Monitor loop** (every ~5 min): a failed cycle skips silently — the next
cycle retries; the dashboard keeps showing the last good data with its
per-feed last-success stamp, and marks a feed **stale** once it is older
than 3 × the cadence. Persistent failure (≥ 1 hour without a success on a
real-time feed) raises the alert without waiting for the morning run.

**Daily sitrep run** (08:30 SGT):

| Condition | Behaviour |
|---|---|
| All feeds fetched, gate says no change | Publish explicit **"all quiet"** sitrep with feed-health banner (last-success timestamps) |
| One feed stale/unreachable, others fresh | **Degraded publish**: sitrep goes out with a prominent per-feed warning ("GDACS unreachable since …; earthquake coverage continues via USGS") |
| GDACS **and** USGS both unreachable, or the event store unreadable | **Abort loudly**: no sitrep; the workflow fails and alerts. ReliefWeb alone cannot see today. |

Threshold rationale: ReliefWeb is days-latency by design, so its absence never
blocks a morning report; losing both real-time feeds means the report would be
blind, which answer #7 treats as worse than no report.

Vanished events: an event missing from a rolling window is **aged-out until
proven deleted** — the per-event detail endpoint disambiguates before the
sitrep says "withdrawn".

## 8. Time handling

- Normalise everything to **UTC internally** at fetch time: GDACS naive strings
  are declared UTC, USGS epoch-ms, RSS RFC-822. Render in SGT only at the view
  layer.
- "Since last report" = diff against **our own stored state**, never against
  yesterday's fetch (rolling windows double-count or gap at boundaries). The
  monitor loop's frequent polling also closes the boundary gaps a
  once-a-day sample of a rolling window would leave.
- The sitrep's window is **since the previous sitrep** (≈ the previous day,
  ending at generation).
- Schedule the sitrep workflow at **00:00 UTC** targeting an 08:30 SGT
  (00:30 UTC) publish — GitHub cron fires late; the margin is the point.
  The monitor loop's cadence is a target, not a promise: Actions cron at
  5 min jitters by minutes; the dashboard's freshness stamp is the honest
  signal.

## 9. Answers to the dossier open questions

**GDACS 1 — which alert level?** Report the event-level `alertlevel`; the gate
also watches `episodealertlevel` so an escalating episode re-triggers. Yes,
colours change after publication — that is exactly what the supersession
policy (§4 #5) handles.

**GDACS 2 / ReliefWeb 2 — what ties feeds together?** GLIDE when present
(reliable only in ReliefWeb, days later); otherwise the spatiotemporal tiers
in §6. `source: "NEIC"` in GDACS means the earthquake lane is USGS-derived —
agreement between them is an echo, not confirmation, and the sitrep must not
present it as corroboration.

**GDACS 3 / ReliefWeb 3 — polite polling & limits?** *(revised 2026-07-08)*
The monitor loop polls GDACS + USGS every ~5 minutes (USGS regenerates every
minute; GDACS gets conditional requests where honoured — verify
`If-Modified-Since`, §12) and ReliefWeb hourly, matching its days-latency
curation. Per-event detail fetches happen only for gated-in events;
exponential backoff on 4xx/5xx, and a cycle that fails is skipped, not
retried in a burst. Feed-down behaviour is §7.

**USGS 1 — which id?** Store the union of `ids` as the identity set (§6).

**USGS 2 — revisions under a published report?** Supersession policy: the next
sitrep carries a changed-since note; escalations lead, downgrades and
deletions are noted quietly; deletion is asserted only after the detail
endpoint confirms it (§7).

**USGS 3 — PAGER values?** `green / yellow / orange / red`, a modeled
fatality/loss forecast that arrives late and gets revised. It maps to the gate
(§5) and is always labelled *Estimated*; it is a different model from GDACS's
score, so disagreement between them is expected and shown, not resolved.

**ReliefWeb 1 — build against what?** RSS-first behind a `ReliefWebSource`
adapter interface; the API implementation drops in when the appname is
approved. The RSS lacks structured fields, queryability and history beyond
~20 items — accepted as an interim cost.

## 10. Out of scope

- Tsunami **warnings** (USGS `tsunami: 1` only means a message exists; real
  warnings live with NOAA — a fourth source we don't have). The sitrep states
  this blindness.
- Conflict, epidemic and displacement coverage beyond ReliefWeb's curated lag.
- Push notifications / paging; historical backfill beyond replay fixtures.
- Intraday **sitreps** — the dashboard updates continuously, but the model
  writes one report per day.

## 11. Day-1 deliverables carried by this PRD

1. **Replay fixtures** — a real historical Orange/Red event captured from the
   query APIs (`fdsnws-event`, GDACS search) plus a genuinely quiet morning;
   the pipeline must run against fixtures before it runs live.
2. **ReliefWeb appname request** submitted today (form + email confirmation
   has a clock we don't control).
3. **Host choice + deploy token** in Actions secrets.
4. **Contract freeze** *(added 2026-07-08)* — JSON Schema files under
   `schemas/` and the contract fixtures of §13.6; slice work starts only
   after these exist, because they are what makes V1–V3 independent (§13).

## 12. Open items for review

- **#5 interpretation**: "options 1+3 combined" was read as
  changelog-on-every-event *plus* prominence-for-escalations — confirm.
- **#6/#7 tension**: the degraded-vs-abort threshold in §7 (ReliefWeb never
  blocks; both real-time feeds down aborts) is proposed, not user-confirmed.
- External host: Netlify vs Vercel vs S3 — recommend Netlify or Vercel with a
  deploy token; decide before wiring the workflow.
- Volatile facts to verify live during Day-1 slicing: ReliefWeb current
  rate-limit guidance, GDACS `If-Modified-Since` support, exact window of
  `EVENTS4APP`.
- **Monitor-loop cadence vs GitHub Actions** *(added 2026-07-08)*: a 5-min
  cron is Actions' minimum, jitters badly at busy hours, and ~288 runs/day
  consumes the free-tier minutes quota within days. Options at V3: accept
  paid minutes, relax to 15 min, or move the loop off Actions (small always-on
  runner). Cadence is a V3 decision; the PRD commits to "regular, with
  visible freshness", not to a number.

## 13. Contracts: schemas & interfaces *(added 2026-07-08 — slice decoupling)*

The three slices (`docs/SLICES.md`, issues #3–#5) are implemented
**independently, against contracts, not against each other**. Everything one
slice consumes from another is frozen here as a schema or an interface, and
shared fixtures stand in for the producing slice until integration. The
contracts carry a version field (`"schema": 1`) and are enforced as JSON
Schema files under `schemas/` plus contract fixtures under `tests/fixtures/`
— both are Day-1 artefacts (§11 #4). Changing a contract afterwards touches
all three slice issues and is recorded in `implementation-notes.md`.

### 13.1 Canonical event — `data/events/<event-id>.json`

One committed file per canonical merged event (decisions #10, #13). The `id`
is minted once from the first-seen record (`<hazard>-<origin-date>-<seq>`)
and never changes; identity *matching* always uses the `identity` block
(§6), never the `id`.

| Block | Fields |
|---|---|
| root | `schema` (1) · `id` · `hazard` (`EQ TC FL VO DR WF`) |
| `identity` | `glide` · `usgs_ids` (the **union**, §6) · `gdacs_event_id` · `gdacs_episode_id` · `reliefweb_ids` |
| `times` | `origin_utc` · `first_seen_utc` · `last_changed_utc` — ISO-8601 UTC (`…Z`), §8 |
| `geo` | `lat` · `lon` · `country_iso3` · `place_name` |
| `severity` | `gdacs_alertlevel` · `gdacs_episode_alertlevel` · `pager_alert` · `usgs_sig` · `magnitude` · `depth_km` — nullable by lane |
| `impact[]` | `{metric, value, label, source}` — `label` is **required**, `estimated` or `reported` (§5); a bare figure is schema-invalid |
| `merge` | `tier` (1/2/3/null) · `confidence` (`confirmed` / `high` / `possible` / `single-source`) · `delta_t_min` · `delta_km` |
| `links` | `reliefweb_umbrellas[]` — many-to-many event↔umbrella (§6) |
| `change` | `status` (`NEW ESCALATED REVISED UPDATED DOWNGRADED WITHDRAWN AGED_OUT UNCHANGED`) · `summary` (deterministic, e.g. "alertlevel Orange→Red") · `since_utc` (§4 #5, §7) |
| `sources[]` | `{feed, fetched_utc, record}` — trimmed raw records, the audit trail |

`change.summary` is written by the deterministic classifier; model prose
about a change lives only in the assessment (13.4).

### 13.2 Run manifest — `data/manifest.json`

The gate's machine-readable output. Workflows and renders condition on this
file, never on parsing logs.

| Field | Meaning |
|---|---|
| `schema` | 1 |
| `run_utc` | when this cycle ran |
| `verdict` | `CHANGED` / `QUIET` |
| `changed_event_ids[]` | the model step's entire input scope |
| `feeds.<name>` | `{last_success_utc, status: ok/stale/down}` — dashboard freshness stamps; degraded/abort input (§7) |
| `previous_sitrep_utc` | the sitrep diff anchor (§8) |

### 13.3 Pipeline stage interfaces

Every stage is separately invocable, JSON in / JSON out, with `--replay
<dir>` supported wherever a feed would otherwise be touched:

| Stage | Reads | Writes |
|---|---|---|
| `fetch --feed gdacs\|usgs\|reliefweb` | live feed or fixture | raw snapshot JSON (feed-shaped) |
| `normalise` | raw snapshots | normalised records JSON |
| `merge` | normalised records + `data/` | canonical events (13.1) |
| `diff` (gate) | canonical events + prior `data/` | updated `data/` + manifest (13.2) |
| assess (model) | manifest + store, read-only | `assessment.json` (13.4) |
| `render --view sitrep\|dashboard` | `data/` + `assessment.json` | `out/` (13.5) |

Composed-run exit codes: `0` published or quiet (including degraded), `3`
deliberate abort-blind per §7, any other non-zero an unexpected failure.
Manifest verdict + exit code are the whole workflow-facing surface — both
testable with stubs.

### 13.4 Model assessment — `assessment.json`

The model reads the store and manifest, writes one uncommitted run artefact,
and never touches `data/`:

```json
{ "schema": 1, "generated_utc": "…Z", "summary_md": "…",
  "events": { "<event-id>": { "note_md": "…" } },
  "editorial_promotions": [ { "event_id": "…", "reason_md": "…" } ] }
```

Promotions may only *add* (§5); render stamps them with the mandatory
`editorial` label. A canned assessment fixture lets every render build and
run model-free.

### 13.5 Render & deploy interface

Render writes `out/sitrep/<date>.html` (self-contained, mailable) and
`out/dashboard/` (map + event list). Deploy publishes `out/` idempotently.
Nothing under `out/` is ever committed (decision #12).

### 13.6 Fixtures as stand-ins

| Fixture | Conforms to | Stands in for |
|---|---|---|
| `tests/fixtures/<scenario>/raw/` | the feed shapes | the live feeds (V1's input; captured Day-1, §11 #1) |
| `tests/fixtures/<scenario>/store/` | 13.1 + 13.2 | **V1's output** — hand-authored Day-1, so V2/V3 never wait on V1 |
| `tests/fixtures/assessment/` | 13.4 | the model step |

Scenarios: eventful, quiet, escalation pair (morning-1/2), GDACS+USGS merge
pair, ReliefWeb umbrella. When real V1 output later diverges from a store
fixture, that is a contract bug to resolve, not a silent fixture update.

### 13.7 What each slice consumes and produces

| Slice | Consumes (frozen) | Produces (must validate) | Stand-ins until integration |
|---|---|---|---|
| V1 | raw fixtures (13.6) | `data/` per 13.1–13.2; skeleton pages in the 13.5 layout | none — head of the pipeline |
| V2 | store fixtures (13.6) · assessment interface (13.4) | merge + classifier writing 13.1 blocks; model step; the real sitrep render | store fixtures replace V1; canned assessment replaces the live model |
| V3 | manifest verdict + exit codes (13.2–13.3) · `out/` layout (13.5) | both workflows, deploy, the dashboard | stage stubs honouring 13.3 replace V1 + V2 |

Independence covers implementation and each slice's demo. **Enabling** the
scheduled sitrep still requires the real gate (V1) and the real model step
(V2) wired in — the repo's architectural rule — so `sitrep.yml` ships
`.disabled` and integration becomes a merge-and-flip step, not a build
dependency.
