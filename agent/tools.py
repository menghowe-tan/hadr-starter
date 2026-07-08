"""HADR tools plugged into the reusable harness.

Level 3 adds fetch_feed. Everything here is project-specific; the harness
knows nothing about disaster feeds.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import httpx

from harness import Tool

FEED_URLS = {
    "gdacs": "https://www.gdacs.org/gdacsapi/api/events/geteventlist/EVENTS4APP",
    "usgs": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_day.geojson",
}


def _gdacs_utc(naive: str | None) -> str | None:
    # GDACS naive datetimes are UTC (PRD §8); declare it.
    return f"{naive}Z" if naive and not naive.endswith("Z") else naive


def _epoch_ms_utc(ms: int | None) -> str | None:
    if ms is None:
        return None
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()


def _trim_gdacs(feature: dict) -> dict:
    p = feature.get("properties", {})
    lon, lat = (feature.get("geometry", {}).get("coordinates") or [None, None])[:2]
    return {
        "hazard": p.get("eventtype"),
        "event_id": p.get("eventid"),
        "episode_id": p.get("episodeid"),
        "glide": p.get("glide") or None,
        "name": p.get("name"),
        "alert_level": p.get("alertlevel"),
        "episode_alert_level": p.get("episodealertlevel"),
        "is_temporary": p.get("istemporary") == "true",
        "country": p.get("country"),
        "iso3": p.get("iso3"),
        "source": p.get("source"),
        "from_utc": _gdacs_utc(p.get("fromdate")),
        "to_utc": _gdacs_utc(p.get("todate")),
        "modified_utc": _gdacs_utc(p.get("datemodified")),
        "lat": lat,
        "lon": lon,
    }


def _trim_usgs(feature: dict) -> dict:
    p = feature.get("properties", {})
    coords = feature.get("geometry", {}).get("coordinates") or [None, None, None]
    return {
        "hazard": "EQ",
        "id": feature.get("id"),
        # Identity is the union of ids — the network prefix can flip (PRD §6).
        "ids": [i for i in (p.get("ids") or "").split(",") if i],
        "title": p.get("title"),
        "magnitude": p.get("mag"),
        "place": p.get("place"),
        "time_utc": _epoch_ms_utc(p.get("time")),
        "updated_utc": _epoch_ms_utc(p.get("updated")),
        "pager_alert": p.get("alert"),
        "sig": p.get("sig"),
        "tsunami_message_exists": bool(p.get("tsunami")),
        "status": p.get("status"),
        "lat": coords[1],
        "lon": coords[0],
        "depth_km": coords[2],
    }


def fetch_feed(feed: str) -> str:
    """Fetch one live feed, normalised to UTC and trimmed to what matters."""
    url = FEED_URLS.get(feed)
    if url is None:
        raise ValueError(f"unknown feed {feed!r}; expected one of {sorted(FEED_URLS)}")
    # Feeds redirect to their canonical host — follow, and log the final URL
    # (docs/solutions/2026-07-06-example-follow-redirects.md).
    response = httpx.get(url, timeout=30.0, follow_redirects=True)
    response.raise_for_status()
    features = response.json().get("features", [])
    trim = _trim_gdacs if feed == "gdacs" else _trim_usgs
    return json.dumps(
        {
            "feed": feed,
            "fetched_utc": datetime.now(timezone.utc).isoformat(),
            "final_url": str(response.url),
            "event_count": len(features),
            "events": [trim(f) for f in features],
        }
    )


FETCH_FEED = Tool(
    name="fetch_feed",
    description=(
        "Fetch the current events from one live disaster feed. Call this for "
        "BOTH 'gdacs' (EU/UN multi-hazard alerts: earthquakes, cyclones, "
        "floods, volcanoes, drought, wildfires, with Green/Orange/Red alert "
        "levels) and 'usgs' (raw real-time earthquakes, past day, M4.5+) "
        "before assessing the situation. Timestamps are UTC."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "feed": {
                "type": "string",
                "enum": ["gdacs", "usgs"],
                "description": "Which feed to fetch.",
            }
        },
        "required": ["feed"],
    },
    fn=fetch_feed,
)

TOOLS = [FETCH_FEED]
