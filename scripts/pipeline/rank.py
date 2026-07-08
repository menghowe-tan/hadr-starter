"""Deterministic severity ranking (design §4): the script orders, the model
only writes.

Escalated events first (newest escalation on top), then alert level
Red → Orange → editorial Green, then modeled exposure (GDACS alert score,
then PAGER, then significance, then magnitude). ``event_id`` is the final
tiebreak so the order is stable across runs.
"""

from __future__ import annotations

from pipeline.diff import LEVEL_RANK

_PAGER_RANK = {"green": 1, "yellow": 2, "orange": 3, "red": 4}


def display_level_rank(record: dict) -> int:
    """The severity the reader should see: GDACS level or PAGER, whichever
    is higher (PAGER counts for ranking even though its movement is a
    *revision*, not an escalation)."""
    return max(
        LEVEL_RANK.get(record.get("alert_level"), 0),
        LEVEL_RANK.get(record.get("episode_alert_level"), 0),
        _PAGER_RANK.get(record.get("pager"), 0),
    )


def _exposure(record: dict) -> tuple:
    return (
        record.get("alert_score") or 0,
        _PAGER_RANK.get(record.get("pager"), 0),
        record.get("sig") or 0,
        record.get("magnitude") or 0,
    )


def sitrep_order(records: list[dict], changes_by_id: dict[str, dict]) -> list[dict]:
    """Order event records for the sitrep's event list."""

    def escalated(record: dict) -> bool:
        change = changes_by_id.get(record["event_id"])
        return bool(change) and change["change"] == "escalated"

    def key(record: dict) -> tuple:
        return (
            0 if escalated(record) else 1,
            # Newest escalation on top; irrelevant for the others.
            "" if not escalated(record) else _inverted(record.get("updated_at") or ""),
            -display_level_rank(record),
            tuple(-value for value in _exposure(record)),
            record["event_id"],
        )

    return sorted(records, key=key)


def _inverted(text: str) -> str:
    """Invert a string's sort order so newer ISO timestamps sort first."""
    return "".join(chr(0x10FFFF - ord(char)) for char in text)
