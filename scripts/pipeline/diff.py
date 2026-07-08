"""Diff the gated fetch against our own stored state (PRD §8) and classify
every movement under the supersession policy (PRD §4 #5; design §5).

"Since last report" is always a diff against the store, never against
yesterday's fetch. The verdict is ``CHANGED`` or ``QUIET``.

Change kinds (glyphs are the render's job):

- ``new`` — never seen before.
- ``escalated`` (▲) — the GDACS alert level (event or episode) rose.
- ``revised`` (△) — magnitude, PAGER, location or depth moved.
- ``updated`` (△) — a new episode on a continuing event, a reappearance,
  a ReliefWeb link, or any other fingerprint movement.
- ``downgraded`` (▽) — the alert level fell; when it falls below the gate
  the event is reported once in "Noted, quieter", then dropped
  (status ``below-gate``).
- ``aged-out`` — an active stored event missing from the rolling window.
- ``withdrawn`` (✕) — asserted **only** after the per-event detail endpoint
  confirms deletion; vanished ≠ deleted (PRD §7). Without a confirmer,
  everything vanished is aged-out.

Escalation/downgrade reads the GDACS alert levels only; PAGER movement is a
*revision* by design (design §5 — PAGER is a different model, not an alert
state). USGS matching runs against the union of ``ids`` — an event whose
preferred id flipped networks still matches its stored record (PRD §6). The
stored ``event_id`` stays canonical; alias unions are merged.

When a feed was not fetched this run (``fetched_sources``), its events are
*not* aged out — blindness is not absence (PRD §7).
"""

from __future__ import annotations

import hashlib
import json
from typing import Callable

from pipeline.merge import haversine_km

VERDICT_CHANGED = "CHANGED"
VERDICT_QUIET = "QUIET"

# The fields whose movement means "something changed" (PRD §5: diff on
# episodeid/datemodified, not fromdate). The alias union is deliberately
# excluded — a preferred-id flip is not news. Umbrella links are included:
# a ground report arriving is news.
FINGERPRINT_FIELDS = (
    "alert_level",
    "episode_alert_level",
    "episode_id",
    "magnitude",
    "pager",
    "lat",
    "lon",
    "depth_km",
    "updated_at",
    "title",
    "gate_reason",
    "umbrellas",
)

LEVEL_RANK = {"green": 1, "yellow": 2, "orange": 3, "red": 4}
_RANK_NAME = {rank: name for name, rank in LEVEL_RANK.items()}


def fingerprint(event: dict) -> str:
    material = json.dumps(
        {field: event.get(field) for field in FINGERPRINT_FIELDS}, sort_keys=True
    )
    return hashlib.sha256(material.encode()).hexdigest()


def _has_gdacs(event: dict) -> bool:
    return "gdacs" in (event.get("sources") or [event.get("source")])


def effective_level_rank(event: dict) -> int:
    """The GDACS alert state (event or episode, whichever is higher)."""
    return max(
        LEVEL_RANK.get(event.get("alert_level"), 0),
        LEVEL_RANK.get(event.get("episode_alert_level"), 0),
    )


def classify(old: dict, new: dict) -> tuple[str, str | None]:
    """``(kind, detail)`` for a matched event whose fingerprint moved."""
    if _has_gdacs(old) and _has_gdacs(new):
        old_rank, new_rank = effective_level_rank(old), effective_level_rank(new)
        if old_rank != new_rank:
            detail = (
                f"{_RANK_NAME.get(old_rank, 'none')} → {_RANK_NAME.get(new_rank, 'none')}"
            )
            return ("escalated", detail) if new_rank > old_rank else ("downgraded", detail)

    revisions = []
    if old.get("magnitude") != new.get("magnitude"):
        revisions.append(f"magnitude {old.get('magnitude')} → {new.get('magnitude')}")
    if old.get("pager") != new.get("pager"):
        revisions.append(f"PAGER {old.get('pager') or 'pending'} → {new.get('pager') or 'pending'}")
    coords = (old.get("lat"), old.get("lon"), new.get("lat"), new.get("lon"))
    if all(value is not None for value in coords):
        moved_km = haversine_km(*coords)
        if moved_km >= 5.0:
            revisions.append(f"epicentre moved {moved_km:.0f} km")
    depths = (old.get("depth_km"), new.get("depth_km"))
    if all(value is not None for value in depths) and abs(depths[0] - depths[1]) >= 5.0:
        revisions.append(f"depth {depths[0]:g} → {depths[1]:g} km")
    if revisions:
        return "revised", "; ".join(revisions)

    if old.get("episode_id") != new.get("episode_id"):
        return "updated", f"new episode on a continuing event (episode {new.get('episode_id')})"
    if (old.get("umbrellas") or []) != (new.get("umbrellas") or []):
        return "updated", "ReliefWeb situation report linked"
    return "updated", None


