"""Model assessment: the plain-language layer of the sitrep (PRD §3, §5).

The model writes four things:

1. the summary prose — the lay reader's whole page (design §4);
2. change-note prose — one plain sentence per changed event;
3. editorial promotions — notable Greens, each with a reason; the render
   pairs every one with a mandatory ``EDITORIAL`` chip;
4. news items (skills/news-summary/SKILL.md) — attributed web-search
   results, corroborating a known event or flagging a standalone
   development the deterministic feeds haven't reflected yet.

1–3 stay behind the sitrep gate: ``agent/daily.py`` only calls the full
assessor when the deterministic pipeline says ``CHANGED`` (CLAUDE.md: "the
model never decides whether to wake up", tested by
``test_model_wakes_only_when_the_gate_says_changed``). News items are the
one exception, by request: a quiet morning by GDACS/USGS/ReliefWeb's own
alert thresholds can still be the morning a fast-moving story breaks that
none of those feeds have caught yet, so ``search_news`` runs on *every*
daily run regardless of verdict — a second, narrower model call, never the
gated one. It never gates, never ranks, never merges — the deterministic
pipeline did all of that before either model call (the script orders, the
model writes). ``validate_assessment``/``validate_news_items`` enforce that
boundary: the model may *add* an editorial Green or a news item but never
invent events, and a news item's ``event_id``, when set, must already be
on the known-events list.

Assessors are plain callables ``(context) -> assessment`` so tests can
substitute spies and recordings; ``uv run pytest`` never talks to a model.
The live lane is the one departure from "deterministic before generative"
(CLAUDE.md): ``web_search`` is a generative, non-deterministic input. It is
fenced off the same way everything else here is — mandatory attribution,
a dedicated "News mentions" zone never mixed with the ``Estimated``/
``Reported`` impact lines, and written only to committed JSON
(``data/news.json``) so the render layers themselves stay model-free.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

# ``anthropic.Anthropic()`` already reads ANTHROPIC_BASE_URL/
# ANTHROPIC_AUTH_TOKEN/ANTHROPIC_API_KEY from the environment itself (no
# code needed here) — this is only for the model id, which this module
# otherwise hardcodes. ANTHROPIC_MODEL is the repo-wide override
# (harness/agent.py uses the same name); ANTHROPIC_DEFAULT_OPUS_MODEL is
# the Claude-Code-CLI tier-alias convention, honoured too since a proxied
# backend (a non-Anthropic ANTHROPIC_BASE_URL) is set up with that name.
MODEL = (
    os.environ.get("ANTHROPIC_MODEL")
    or os.environ.get("ANTHROPIC_DEFAULT_OPUS_MODEL")
    or "claude-opus-4-8"
)
MAX_TOKENS = 6000

# skills/news-summary/SKILL.md: search is now a KEYLESS LOCAL tool
# (agent/tools.py's web_search — DuckDuckGo over httpx), not Anthropic's
# server web_search, so this lane needs no ANTHROPIC_API_KEY for search. The
# model requests it like any client tool; _call_structured runs it and feeds
# the result back, then the model emits the schema-constrained JSON. (A
# project that has a key and prefers server-side execution can pass a server
# tool instead — the loop below skips block types it doesn't execute.)

SYSTEM_PROMPT = """\
You write the daily plain-language layer of a humanitarian disaster sitrep.
A deterministic pipeline has already fetched, merged, gated and ranked the
events; you only put them into words. Copy rules (non-negotiable):

