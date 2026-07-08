"""Severity gate — deterministic, per hazard (PRD §5).

The gate decides what counts as an event of record. The model may later
*add* an editorial Green but never remove; nothing here calls a model.

A merged canonical event is admitted if **any** of its lanes admits it:

- GDACS lane (all six hazard types): in when ``alertlevel`` **or**
  ``episodealertlevel`` is Orange+; ``istemporary == "true"`` never in
  (the temporary flag blocks only the GDACS lane — a solid USGS record can
  still admit the merged event).
- USGS earthquake lane: in when PAGER ≥ yellow, or ``sig`` ≥ 600, or
  M ≥ 5.5 with depth < 70 km. Below M 4.5 never in — enforced by polling
  the ``4.5_day`` feed, the filter is the feed choice.
"""

from __future__ import annotations

ORANGE_PLUS = {"orange", "red"}
PAGER_YELLOW_PLUS = {"yellow", "orange", "red"}


def _sources(event: dict) -> list[str]:
    return event.get("sources") or [event["source"]]


def gate_reason(event: dict) -> str | None:
    """Why this event clears the gate, or None if it does not."""
    sources = _sources(event)

    if "gdacs" in sources and not event["is_temporary"]:
        if event["alert_level"] in ORANGE_PLUS:
            return f"GDACS alert {event['alert_level']}"
        if event["episode_alert_level"] in ORANGE_PLUS:
            return f"GDACS episode alert {event['episode_alert_level']}"

    if "usgs" in sources:
        if event["pager"] in PAGER_YELLOW_PLUS:
            return f"PAGER {event['pager']}"
        if (event["sig"] or 0) >= 600:
            return f"sig {event['sig']} ≥ 600"
        magnitude, depth = event["magnitude"], event["depth_km"]
        if magnitude is not None and depth is not None and magnitude >= 5.5 and depth < 70:
            return f"M {magnitude} at {depth} km depth"

    return None


def apply_gate(events: list[dict]) -> list[dict]:
    """Return the gated-in events, each annotated with its ``gate_reason``."""
    gated = []
    for event in events:
        reason = gate_reason(event)
        if reason is not None:
            gated.append({**event, "gate_reason": reason})
    return gated


def green_candidates(events: list[dict]) -> list[dict]:
    """Gated-out Greens the model may promote with an editorial label.

    Deterministic pre-selection only — the promotion itself is the model's
    call (PRD §5) and is rendered with a mandatory ``EDITORIAL`` chip.
    """
    return [
        event
        for event in events
        if gate_reason(event) is None
        and not event.get("is_temporary")
        and (event.get("alert_level") == "green" or event.get("episode_alert_level") == "green")
    ]
