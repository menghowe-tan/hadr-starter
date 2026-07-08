"""Cross-feed identity: the tiered deterministic merge (PRD §6).

Two records become one canonical event by the first tier that matches:

- tier 1 — GLIDE numbers equal (non-empty) → ``confirmed``;
- tier 2 — same hazard, origin times within 30 min, epicentres within
  100 km → ``high``, and the evidence (Δt, Δd) is kept so the report can
  show its working;
- tier 3 — same hazard + country within 24 h → ``possible``: **never**
  merged, only cross-referenced (``possible_related``), rendered as two
  cards with a cross-reference line.

Two rules the PRD's table leaves implicit, both forced by the Mandalay
fixture and recorded in ``implementation-notes.md``:

- **Only records from different feeds merge.** A feed's own event ids are
  trusted as distinct physical events — the M 7.7 mainshock and the M 6.7
  aftershock are 11 min and 35 km apart, inside tier-2 thresholds, and must
  not collapse into one event.
- **Ambiguity resolves greedily by closest origin time, then distance**,
  one partner per feed per event — so the USGS mainshock (Δt 2 s) claims
  the GDACS mainshock before the aftershock can.

A script decides merges; the model only explains them (PRD §6).
"""

from __future__ import annotations

import re
from datetime import datetime
from math import asin, cos, radians, sin, sqrt

TIER2_WINDOW_SECONDS = 30 * 60
TIER2_RADIUS_KM = 100.0
TIER3_WINDOW_SECONDS = 24 * 3600

_SOURCE_ORDER = {"gdacs": 0, "usgs": 1, "reliefweb": 2}
_PARENTHETICAL = re.compile(r"\s*\([^)]*\)")


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    lat1, lon1, lat2, lon2 = map(radians, (lat1, lon1, lat2, lon2))
    a = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371.0 * asin(sqrt(a))


def _timestamp(event: dict) -> float | None:
    occurred = event.get("occurred_at")
    return datetime.fromisoformat(occurred).timestamp() if occurred else None


def _evidence(a: dict, b: dict) -> tuple[float, float] | None:
    """(Δt seconds, Δd km) between two records, or None if incomparable."""
    ta, tb = _timestamp(a), _timestamp(b)
    if ta is None or tb is None:
        return None
    coords = (a.get("lat"), a.get("lon"), b.get("lat"), b.get("lon"))
    if any(value is None for value in coords):
        return None
    return abs(ta - tb), haversine_km(*coords)


def countries_overlap(a: str | None, b: str | None) -> bool:
    """True when the two country strings share at least one country.

    GDACS lists are comma-separated; ReliefWeb appends parentheticals
    ("Venezuela (Bolivarian Republic of)"). Compared casefolded.
    """

    def names(value: str | None) -> set[str]:
        if not value:
            return set()
        return {
            _PARENTHETICAL.sub("", part).strip().casefold()
            for part in value.split(",")
            if part.strip()
        }

    return bool(names(a) & names(b))


def _sources(event: dict) -> list[str]:
    return event.get("sources") or [event["source"]]


def _candidate_pairs(events: list[dict]) -> list[tuple]:
    """All cross-feed pairs eligible to merge, best evidence first."""
    pairs = []
    for i, a in enumerate(events):
        for j in range(i + 1, len(events)):
            b = events[j]
            if a["source"] == b["source"] or a["hazard"] != b["hazard"]:
                continue
            evidence = _evidence(a, b)
            if a.get("glide") and a.get("glide") == b.get("glide"):
                tier = 1
            elif (
                evidence is not None
                and evidence[0] <= TIER2_WINDOW_SECONDS
                and evidence[1] <= TIER2_RADIUS_KM
            ):
                tier = 2
            else:
                continue
            dt, dd = evidence if evidence is not None else (float("inf"), float("inf"))
            pairs.append((tier, dt, dd, i, j))
    pairs.sort()
    return pairs


