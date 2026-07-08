"""Model assessment: the plain-language layer of the sitrep (PRD §3, §5).

The model writes three things and only three things:

1. the summary prose — the lay reader's whole page (design §4);
2. change-note prose — one plain sentence per changed event;
3. editorial promotions — notable Greens, each with a reason; the render
   pairs every one with a mandatory ``EDITORIAL`` chip.

It never gates, never ranks, never merges — the deterministic pipeline did
all of that before the model woke (the script orders, the model writes).
``validate_assessment`` enforces that boundary: the model may *add* an
editorial Green but never invent events.

Assessors are plain callables ``(context) -> assessment`` so tests can
substitute spies and recordings; ``uv run pytest`` never talks to a model.
"""

from __future__ import annotations

import json
from pathlib import Path

MODEL = "claude-opus-4-8"
MAX_TOKENS = 4096

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
"""

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
    },
    "required": ["summary", "change_notes", "editorial_greens"],
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
    }


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
    return assessment


class ClaudeAssessor:
    """Live headless call through the official Anthropic SDK."""

    def __call__(self, context: dict) -> dict:
        import anthropic  # lazy: tests never need the live lane

        client = anthropic.Anthropic()
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            thinking={"type": "adaptive"},
            system=SYSTEM_PROMPT,
            output_config={"format": {"type": "json_schema", "schema": ASSESSMENT_SCHEMA}},
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Write the sitrep language for this morning's data.\n\n"
                        + json.dumps(context, ensure_ascii=False, indent=1)
                    ),
                }
            ],
        )
        if response.stop_reason == "refusal":
            raise RuntimeError("model declined the assessment request")
        text = next(block.text for block in response.content if block.type == "text")
        return _normalise(json.loads(text))


class RecordedAssessor:
    """Replays a recorded model output (``assessment.json``) — the fixture
    lane that keeps ``uv run pytest`` deterministic and offline."""

    def __init__(self, path: Path):
        self.path = Path(path)

    def __call__(self, context: dict) -> dict:
        return _normalise(json.loads(self.path.read_text()))
