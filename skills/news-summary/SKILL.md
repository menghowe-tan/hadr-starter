# Skill: news-summary

**Model:** `claude-opus-4-8` (same call as the daily assessment — this is not
a separate model step; it is one extra capability given to the existing
call in `agent/assess.py`'s `ClaudeAssessor`). Uses the Anthropic API's
native `web_search_20250305` server tool, so no separate search API key is
needed beyond `ANTHROPIC_API_KEY`.

## Why this skill exists

`goal.md`'s standing orders end every report with what the pipeline cannot
see: tsunami warnings (no NOAA feed), and anything conflict/epidemic/
displacement-shaped, which only reaches this agent through ReliefWeb's
curated lag of days. GDACS, USGS and ReliefWeb are all *polled* sources —
none of them let the agent go looking for a fast-moving story the moment it
breaks. This skill gives the model one more tool, live web search, so a
sitrep can say "here is what the wires are already reporting" about an
event that is on record, or about a disaster the deterministic feeds have
not caught up to yet.

## What it is not

It does not gate, rank, merge, or decide what counts as an "event" — that
boundary (CLAUDE.md: deterministic before generative) does not move. A
news item is commentary attached to the pipeline's own decisions, never a
replacement for one. The model cannot use a news search result to promote,
demote, or invent an event; `validate_assessment` enforces that a
`news_item`'s `event_id`, when set, must already be a known event.

## Repeatable capability

Given the day's active + candidate-green events (the same context
`build_context` already assembles), the model may call `web_search` a
handful of times and return a `news_items` list. Each item is:

| field          | meaning                                                             |
|----------------|----------------------------------------------------------------------|
| `headline`     | the article's own headline, not a paraphrase                        |
| `source`       | the outlet name (e.g. "Reuters", "Al Jazeera") — never invented      |
| `url`          | the article URL — every item must be checkable                      |
| `published_at` | the article's own date, best effort, empty string if unknown         |
| `event_id`     | a known event this corroborates, or `""` for a standalone development |
| `note`         | one plain sentence: why a reader should care                        |

Copy rules (mirrors `agent/assess.py`'s `SYSTEM_PROMPT`):

- **Attribution is mandatory.** No source name and URL, no item — this is
  the one hard gate a news item must clear.
- **Sparing, not exhaustive.** Zero news items is often the right answer;
  this is a supplement for a fast-moving or under-covered story, not a
  running news ticker.
- **Label it, don't launder it.** A news item is unverified web reporting,
  never a `Reported` impact figure — it renders in its own zone
  ("News mentions"), separate from the impact lines that carry the
  `Estimated`/`Reported` provenance labels (design §5, render.py's
  `VALID_IMPACT_LABELS`). It never substitutes for a ReliefWeb confirmation.

## Where it lands

`agent/assess.py` returns `news_items` alongside `summary`/`change_notes`/
`editorial_greens`. `agent/daily.py` persists it to the committed store as
`data/news.json` (`{"checked_at", "items"}`) — the same "committed JSON is
the database" convention as everything else under `data/`. That one file
is what makes both renders honest without either of them calling a model:

- `scripts/pipeline/render.py` reads it from the day's `assessment` and
  renders a "News mentions" zone in `reports/sitrep.html` — the document a
  model wrote *this morning*.
- `scripts/render_dashboard.py` reads `data/news.json` straight off disk
  and renders the same items in `out/dashboard/index.html` — a script that
  never calls a model, showing what the model found *last time it ran*
  (the news search only happens once a day, on the gated sitrep run; the
  15-minute monitor loop is unchanged and stays fully model-free).

When the model does not run (`QUIET` verdict, or `--assess off`),
`data/news.json` is left exactly as it was — same carry-forward logic as
the manifest's `deploy_state` — so the dashboard never regresses to "no
news" just because nothing else changed overnight.
