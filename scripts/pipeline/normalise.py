"""Normalise raw feed payloads into canonical events.

Time rules (PRD §8, CLAUDE.md): everything becomes UTC here, at fetch time.
GDACS naive datetime strings are declared UTC; USGS timestamps are epoch
milliseconds. SGT appears only in rendered views.

Identity rules (PRD §6): USGS identity is the union of the ``ids`` list —
the preferred ``id`` can flip networks between fetches, so it is never used
alone. GDACS identity is ``eventtype`` + ``eventid``.

A canonical event is a plain JSON-serialisable dict; ``docs/SLICE-V1.md``
step 3. Cross-feed merge (GDACS↔USGS tiers) is slice V2 — here one feed
record is one canonical event.
"""

from __future__ import annotations

from datetime import datetime, timezone


def utc_from_gdacs(value: str) -> str:
    """GDACS naive ISO strings are UTC by declaration (CLAUDE.md)."""
    moment = datetime.fromisoformat(value)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).isoformat()


def utc_from_epoch_ms(value: int | float) -> str:
    """USGS ``time``/``updated`` are epoch milliseconds."""
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc).isoformat()


def _string_bool(value) -> bool:
    """GDACS booleans arrive as the strings "true"/"false"."""
    return str(value).lower() == "true"


def _lower_or_none(value) -> str | None:
    return value.lower() if value else None


def normalise_gdacs(payload: dict) -> list[dict]:
    events = []
    for feature in payload.get("features", []):
        properties = feature["properties"]
        longitude, latitude = feature["geometry"]["coordinates"][:2]
        severity = properties.get("severitydata") or {}
        hazard = properties["eventtype"]
        events.append(
            {
                "event_id": f"gdacs-{hazard}-{properties['eventid']}",
                "source": "gdacs",
                "hazard": hazard,
                "title": properties.get("name") or properties.get("description") or "",
                "country": properties.get("country") or None,
                "lat": latitude,
                "lon": longitude,
                "depth_km": None,
                "magnitude": severity.get("severity") if hazard == "EQ" else None,
                "severity_text": severity.get("severitytext") or None,
                "alert_level": _lower_or_none(properties.get("alertlevel")),
                "alert_score": properties.get("alertscore"),
                # Who computed the GDACS record: "NEIC" means the earthquake
                # lane is USGS-derived — agreement is an echo, not
                # corroboration (PRD §9), and the render says so.
                "feed_source": properties.get("source") or None,
                "episode_id": properties.get("episodeid"),
                "episode_alert_level": _lower_or_none(properties.get("episodealertlevel")),
                "pager": None,
                "sig": None,
                "glide": properties.get("glide") or None,
                "is_temporary": _string_bool(properties.get("istemporary")),
                "ids": [str(properties["eventid"])],
                "occurred_at": utc_from_gdacs(properties["fromdate"]),
                "updated_at": (
                    utc_from_gdacs(properties["datemodified"])
                    if properties.get("datemodified")
                    else None
                ),
                "urls": properties.get("url") or {},
            }
        )
    return events


def normalise_usgs(payload: dict) -> list[dict]:
    events = []
    for feature in payload.get("features", []):
        properties = feature["properties"]
        coordinates = feature["geometry"]["coordinates"]
        longitude, latitude = coordinates[0], coordinates[1]
        depth = coordinates[2] if len(coordinates) > 2 else None
        # Identity set: the union of `ids`, preferred id included (PRD §6).
        ids = [entry for entry in (properties.get("ids") or "").split(",") if entry]
        preferred = feature.get("id") or ids[0]
        if preferred not in ids:
            ids.insert(0, preferred)
        pager = _lower_or_none(properties.get("alert"))
        events.append(
            {
                "event_id": f"usgs-{preferred}",
                "source": "usgs",
                "hazard": "EQ",
                "title": properties.get("title") or properties.get("place") or "",
                "country": None,
                "lat": latitude,
                "lon": longitude,
                "depth_km": depth,
                "magnitude": properties.get("mag"),
                "severity_text": None,
                "alert_level": pager,
                "alert_score": None,
                "episode_id": None,
                "episode_alert_level": None,
                "pager": pager,
                "sig": properties.get("sig"),
                "glide": None,
                "is_temporary": False,
                "ids": ids,
                "occurred_at": utc_from_epoch_ms(properties["time"]),
                "updated_at": (
                    utc_from_epoch_ms(properties["updated"])
                    if properties.get("updated") is not None
                    else None
                ),
                "urls": {"report": properties.get("url"), "details": properties.get("detail")},
            }
        )
    return events
