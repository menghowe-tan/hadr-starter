# HADR Monitor

A monitoring agent for humanitarian assistance and disaster response (HADR),
built over three days with Claude Code.

## The end state

By Wednesday afternoon this repository contains an agent that:

- watches live disaster feeds — GDACS, USGS and ReliefWeb (see [`feeds/`](feeds/))
- filters out the noise and assesses what remains: what happened, where, how bad, who is affected
- publishes a live map dashboard (redeployed every monitor cycle) and a
  morning situation report at 08:30 Singapore time, both to an external host
- runs on a schedule, unattended, and stays quiet when nothing has changed

How it does any of that is not specified anywhere in this repository. That is
the course.

## The three days

| Day | Theme | You will |
|-----|-------|----------|
| 1 | **Plan** | Interrogate the feeds, write the PRD, cut it into vertical slices |
| 2 | **Autonomy** | Build the first slice, write a skill, wire up the 08:30 routine, launch the overnight loop |
| 3 | **Trust** | Review code you didn't write, harden the pipeline, demo |

## Day 1 setup

1. Sign in to Claude Code with your Team seat
2. Create your own repository from this template, then clone it
3. Run `/install-github-app` so @claude reviews your pull requests from Day 2
4. Install OpenCode and sign in with your Go key
5. Fill in `CLAUDE.md` **before your first prompt** — every agent session
   inherits it, so an empty one means every session re-guesses your language,
   test command and conventions

One more thing with a clock you don't control: the ReliefWeb API requires a
pre-approved `appname`, requested via a form and confirmed by email. Request it
on Day 1 — see [`feeds/reliefweb.md`](feeds/reliefweb.md) for the details and
the no-approval RSS fallback.

## What's in this repository

```
feeds/                    Dossiers on the three feeds: verified endpoints,
                          example responses, and open questions each feed
                          poses. Read these before writing the PRD.
scripts/                  Deterministic checks. Anything that must give the
                          same answer twice does not belong in a prompt.
skills/                   Skills you write on Day 2, one folder per skill:
                          a SKILL.md, supporting assets, and a note on which
                          model each step should use.
docs/solutions/           One learning per file. When something costs you more
                          than ten minutes, the fix goes here so no future
                          session pays for it twice. Grep it before debugging.
implementation-notes.md   Kept by the agent, reviewed by you: decisions, open
                          questions, deviations. An undocumented deviation is
                          a bug.
CLAUDE.md                 Project instructions every agent session loads.
                          Yours to fill in.
.github/workflows/        @claude PR review, the 15-min monitor loop, and
                          the morning sitrep — see "Running the system" below.
.github/ISSUE_TEMPLATE/   Templates for vertical slices and for filing issues
                          against a neighbour's skill.
```

## Running the system

Everything below works offline, against the replay fixtures under
[`tests/fixtures/`](tests/fixtures/) — no network access or API key needed
until you switch to `live`.

```
uv run pytest                                              # 98 tests, deterministic and offline

# One monitor cycle: fetch → normalise → merge → gate → diff → store → dashboard skeleton
uv run scripts/run.py --replay tests/fixtures/eventful
uv run scripts/run.py                                       # live: one polite fetch per feed

# The daily sitrep — the only place a model wakes, and only when the gate says CHANGED
uv run agent/daily.py --replay tests/fixtures/eventful --assess off        # no model, deterministic fallback
uv run agent/daily.py --replay tests/fixtures/morning-1 --assess recorded  # replays a committed assessment.json
uv run agent/daily.py --assess live                                        # live fetch + live model (needs ANTHROPIC_API_KEY)

# Render the live Leaflet dashboard from the committed store, then deploy out/ to Netlify
uv run scripts/render_dashboard.py
uv run scripts/deploy.py --dry-run                          # hash + decide, never calls the host
uv run scripts/deploy.py                                    # needs NETLIFY_AUTH_TOKEN + NETLIFY_SITE_ID
```

Both CLIs print the verdict (`CHANGED`/`QUIET`) as their final line and exit
`3` if GDACS and USGS are both down (`scripts/health.py`'s abort path,
PRD §7) — a blind morning is worse than no report.

Unattended, two GitHub Actions workflows run this same code:
[`monitor.yml`](.github/workflows/monitor.yml) every 15 minutes (dashboard
only) and [`sitrep.yml`](.github/workflows/sitrep.yml) daily at 00:00 UTC
(targeting an 08:30 SGT publish). Both are also dispatchable on demand from
the Actions tab with a `scenario` input — `eventful`, `quiet`, `gdacs-down`,
`both-down` (replays a fixture under `tests/fixtures/`) or `live`.

## The one architectural rule

[`.github/workflows/sitrep.yml`](.github/workflows/sitrep.yml) encodes the
shape the pipeline must take:

1. a **deterministic script** decides whether anything changed;
2. a **headless model call** runs only if it did.

The model never decides whether to wake up.

## Working conventions

- **Vertical slices.** Each unit of work is one thin feature that runs end to
  end, filed with the [slice issue template](.github/ISSUE_TEMPLATE/slice.md):
  a one-sentence goal, a definition of done a reviewer can verify in two
  minutes, and an explicit out-of-scope list so nobody — human or agent —
  helpfully builds ahead.
- **Deterministic before generative.** Fetching, diffing, dedup and change
  detection live in `scripts/` and never call a model. The model's job is
  assessment and writing, gated behind the deterministic check.
- **Write down what it cost you.** Fixes that took more than ten minutes go in
  `docs/solutions/` as `YYYY-MM-DD-short-slug.md` — symptom, cause, fix, terse.
- **Deviations are recorded, not discovered.** Anything built that departs from
  the PRD or `CLAUDE.md` goes in `implementation-notes.md` with the reason.

## The feeds, at a glance

| Feed | What it is | Access | Character |
|------|-----------|--------|-----------|
| [GDACS](feeds/gdacs.md) | EU/UN multi-hazard alerts: earthquakes, cyclones, floods, volcanoes, drought, wildfires | Open GeoJSON + RSS | Colour-coded alert levels; no published rate limits |
| [USGS](feeds/usgs.md) | Real-time earthquake feed | Open GeoJSON, regenerated every minute | Fast and raw; events get revised and occasionally deleted |
| [ReliefWeb](feeds/reliefweb.md) | UN OCHA's curated humanitarian record | API needs a pre-approved appname; RSS is open | Slow and human-verified: a disaster appears once people decide it matters |

Each dossier ends with open questions — identity across feeds, revisions after
publication, polite polling, behaviour when a feed is down. Your PRD should
answer them; your agent will meet them either way.

## Artefacts expected by the end

| Artefact | What it proves |
|----------|----------------|
| `prd.html` | You interrogated the feeds and made the product calls |
| `system-view.html` | You can explain the architecture you ended up with |
| `dashboard.html` | The agent publishes; this is the morning sitrep itself |
| `goal.md` | The standing objective the unattended agent works toward |
| `implementation-notes.md` | The agent kept honest records and you read them |
| at least one skill | You taught the agent a repeatable capability |