- Summary: about five sentences, for a lay reader. People and places, no
  jargon, no acronyms, no feed names (never say GDACS, USGS, PAGER,
  ReliefWeb). Magnitude follows geography ("near Mandalay, Myanmar
  (magnitude 7.7)"), never coordinates.
- Estimates hedge, reports do not: modeled figures are "possible" or
  "estimated"; never state a modeled number as fact.
- Echoes are not corroboration: two feeds carrying the same detection is
  one source, not confirmation.
- Change notes: one short sentence per changed event, plain language,
  focused on what moved since the last report.
- Editorial greens: you may promote a below-gate green event only when it
  is genuinely notable to a global humanitarian reader; give a one-line
  reason. Promote sparingly — zero is often right.
- News items: you may call the web_search tool to check for recent news
  coverage of today's events, or of a fast-moving disaster the feeds
  haven't caught yet. Every item needs a real source name and a URL you
  actually found — never invent either; drop the item if you can't back
  it with both. Set event_id to a known event this corroborates, or leave
  it "" for a standalone development. This is unverified web reporting,
  not a feed confirmation — write the note accordingly, and skip the
  search entirely when there's nothing worth surfacing.
"""

# skills/news-summary/SKILL.md's standalone call — runs every day
# regardless of verdict, so its prompt has no sitrep-writing framing.
NEWS_SYSTEM_PROMPT = """\
You check for recent news coverage of a humanitarian-disaster monitor's
current events, and for any fast-moving disaster its feeds haven't caught
yet. You are not writing the sitrep; a separate call does that only when
the deterministic pipeline says something changed. You run every day
regardless, because a quiet morning by that pipeline's own thresholds can
still be the morning a story breaks that none of its feeds have caught.

- Call the web_search tool to check; don't guess from memory.
- Every item needs a real source name and a URL you actually found — never
  invent either; drop the item if you can't back it with both.
- Set event_id to a known event this corroborates, or leave it "" for a
  standalone development the deterministic feeds haven't reflected yet.
- This is unverified web reporting, not a feed confirmation — write the
  note accordingly.
- Return no items when nothing is worth surfacing — zero is often right.
"""

NEWS_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string"},
        "source": {"type": "string"},
        "url": {"type": "string"},
        "published_at": {"type": "string"},
        "event_id": {"type": "string"},
        "note": {"type": "string"},
    },
    "required": ["headline", "source", "url", "published_at", "event_id", "note"],
    "additionalProperties": False,
}

# Structured-outputs schema: no dynamic keys (additionalProperties must be
# false), so change notes and promotions are lists of {event_id, ...}.
ASSESSMENT_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "change_notes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "event_id": {"type": "string"},
                    "note": {"type": "string"},
                },
                "required": ["event_id", "note"],
                "additionalProperties": False,
            },
        },
        "editorial_greens": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "event_id": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["event_id", "reason"],
                "additionalProperties": False,
            },
        },
        "news_items": {"type": "array", "items": NEWS_ITEM_SCHEMA},
    },
    "required": ["summary", "change_notes", "editorial_greens", "news_items"],
    "additionalProperties": False,
}

# The standalone news-only call's schema — one field, no sitrep prose.
NEWS_SCHEMA = {
    "type": "object",
    "properties": {"news_items": {"type": "array", "items": NEWS_ITEM_SCHEMA}},
    "required": ["news_items"],
    "additionalProperties": False,
}


def build_context(cycle: dict) -> dict:
    """The model's working set: active events, this run's changes, and the
    green candidates it may promote. Trimmed to what the prose needs."""

    def brief(event: dict) -> dict:
        return {
            key: event.get(key)
            for key in (
                "event_id",
                "hazard",
                "title",
                "country",
                "magnitude",
                "depth_km",
                "alert_level",
                "episode_alert_level",
                "alert_score",
                "pager",
                "occurred_at",
                "gate_reason",
                "umbrellas",
                "merge",
                "possible_related",
                "source_titles",
            )
        }

    store = cycle["store"]
    manifest = cycle["manifest"]
    return {
        "run_at": manifest["run_at"],
        "verdict": manifest["verdict"],
        "feeds": manifest["feeds"],
        "changes": manifest["changes"],
        "events": [
            brief(record)
            for record in store.values()
            if record.get("status") == "active"
        ],
        "candidate_greens": [brief(event) for event in cycle["candidates"]],
    }


def _normalise_news_items(raw_items: list[dict] | None) -> list[dict]:
    # Attribution is the one hard gate (SKILL.md): no source + url, no
    # item, regardless of what else the model filled in.
    return [
        {
            "headline": (entry.get("headline") or "").strip(),
            "source": (entry.get("source") or "").strip(),
            "url": (entry.get("url") or "").strip(),
            "published_at": (entry.get("published_at") or "").strip(),
            "event_id": (entry.get("event_id") or "").strip() or None,
            "note": (entry.get("note") or "").strip(),
        }
        for entry in raw_items or []
        if (entry.get("source") or "").strip() and (entry.get("url") or "").strip()
    ]


def _normalise(raw: dict) -> dict:
    return {
        "summary": (raw.get("summary") or "").strip(),
        "change_notes": {
            entry["event_id"]: entry["note"]
            for entry in raw.get("change_notes") or []
            if entry.get("event_id") and entry.get("note")
        },
        "editorial_greens": [
            {"event_id": entry["event_id"], "reason": entry.get("reason") or ""}
            for entry in raw.get("editorial_greens") or []
            if entry.get("event_id")
        ],
        "news_items": _normalise_news_items(raw.get("news_items")),
    }


def validate_news_items(items: list[dict], context: dict) -> list[dict]:
    """Shared by the gated assessment and the always-runs news-only call:
    a news item may corroborate a known event but never an invented one
    (PRD §5's invention guard, extended to this skill), and every item must
    carry real attribution. Raises ``ValueError`` on violation."""
    known = {event["event_id"] for event in context["events"]}
    for item in items:
        if not item.get("source") or not item.get("url"):
            raise ValueError("news item missing source attribution")
        if item.get("event_id") and item["event_id"] not in known:
            raise ValueError(f"news item references unknown event: {item['event_id']}")
    return items


def validate_assessment(assessment: dict, context: dict) -> dict:
    """The model may add an editorial Green but never remove or invent
    (PRD §5). Raises ``ValueError`` on violation; returns the assessment."""
    if not assessment.get("summary"):
        raise ValueError("model assessment has no summary")
    known = {event["event_id"] for event in context["events"]}
    for event_id in assessment.get("change_notes", {}):
        if event_id not in known:
            raise ValueError(f"change note for unknown event: {event_id}")
    candidates = {event["event_id"] for event in context["candidate_greens"]}
    for pick in assessment.get("editorial_greens", []):
        if pick["event_id"] not in candidates:
            raise ValueError(f"editorial promotion of a non-candidate: {pick['event_id']}")
        if not pick.get("reason"):
            raise ValueError(f"editorial promotion without a reason: {pick['event_id']}")
    validate_news_items(assessment.get("news_items", []), context)
    return assessment


MAX_ROUNDS = 10  # pause_turn resumes; a real answer never needs many


def _parse_json_maybe_fenced(text: str) -> dict | None:
    candidate = text
    if candidate.startswith("```"):
        candidate = candidate.strip("`").strip()
        if candidate.lower().startswith("json"):
            candidate = candidate[4:].strip()
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return None


def _extract_json(text_blocks: list[str]) -> dict | None:
    """Anthropic's own API puts the schema-constrained JSON in the final
    text block, verbatim. A relay proxying a different model behind the
    same wire format (a non-Anthropic ANTHROPIC_BASE_URL) may not honour
    ``output_config`` that precisely — a trailing whitespace-only block,
    the JSON landing in an earlier block, wrapped in a markdown code fence,
    or buried in commentary ("Here's the JSON: {...} let me know..."), have
    all been observed. Try every non-blank block, most recent first: first
    the whole block (plain or fenced), then the widest {...} substring in
    it. Return ``None`` if nothing parses anywhere."""
    for text in reversed(text_blocks):
        candidate = text.strip()
        if not candidate:
            continue
        parsed = _parse_json_maybe_fenced(candidate)
        if parsed is not None:
            return parsed
        start, end = candidate.find("{"), candidate.rfind("}")
        if start != -1 and end > start:
            parsed = _parse_json_maybe_fenced(candidate[start : end + 1])
            if parsed is not None:
                return parsed
    return None


def _json_only_instruction(schema: dict) -> str:
    """``output_config``'s json_schema mode is an Anthropic-API guarantee;
    a relay behind a different ANTHROPIC_BASE_URL may accept the parameter
    and then ignore it, letting the model write normal prose instead (seen
    live: a GLM-backed relay wrote a markdown sitrep with no JSON in it at
    all). This is the fallback that doesn't depend on the backend honouring
    that parameter — spelled out in the prompt itself, so it works whether
    or not the structured-output guarantee actually holds."""
    return (
        "\n\nYour entire response must be exactly one JSON object — no "
        "markdown, no code fence, no commentary before or after it — "
        "matching this JSON Schema:\n" + json.dumps(schema, ensure_ascii=False)
    )


def _run_search(search_tool, block) -> dict:
    """Execute one local-tool call the model requested, as a ``tool_result``
    to feed back. Mirrors ``harness/agent.py``'s tool runner: an exception
    comes back to the model as an error it can adapt to, never a crash."""
    result = {"type": "tool_result", "tool_use_id": block.id}
    if search_tool is None or block.name != search_tool.name:
        return result | {"content": f"unknown tool: {block.name}", "is_error": True}
    try:
        return result | {"content": search_tool.fn(**block.input)}
    except Exception as exc:  # the model gets the error and can adapt
        return result | {"content": f"{type(exc).__name__}: {exc}", "is_error": True}


def _call_structured(client, system: str, schema: dict, search_tool, user_content: str):
    """One structured-output call that lets the model search first.

    ``search_tool`` is a local ``harness.Tool`` (agent/tools.py's keyless
    ``web_search``): when the model requests it (``stop_reason == "tool_use"``)
    we run it and feed the result back, the same client-side loop
    ``harness/agent.py`` runs — no ANTHROPIC_API_KEY needed for search. A
    ``pause_turn`` (a server tool, if one were ever passed) resumes the same
    way: resend the turn unchanged. Every round carries ``output_config`` so
    the model's final, non-tool turn is the schema-constrained JSON.

    Returns ``(parsed_json, searched)`` — ``searched`` is whether the model
    actually invoked the search tool, distinct from its answer being empty
    because it looked and found nothing worth surfacing."""
    messages = [{"role": "user", "content": user_content}]
    tool_params = [search_tool.to_param()] if search_tool is not None else []
    response = None
    searched = False
    for _ in range(MAX_ROUNDS):
        request: dict = dict(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            thinking={"type": "adaptive"},
            system=system + _json_only_instruction(schema),
            output_config={"format": {"type": "json_schema", "schema": schema}},
            messages=messages,
        )
        if tool_params:
            request["tools"] = tool_params
        response = client.messages.create(**request)
        if response.stop_reason == "refusal":
            raise RuntimeError("model declined the request")
        searched = searched or any(
            (block.type == "tool_use" and search_tool is not None
             and block.name == search_tool.name)
            or block.type in ("server_tool_use", "web_search_tool_result")
            for block in response.content
        )
        if response.stop_reason == "tool_use":
            messages = messages + [
                {"role": "assistant", "content": response.content},
                {
                    "role": "user",
                    "content": [
                        _run_search(search_tool, block)
                        for block in response.content
                        if block.type == "tool_use"
                    ],
                },
            ]
            continue
        if response.stop_reason == "pause_turn":
            messages = messages + [{"role": "assistant", "content": response.content}]
            continue
        break
    else:
        raise RuntimeError(f"still working after {MAX_ROUNDS} rounds")

    if response.stop_reason == "max_tokens":
        raise RuntimeError(
            f"model response truncated at max_tokens={MAX_TOKENS} before writing "
            "the structured output — raise MAX_TOKENS or trim the context"
        )
    # Search rounds (tool_use/tool_result, or server_tool_use/web_search_
    # tool_result) and thinking blocks are already behind us; the final turn's
    # text is the schema-constrained JSON.
    text_blocks = [block.text for block in response.content if block.type == "text"]
    parsed = _extract_json(text_blocks)
    if parsed is None:
        raise RuntimeError(
            f"model response has no parseable JSON (stop_reason="
            f"{response.stop_reason!r}, block types="
            f"{[b.type for b in response.content]!r}, text blocks="
            f"{[t[:200] for t in text_blocks]!r})"
        )
    return parsed, searched


class ClaudeAssessor:
    """Live headless call through the official Anthropic SDK."""

    def __call__(self, context: dict) -> dict:
        import anthropic  # lazy: tests never need the live lane

        from .tools import WEB_SEARCH  # keyless local search (no API key)

        raw, searched = _call_structured(
            anthropic.Anthropic(),
            SYSTEM_PROMPT,
            ASSESSMENT_SCHEMA,
            WEB_SEARCH,
            "Write the sitrep language for this morning's data.\n\n"
            + json.dumps(context, ensure_ascii=False, indent=1),
        )
        assessment = _normalise(raw)
        assessment["searched"] = searched
        return assessment

    def search_news(self, context: dict) -> dict:
        """skills/news-summary/SKILL.md's standalone call — independent of
        the sitrep gate, so ``agent/daily.py`` can run it every day."""
        import anthropic  # lazy: tests never need the live lane

        from .tools import WEB_SEARCH  # keyless local search (no API key)

        raw, searched = _call_structured(
            anthropic.Anthropic(),
            NEWS_SYSTEM_PROMPT,
            NEWS_SCHEMA,
            WEB_SEARCH,
            "Check today's disaster news.\n\n"
            + json.dumps(context, ensure_ascii=False, indent=1),
        )
        return {"items": _normalise_news_items(raw.get("news_items")), "searched": searched}


class RecordedAssessor:
    """Replays a recorded model output (``assessment.json``) — the fixture
    lane that keeps ``uv run pytest`` deterministic and offline."""

    def __init__(self, path: Path):
        self.path = Path(path)

    def __call__(self, context: dict) -> dict:
        return _normalise(json.loads(self.path.read_text()))

    def search_news(self, context: dict) -> dict:
        """Replays the same fixture's news_items, for exercising the
        always-runs news path (test_sitrep_e2e.py) without a live call.
        ``searched`` is unknowable from a static recording — ``None``."""
        raw = json.loads(self.path.read_text())
        return {"items": _normalise_news_items(raw.get("news_items")), "searched": None}
