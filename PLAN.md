# Blindspot pass: GDACS / USGS / ReliefWeb for a HADR monitor

> **Superseded by [`docs/PRD.md`](docs/PRD.md)** — every decision below was
> carried into the PRD's decisions table. This file remains as the record of
> *why*: the feed-blindspot briefing and the raw PRD interview.

## Context

You're building the 3-day HADR monitoring agent and have never worked with these
feeds. The `feeds/` dossiers already cover the basics (mutable USGS events, GDACS
alert levels, ReliefWeb appname approval). This briefing covers what the dossiers
*don't* say — the unknown unknowns — and ends with the PRD decisions each one
forces, so you can prompt with them instead of discovering them mid-build.

## 1. The three feeds are one pipeline, not three witnesses

Your GDACS example event says `"source": "NEIC"` — that's the USGS National
Earthquake Information Center. For earthquakes, GDACS **is** USGS data with an
impact model bolted on. The three feeds are not independent observers that
corroborate each other; they're three stages of the same story at different
latencies:

- **USGS**: minutes after the shaking. Raw physics, no impact judgment.
- **GDACS**: tens of minutes to hours. Same detection + a *modeled* impact
  estimate (population exposure × vulnerability) → the colour.
- **ReliefWeb**: days. Humans confirming what actually happened on the ground.

