"""Fetch raw feed payloads — live (single polite request) or replayed.

Replay mode reads ``<fixture-dir>/gdacs.json`` and ``<fixture-dir>/usgs.json``
captured by ``tests/fixtures/capture_fixtures.py``. Live mode performs one
request per feed per invocation (no polling loop in V1; the schedule is V3).
"""

from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

GDACS_URL = "https://www.gdacs.org/gdacsapi/api/events/geteventlist/EVENTS4APP"
# The 4.5_day window IS the "never below M 4.5" gate rule (PRD §5).
USGS_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_day.geojson"

USER_AGENT = "hadr-starter monitor (github.com/menghowe-tan/hadr-starter)"


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _fetch_live(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def _fetch(feed_file: str, url: str, replay_dir: Path | None) -> tuple[dict, str]:
    """Return ``(payload, fetched_at_utc_iso)`` for one feed."""
    if replay_dir is not None:
        payload = json.loads((Path(replay_dir) / feed_file).read_text())
    else:
        payload = _fetch_live(url)
    return payload, _now_utc_iso()


def fetch_gdacs(replay_dir: Path | None = None) -> tuple[dict, str]:
    return _fetch("gdacs.json", GDACS_URL, replay_dir)


def fetch_usgs(replay_dir: Path | None = None) -> tuple[dict, str]:
    return _fetch("usgs.json", USGS_URL, replay_dir)
