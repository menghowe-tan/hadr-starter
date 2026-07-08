"""Fetch raw feed payloads — live (single polite request) or replayed.

Replay mode reads ``<fixture-dir>/gdacs.json``, ``<fixture-dir>/usgs.json``
and ``<fixture-dir>/reliefweb.xml`` captured by
``tests/fixtures/capture_fixtures.py`` (the morning fixtures are derived by
``tests/fixtures/derive_mornings.py``). Live mode performs one request per
feed per invocation (no polling loop yet; the schedule is V3).

Every fetch returns ``(payload_or_None, fetched_at, status)``. A failed or
missing feed is reported as ``status == "down"`` with ``payload is None`` —
the pipeline continues degraded (PRD §7); deciding whether a morning without
both real-time feeds aborts is the sitrep runner's job, not this module's.
"""

from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

GDACS_URL = "https://www.gdacs.org/gdacsapi/api/events/geteventlist/EVENTS4APP"
# The 4.5_day window IS the "never below M 4.5" gate rule (PRD §5).
USGS_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_day.geojson"
# RSS needs no appname approval; the API lane is an adapter slot (PRD §9).
RELIEFWEB_RSS_URL = "https://reliefweb.int/disasters/rss.xml"

USER_AGENT = "hadr-starter monitor (github.com/menghowe-tan/hadr-starter)"

STATUS_OK = "ok"
STATUS_DOWN = "down"


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _fetch_live(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def _fetch_raw(feed_file: str, url: str, replay_dir: Path | None) -> tuple[bytes | None, str, str]:
    """Return ``(raw_bytes_or_None, fetched_at_utc_iso, status)`` for one feed."""
    try:
        if replay_dir is not None:
            raw = (Path(replay_dir) / feed_file).read_bytes()
        else:
            raw = _fetch_live(url)
    except (OSError, ValueError):
        return None, _now_utc_iso(), STATUS_DOWN
    return raw, _now_utc_iso(), STATUS_OK


def _fetch_json(feed_file: str, url: str, replay_dir: Path | None) -> tuple[dict | None, str, str]:
    raw, fetched_at, status = _fetch_raw(feed_file, url, replay_dir)
    if raw is None:
        return None, fetched_at, status
    try:
        return json.loads(raw), fetched_at, status
    except ValueError:
        return None, fetched_at, STATUS_DOWN


def fetch_gdacs(replay_dir: Path | None = None) -> tuple[dict | None, str, str]:
    return _fetch_json("gdacs.json", GDACS_URL, replay_dir)


def fetch_usgs(replay_dir: Path | None = None) -> tuple[dict | None, str, str]:
    return _fetch_json("usgs.json", USGS_URL, replay_dir)


def fetch_reliefweb_rss(replay_dir: Path | None = None) -> tuple[str | None, str, str]:
    """Raw RSS XML text; parsing lives in ``pipeline.reliefweb``."""
    raw, fetched_at, status = _fetch_raw("reliefweb.xml", RELIEFWEB_RSS_URL, replay_dir)
    if raw is None:
        return None, fetched_at, status
    return raw.decode("utf-8", errors="replace"), fetched_at, status
