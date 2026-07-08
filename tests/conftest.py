import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"


@pytest.fixture
def eventful_dir() -> Path:
    return FIXTURES / "eventful"


@pytest.fixture
def quiet_dir() -> Path:
    return FIXTURES / "quiet"


def load_fixture(fixture_dir: Path, feed: str) -> dict:
    return json.loads((fixture_dir / f"{feed}.json").read_text())


def make_usgs_event(
    magnitude=5.0,
    depth_km=10.0,
    sig=300,
    pager=None,
    event_id="usgs-test1",
    ids=("test1",),
    title="M test",
    updated_at="2025-03-28T07:00:00+00:00",
) -> dict:
    return {
        "event_id": event_id,
        "source": "usgs",
        "hazard": "EQ",
        "title": title,
        "country": None,
        "lat": 0.0,
        "lon": 0.0,
        "depth_km": depth_km,
        "magnitude": magnitude,
        "severity_text": None,
        "alert_level": pager,
        "alert_score": None,
        "episode_id": None,
        "episode_alert_level": None,
        "pager": pager,
        "sig": sig,
        "glide": None,
        "is_temporary": False,
        "ids": list(ids),
        "occurred_at": "2025-03-28T06:20:52+00:00",
        "updated_at": updated_at,
        "urls": {},
    }


def make_gdacs_event(
    alert_level="green",
    episode_alert_level="green",
    is_temporary=False,
    event_id="gdacs-EQ-1",
    hazard="EQ",
    title="Earthquake in Testland",
) -> dict:
    return {
        "event_id": event_id,
        "source": "gdacs",
        "hazard": hazard,
        "title": title,
        "country": "Testland",
        "lat": 0.0,
        "lon": 0.0,
        "depth_km": None,
        "magnitude": 5.0 if hazard == "EQ" else None,
        "severity_text": None,
        "alert_level": alert_level,
        "alert_score": 1,
        "episode_id": 100,
        "episode_alert_level": episode_alert_level,
        "pager": None,
        "sig": None,
        "glide": None,
        "is_temporary": is_temporary,
        "ids": [event_id.rsplit("-", 1)[-1]],
        "occurred_at": "2025-03-28T06:20:54+00:00",
        "updated_at": "2025-03-28T12:00:00+00:00",
        "urls": {},
    }