def _merged_event(members: list[dict], confidence: str, evidence: dict | None) -> dict:
    members = sorted(
        members, key=lambda e: (_SOURCE_ORDER.get(e["source"], 9), e["event_id"])
    )
    primary = members[0]
    gdacs = next((m for m in members if m["source"] == "gdacs"), None)
    usgs = next((m for m in members if m["source"] == "usgs"), None)

    event = dict(primary)
    ids: list[str] = []
    for member in members:
        ids += [alias for alias in member.get("ids", []) if alias not in ids]
    event["ids"] = ids

    if usgs is not None:
        # USGS is authoritative for earthquake physics; GDACS (the primary
        # when present) keeps title, country, alert levels, GLIDE.
        for field in ("lat", "lon", "depth_km", "pager", "sig"):
            event[field] = usgs.get(field)
        if usgs.get("magnitude") is not None:
            event["magnitude"] = usgs["magnitude"]
        event["urls"] = {**(usgs.get("urls") or {}), **(primary.get("urls") or {})}
    if gdacs is not None and gdacs is not primary:
        for field in ("alert_level", "episode_alert_level", "alert_score", "glide", "country"):
            event[field] = gdacs.get(field)

    occurred = [m["occurred_at"] for m in members if m.get("occurred_at")]
    updated = [m["updated_at"] for m in members if m.get("updated_at")]
    event["occurred_at"] = min(occurred) if occurred else primary.get("occurred_at")
    event["updated_at"] = max(updated) if updated else primary.get("updated_at")

    event["sources"] = [m["source"] for m in members]
    event["members"] = [m["event_id"] for m in members]
    event["source_titles"] = {m["source"]: m.get("title") for m in members}
    event["merge"] = {"confidence": confidence, "evidence": evidence}
    return event


def merge_records(events: list[dict]) -> list[dict]:
    """Merge normalised records into canonical events (tiers 1–2).

    Order-stable: output follows the input order of each group's first
    member. Singletons carry ``merge: single-source``.
    """
    parent = list(range(len(events)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    group_sources: dict[int, set[str]] = {i: {e["source"]} for i, e in enumerate(events)}
    group_pair: dict[int, tuple] = {}

    for tier, dt, dd, i, j in _candidate_pairs(events):
        ri, rj = find(i), find(j)
        if ri == rj or group_sources[ri] & group_sources[rj]:
            continue  # already together, or would double up one feed
        parent[rj] = ri
        group_sources[ri] |= group_sources.pop(rj)
        # The pair that caused the union is the merge's evidence.
        best = group_pair.get(ri)
        candidate = (tier, dt, dd, events[i], events[j])
        if best is None or candidate[:3] < best[:3]:
            group_pair[ri] = candidate

    groups: dict[int, list[dict]] = {}
    order: list[int] = []
    for index, event in enumerate(events):
        root = find(index)
        if root not in groups:
            groups[root] = []
            order.append(root)
        groups[root].append(event)

    merged = []
    for root in order:
        members = groups[root]
        if len(members) == 1:
            event = dict(members[0])
            event["sources"] = [event["source"]]
            event["members"] = [event["event_id"]]
            event["merge"] = {"confidence": "single-source", "evidence": None}
            merged.append(event)
            continue
        tier, dt, dd, a, b = group_pair[root]
        if tier == 1:
            confidence, evidence = "confirmed", {"glide": a.get("glide")}
            if dt != float("inf"):
                evidence.update({"dt_seconds": round(dt), "dd_km": round(dd, 1)})
        else:
            confidence = "high"
            evidence = {"dt_seconds": round(dt), "dd_km": round(dd, 1)}
        merged.append(_merged_event(members, confidence, evidence))
    return merged


def annotate_possible_related(events: list[dict]) -> None:
    """Tier 3, in place: same hazard + country within 24 h, **not** merged.

    Cross-references are symmetric and sorted; rendering shows them as two
    cards with a "possibly related" line (PRD §6: shown, not merged
    silently).
    """
    for event in events:
        event.setdefault("possible_related", [])
    for i, a in enumerate(events):
        for b in events[i + 1 :]:
            if a["hazard"] != b["hazard"]:
                continue
            if set(a.get("members", [])) & set(b.get("members", [])):
                continue
            if not countries_overlap(a.get("country"), b.get("country")):
                continue
            ta, tb = _timestamp(a), _timestamp(b)
            if ta is None or tb is None or abs(ta - tb) > TIER3_WINDOW_SECONDS:
                continue
            if b["event_id"] not in a["possible_related"]:
                a["possible_related"].append(b["event_id"])
            if a["event_id"] not in b["possible_related"]:
                b["possible_related"].append(a["event_id"])
    for event in events:
        event["possible_related"].sort()
