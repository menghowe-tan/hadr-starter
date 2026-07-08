"""Diff the gated fetch against our own stored state (PRD §8).

"Since last report" is always a diff against the store, never against
yesterday's fetch. The verdict is ``CHANGED`` or ``QUIET``.

Change kinds in V1 (full change-note classification is V2):

- ``new`` — never seen before.
- ``updated`` — fingerprint moved (alert level, episode, magnitude,
  location, ``datemodified``/``updated``), or an aged-out event reappeared.
- ``aged-out`` — an active stored event missing from the rolling window.
  Aged-out until proven deleted (PRD §7): V1 never calls it withdrawn.

USGS matching runs against the union of ``ids`` — an event whose preferred
id flipped networks still matches its stored record (PRD §6). The stored
``event_id`` stays canonical; alias unions are merged.
"""

from __future__ import annotations

import hashlib
import json

VERDICT_CHANGED = "CHANGED"
VERDICT_QUIET = "QUIET"

# The fields whose movement means "something changed" (PRD §5: diff on
# episodeid/datemodified, not fromdate). The alias union is deliberately
# excluded — a preferred-id flip is not news.
FINGERPRINT_FIELDS = (
    "alert_level",
    "episode_alert_level",
    "episode_id",
    "magnitude",
    "lat",
    "lon",
    "depth_km",
    "updated_at",
    "title",
    "gate_reason",
)


def fingerprint(event: dict) -> str:
    material = json.dumps(
        {field: event.get(field) for field in FINGERPRINT_FIELDS}, sort_keys=True
    )
    return hashlib.sha256(material.encode()).hexdigest()


def _match_stored(event: dict, stored: dict[str, dict], alias_index: dict[str, str]) -> str | None:
    if event["event_id"] in stored:
        return event["event_id"]
    for alias in event["ids"]:
        if alias in alias_index:
            return alias_index[alias]
    return None


def diff_and_update(
    stored: dict[str, dict], gated: list[dict], now_iso: str
) -> tuple[str, list[dict], dict[str, dict]]:
    """Return ``(verdict, changes, updated_store)``.

    ``updated_store`` is a new mapping; ``stored`` is not mutated.
    """
    store = {event_id: dict(record) for event_id, record in stored.items()}
    alias_index = {
        alias: event_id
        for event_id, record in store.items()
        for alias in record.get("ids", [])
    }

    changes: list[dict] = []
    seen: set[str] = set()

    for event in gated:
        match = _match_stored(event, store, alias_index)
        new_fingerprint = fingerprint(event)

        if match is None:
            store[event["event_id"]] = {
                **event,
                "status": "active",
                "first_seen": now_iso,
                "last_seen": now_iso,
                "fingerprint": new_fingerprint,
            }
            seen.add(event["event_id"])
            changes.append({"event_id": event["event_id"], "change": "new"})
            continue

        record = store[match]
        reappeared = record.get("status") != "active"
        if new_fingerprint != record.get("fingerprint") or reappeared:
            changes.append({"event_id": match, "change": "updated"})
        merged_ids = list(record.get("ids", []))
        merged_ids += [alias for alias in event["ids"] if alias not in merged_ids]
        store[match] = {
            **record,
            **event,
            "event_id": match,  # canonical id never flips with the alias
            "ids": merged_ids,
            "status": "active",
            "last_seen": now_iso,
            "fingerprint": new_fingerprint,
        }
        seen.add(match)

    for event_id, record in store.items():
        if event_id not in seen and record.get("status") == "active":
            record["status"] = "aged-out"
            record["aged_out_at"] = now_iso
            changes.append({"event_id": event_id, "change": "aged-out"})

    verdict = VERDICT_CHANGED if changes else VERDICT_QUIET
    return verdict, changes, store
