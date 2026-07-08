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

This product is an unattended agent that does that reading: every morning at
**08:30 Singapore time** it publishes a situation report that filters the
noise, merges the feeds into single events, distinguishes estimates from
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

A daily pipeline, deterministic first, generative second (the repo's one
architectural rule):

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
  1. a **self-contained HTML sitrep document** (inline styles, no external
     requests, mailable — doubles as the course's `dashboard.html` artefact);
  2. an **interactive Leaflet map page** — markers coloured by alert level,
     click for event detail, OSM tiles (external dependency at view time
     accepted).
- **System of record:** committed JSON in the repo (`data/`) — one file per
  canonical merged event plus a run manifest. Documents and the map are
  generated *views* over it and are **not committed**; they deploy to an
  external host (Netlify/Vercel class) via a token in Actions secrets.

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
  yesterday's fetch (rolling windows double-count or gap at boundaries).
- Schedule the workflow at **00:00 UTC** targeting an 08:30 SGT (00:30 UTC)
  publish — GitHub cron fires late; the margin is the point.

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

**GDACS 3 / ReliefWeb 3 — polite polling & limits?** One fetch per feed per
run (daily), plus per-event detail fetches only for gated-in events;
conditional requests where honoured; exponential backoff on 4xx/5xx and never
more than one retry burst per run. Feed-down behaviour is §7.

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
- Multi-run intraday updates (the design allows it later; Day 1–3 ships one
  morning run).

## 11. Day-1 deliverables carried by this PRD

1. **Replay fixtures** — a real historical Orange/Red event captured from the
   query APIs (`fdsnws-event`, GDACS search) plus a genuinely quiet morning;
   the pipeline must run against fixtures before it runs live.
2. **ReliefWeb appname request** submitted today (form + email confirmation
   has a clock we don't control).
3. **Host choice + deploy token** in Actions secrets.

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
