"""Severity gate — deterministic, per hazard (PRD §5).

The gate decides what counts as an event of record. The model (V2) may
later *add* an editorial Green but never remove; nothing here calls a model.

- GDACS (all six hazard types): in when ``alertlevel`` **or**
  ``episodealertlevel`` is Orange+; ``istemporary == "true"`` never in.
- USGS earthquake lane: in when PAGER ≥ yellow, or ``sig`` ≥ 600, or
  M ≥ 5.5 with depth < 70 km. Below M 4.5 never in — enforced by polling
  the ``4.5_day`` feed, the filter is the feed choice.
"""

from __future__ import annotations

ORANGE_PLUS = {"orange", "red"}
PAGER_YELLOW_PLUS = {"yellow", "orange", "red"}


def gate_reason(event: dict) -> str | None:
    """Why this event clears the gate, or None if it does not."""
    if event["source"] == "gdacs":
        if event["is_temporary"]:
            return None
        if event["alert_level"] in ORANGE_PLUS:
            return f"GDACS alert {event['alert_level']}"
        if event["episode_alert_level"] in ORANGE_PLUS:
            return f"GDACS episode alert {event['episode_alert_level']}"
        return None

    if event["source"] == "usgs":
        if event["pager"] in PAGER_YELLOW_PLUS:
            return f"PAGER {event['pager']}"
        if (event["sig"] or 0) >= 600:
            return f"sig {event['sig']} ≥ 600"
        magnitude, depth = event["magnitude"], event["depth_km"]
        if magnitude is not None and depth is not None and magnitude >= 5.5 and depth < 70:
            return f"M {magnitude} at {depth} km depth"
        return None

    return None


def apply_gate(events: list[dict]) -> list[dict]:
    """Return the gated-in events, each annotated with its ``gate_reason``."""
    gated = []
    for event in events:
        reason = gate_reason(event)
        if reason is not None:
            gated.append({**event, "gate_reason": reason})
    return gated