Consequence: "two feeds agree" is not confirmation for earthquakes — it's an
echo. And a disaster in ReliefWeb but not GDACS isn't a data bug; it's the
curation lag (or a hazard GDACS doesn't model). Your sitrep is always a
snapshot of a story still being revised.

## 2. Early severity is a model output, not an observation

Both severity signals you'll rely on are *forecasts*:

- GDACS `alertscore` = modeled population exposure + country vulnerability.
- USGS `alert` (the PAGER field from dossier open question 3) = modeled
  fatalities and economic loss — and it arrives *later* than the event itself,
  then gets revised.

Real "who is affected" numbers don't exist anywhere on day zero. GDACS Green/
Orange/Red and PAGER colours also disagree routinely (different models,
different questions). Your morning report needs to distinguish **estimated**
from **reported** impact explicitly, or it will state model guesses as fact.

## 3. Hazard types break the "event" abstraction in different ways

The dossiers show one earthquake each. Earthquakes are the *easy* case — a
point in space and an instant in time. The other GDACS hazards behave
differently:

- **Tropical cyclones** live for 1–3 weeks, accumulating episodes. The Point
  geometry is the *current storm centre* — often 500 km offshore from where the
  impact will be. One "event", dozens of updates, moving location.
- **Floods** have fuzzy start/end and fuzzy geography; GDACS flood detection is
  patchy compared to earthquakes.
- **Droughts** span months: `fromdate` is ancient, `datemodified` is today.
  Naive "new since yesterday" logic will either re-report a drought every
  morning or never mention it at all.

"What changed since the last sitrep?" needs a per-hazard-type answer, not one
diff rule.

## 4. Noise economics: the default feeds are mostly noise

`all_day.geojson` carries ~200–300 events on a normal day, dominated by M1–2
micro-quakes in California and Alaska — not because those places shake more,
but because **detection threshold follows sensor density**. Globally the
catalog is only complete down to ~M4.5. Meanwhile GDACS emits a steady stream
of Green events. Two traps hide here:

- Magnitude ≠ impact. A shallow M5.5 under a dense city outranks an M7.2 in
  the mid-Atlantic. Depth (the third coordinate in USGS geometry) and
  population matter more than the headline number.
- If you don't set severity thresholds *per hazard* up front, the agent either
  screams every morning or you'll bolt on filtering under time pressure on
  Day 2. Note USGS already offers pre-filtered windows (`4.5_week`,
  `significant_month`) — picking the right feed can replace a filtering layer.

## 5. Cross-feed identity is many-to-many, not a join key

The dossiers ask "what ties feeds together?" — the deeper trap is the shape of
the answer:

- **GLIDE** is the designed join key, but it's `""` on fresh GDACS events
  (assigned later, sometimes never) and only reliable in ReliefWeb, days after.
- A ReliefWeb "disaster" is a country-level umbrella ("Venezuela: Earthquakes –
  Jun 2026" covers *two* quakes). The mapping to physical events is
  **many-to-many**, not 1:1 — your data model needs to allow it.
- USGS event `id` can *change network prefix* when the preferred source flips
  (that's why `ids` is a list). Dedup against the union of `ids`, or yesterday's
  `us6000abcd` reappears today as `ci41287863` and you double-report.

Fallback matching is spatiotemporal (same hazard type + time window + distance),
with confidence tiers — decide in the PRD what confidence is enough to merge.

## 6. Rolling windows: vanished ≠ deleted, and there's no backfill

`all_day` is a rolling 24 h window, not a calendar day. An event missing from
the next poll either **aged out** or was **deleted** — indistinguishable from
the summary feed alone (the per-event detail endpoint resolves it). The
realtime feeds have no history: miss a poll, the data is gone. If you need
lookback, USGS has a separate query API (`fdsnws-event`), GDACS has a search
endpoint, and the ReliefWeb API is fully queryable — the RSS fallback is the
latest ~20 items only, which makes the appname approval more load-bearing than
it looks.

## 7. You can't demo on live disasters — build replay on Day 1

The Wednesday demo has a clock; Red-level disasters don't. On a quiet week your
pipeline's interesting path never fires naturally. The single highest-leverage
early move: **capture fixtures** (a real historical Orange/Red event pulled
from the query APIs above, plus a genuinely quiet morning) and make the
pipeline runnable against them. This also gives your deterministic
`scripts/` layer something to be tested with, and makes "stays quiet when
nothing changed" a demoable feature instead of an assertion.

## 8. Time is a trap in four separate ways

- GDACS timestamps are **naive strings** (`2026-07-06T11:29:36`, no zone — it's
  UTC, undeclared). USGS is epoch milliseconds UTC. RSS is RFC-822. Three
  formats, one of them ambiguous.
- Your report is 08:30 **Singapore** but every window is UTC; "today's events"
  in SGT straddles two UTC days.
- GitHub Actions cron fires late — minutes to tens of minutes at busy times.
  Schedule with margin if 08:30 is a hard promise.
- A rolling 24 h window sampled once a day can double-count or gap events at
  the boundary; diff against your own stored state, not against yesterday's
  fetch.

## 9. Parsing traps (small, but each costs 20 minutes)

- GDACS: `"istemporary": "false"` — booleans are strings; `glide` is `""` not
  null; the schema **varies by hazard type** (cyclones carry fields earthquakes
  don't).
- ReliefWeb RSS: the payload is HTML-escaped HTML with the taxonomy embedded in
  `<div class="tag glide">` elements — you're scraping semantics out of CSS
  classes.
- The list feeds are shallow; the riches (severity detail, exposure, polygons)
  are in per-event detail endpoints (`geteventdata`, ReliefWeb `fields`
  selection). Budget for the second fetch.

## 10. Know what the agent is blind to, and say so

No tsunami warnings (USGS `tsunami: 1` means a message *exists* — actual
warnings live with NOAA's tsunami centers, a fourth source you don't have). No
conflict, epidemic, or displacement signal except via ReliefWeb's slow curated
lane. GDACS wildfires/floods are far patchier than its earthquakes. A sitrep
that states its own coverage limits is more trustworthy than one that
implies omniscience.

## What this means for your PRD prompts

Each blindspot is a product decision to specify rather than let the agent guess:

1. **Severity threshold per hazard** — what makes the sitrep (e.g. GDACS
   Orange+, USGS `significant_*` or M ≥ 5.5 near population)?
2. **Supersession policy** — what does the report do when yesterday's event is
   revised, escalated Green→Red, or deleted?
3. **Identity rule** — when do two records merge (GLIDE match vs spatiotemporal
   confidence tiers), and does the model or a script decide?
4. **Estimate vs report** — how does the sitrep label modeled impact vs
   confirmed numbers?
5. **Quiet-morning and feed-down definitions** — what exactly is "nothing
   changed", and what does 08:30 say when a feed is unreachable?
6. **Replay fixtures** — name them as a Day-1 slice deliverable.

## Verification

This briefing is a knowledge deliverable — nothing to run. Volatile specifics
worth checking live during Day 1 slicing (not asserted as fact above):
ReliefWeb's current rate-limit guidance, whether GDACS honours
`If-Modified-Since`, and the exact window of the `EVENTS4APP` list endpoint.

---

# PRD interview (grill-with-docs, adapted)

Running the interview from bguiz/build-agent-skills `build-1-plan-product`,
adapted: no REQS.md exists, so the repo README + the user's stated goal stand
in as the initial idea; sub-skills (grill-with-docs, to-prd, shaping,
breadboarding) are not installed, so the grill runs inline. All questions
logged upfront per the skill's A1 step. PRD comes only after answers.

## QUESTIONS log

Product framing:
1. Who is the 08:30 sitrep for — you as a learner, humanitarian analysts, or an ops/leadership brief?
2. Geographic scope — global, Asia-Pacific weighted, or global with a regional lens?
3. Hazard scope — all six GDACS types, or start narrower (EQ/TC/FL, or EQ only)?
4. Severity bar — what earns a line in the report (Orange+, Red only, notable Greens)?

Behaviour semantics:
5. Supersession — what does the report do when an already-reported event is revised, escalated, or deleted?
6. Quiet morning — publish an "all quiet" sitrep, or stay silent?
7. Feed down — degrade visibly, skip silently, or alert?
8. Cross-feed identity — merge on GLIDE only (conservative), spatiotemporal matching with confidence tiers, or let the model judge at report time?

Delivery/tech:
9. Language/stack for `scripts/` (CLAUDE.md is empty — this decision gates everything)?
10. State between runs — committed JSON, SQLite, or stateless?
11. ReliefWeb appname — applied yet? Build API-first or RSS-first?
12. Dashboard — committed `dashboard.html` on Pages, or something else?

## Answers

1. **Audience**: all three — lay persons, humanitarian analysts, and leadership.
   Implies a layered sitrep: plain-language summary up top, severity-ranked
   sourced detail beneath.
2. **Geography**: global.
3. **Hazards**: all six GDACS types (accepts the drought/flood semantics work).
4. **Severity bar**: Orange+ always, plus notable Greens at editorial
   discretion (felt reports, populated areas).
5. **Revisions**: options 1+3 combined — every reported event carries a
   "changed since last report" note; escalations (Green→Orange→Red) get top
   prominence, downgrades/withdrawals noted but quieter. Needs stored prior
   state. *(Interpretation of "1 and 3" — confirm in PRD review.)*
6. **Quiet morning**: publish an explicit "all quiet" sitrep with feed health.
7. **Feed down**: fail the run loudly — no sitrep, alert instead. Missing data
   is treated as worse than no report. (Note tension with #6's feed-health
   banner: health display is for degraded-but-publishable mornings; hard feed
   failure aborts. Threshold between the two is a PRD decision.)
8. **Identity**: tiered deterministic merge — GLIDE when present, else
   hazard-type + time-window + distance, with a confidence tag surfaced in the
   report.
9. **Stack**: Python + uv.
10. **State**: JSON files committed to the repo.
11. **ReliefWeb**: appname not yet requested — apply immediately; build the
    ReliefWeb slice RSS-first behind an adapter so the API drops in on
    approval.
12. **Publishing** (user rejected all offered options): do NOT commit a
    regenerated dashboard.html daily. Instead: event data lives in a
    "database"; on top of it generate (a) a document for viewing and sending
    to other users, and (b) a webpage with a world-map view.
13. **Data store**: committed JSON *is* the database — system of record in
    git; documents and map are generated views over it.
14. **Sendable document**: self-contained HTML file (inline styles, mailable,
    doubles as the course's dashboard.html artefact).
15. **Hosting**: external host (Netlify/Vercel/S3 class) — nothing generated
    committed to main. Specific host + credentials setup is a Day-1 task;
    recommend Netlify or Vercel with a deploy token in Actions secrets.
16. **Map**: interactive Leaflet map, markers coloured by alert level, click
    for event detail; OSM tiles (external dependency at view time accepted).

---

# Plan: produce the PRD

With the grill complete, the next concrete deliverable is the PRD
(step B of the skill's process). On approval:

1. **Write `docs/PRD.md`** containing, per the skill's to-prd shape:
   - Problem statement and audience (three-layer readership, answer #1)
   - User stories per reader type
   - Solution description: the pipeline (fetch → normalise → merge → diff →
     gate → model assessment → render document + map data), the two-artefact
     output (sendable HTML sitrep + Leaflet map page on external host), and
     the committed-JSON event store as system of record
   - Decisions table: all 16 interview answers, each traced to its blindspot
     where applicable (severity bar, supersession, identity tiers, quiet/
     feed-down semantics, RSS-first ReliefWeb adapter)
   - Out of scope: tsunami warnings, conflict/epidemic coverage, push
     notifications, historical backfill beyond fixtures
   - Open items: external host choice + secrets; escalation-vs-changelog
     nuance (answer #5 interpretation); ReliefWeb appname approval timing
2. **Render `prd.html`** (course artefact) from the same content — a
   readable, self-contained page.
3. **Update `implementation-notes.md`** with the deviation from the README's
   assumed architecture (dashboard.html committed to repo → external hosting,
   with the user's reason) — the README calls an undocumented deviation a bug.
4. **Fill `CLAUDE.md`** minimally: Python + uv, test command placeholder,
   the committed-JSON store convention, deviations policy pointer.
5. Also do the two clock-bound Day-1 actions the interview surfaced:
   remind the user to submit the ReliefWeb appname form today; PRD marks
   RSS-first adapter as the interim path.

## Verification

- `docs/PRD.md` answers every open question posed in the three `feeds/*.md`
  dossiers (the README requires this of the PRD).
- All 16 interview answers appear in the PRD's decision table verbatim in
  spirit; the two flagged interpretations (#5, #7 tension) are called out for
  the user to confirm in review.
- `prd.html` opens standalone in a browser with no external requests.