def _change(event_id: str, kind: str, detail: str | None = None) -> dict:
    entry = {"event_id": event_id, "change": kind}
    if detail:
        entry["detail"] = detail
    return entry


def _match_stored(event: dict, stored: dict[str, dict], alias_index: dict[str, str]) -> str | None:
    if event["event_id"] in stored:
        return event["event_id"]
    for alias in event["ids"]:
        if alias in alias_index:
            return alias_index[alias]
    return None


def _build_alias_index(records: dict[str, dict]) -> dict[str, str]:
    return {
        alias: event_id
        for event_id, record in records.items()
        for alias in record.get("ids", [])
    }


def diff_and_update(
    stored: dict[str, dict],
    gated: list[dict],
    now_iso: str,
    *,
    all_events: list[dict] | None = None,
    fetched_sources: set[str] | None = None,
    confirm_withdrawal: Callable[[dict], bool] | None = None,
) -> tuple[str, list[dict], dict[str, dict]]:
    """Return ``(verdict, changes, updated_store)``.

    ``updated_store`` is a new mapping; ``stored`` is not mutated.
    ``all_events`` (the merged, pre-gate set) lets a still-present event
    that fell below the gate be reported as downgraded rather than aged
    out; without it, vanished-from-gate means vanished.
    """
    store = {event_id: dict(record) for event_id, record in stored.items()}
    alias_index = _build_alias_index(store)

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
            changes.append(_change(event["event_id"], "new"))
            continue

        record = store[match]
        reappeared = record.get("status") != "active"
        if new_fingerprint != record.get("fingerprint") or reappeared:
            kind, detail = classify(record, event)
            if reappeared and kind == "updated" and detail is None:
                detail = "re-entered the feed window"
            changes.append(_change(match, kind, detail))
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

    current_index = _build_alias_index(
        {event["event_id"]: event for event in (all_events or [])}
    )
    current_by_id = {event["event_id"]: event for event in (all_events or [])}

    for event_id, record in store.items():
        if event_id in seen or record.get("status") != "active":
            continue
        sources = record.get("sources") or [record.get("source")]
        if fetched_sources is not None and not all(s in fetched_sources for s in sources):
            continue  # its feed was down this run: blindness, not absence

        # Still present in the feed, just below the gate now?
        current = current_by_id.get(event_id)
        if current is None:
            for alias in record.get("ids", []):
                if alias in current_index:
                    current = current_by_id[current_index[alias]]
                    break
        if current is not None:
            kind, detail = classify(record, current)
            if kind != "downgraded":
                kind = "downgraded"
                detail = detail or "below the severity gate"
            changes.append(_change(event_id, kind, detail))
            record.update(
                {
                    key: current.get(key)
                    for key in FINGERPRINT_FIELDS
                    if key not in ("gate_reason",)
                }
            )
            record["status"] = "below-gate"
            record["fingerprint"] = fingerprint(record)
            record["last_seen"] = now_iso
            continue

        if confirm_withdrawal is not None and confirm_withdrawal(record):
            record["status"] = "withdrawn"
            record["withdrawn_at"] = now_iso
            changes.append(_change(event_id, "withdrawn", "deletion confirmed at the detail endpoint"))
        else:
            record["status"] = "aged-out"
            record["aged_out_at"] = now_iso
            changes.append(_change(event_id, "aged-out"))

    verdict = VERDICT_CHANGED if changes else VERDICT_QUIET
    return verdict, changes, store
