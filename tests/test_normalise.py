"""Integration: the captured fixtures parse into the canonical schema."""

from conftest import load_fixture
from pipeline.normalise import normalise_gdacs, normalise_usgs


def test_gdacs_fixture_parses(eventful_dir):
    events = normalise_gdacs(load_fixture(eventful_dir, "gdacs"))
    assert len(events) == 79
    by_id = {e["event_id"]: e for e in events}

    mandalay = by_id["gdacs-EQ-1474477"]
    # Naive GDACS datetimes are declared UTC.
    assert mandalay["occurred_at"] == "2025-03-28T06:20:54+00:00"
    # String booleans become real booleans.
    assert mandalay["is_temporary"] is False
    # Empty GLIDE becomes None, not "".
    assert mandalay["glide"] is None
    assert mandalay["alert_level"] == "red"
    assert mandalay["episode_alert_level"] == "red"
    assert mandalay["magnitude"] == 7.7
    assert mandalay["hazard"] == "EQ"

    # Every timestamp in the batch is timezone-aware UTC.
    for event in events:
        assert event["occurred_at"].endswith("+00:00")
        if event["updated_at"] is not None:
            assert event["updated_at"].endswith("+00:00")


def test_usgs_fixture_parses(eventful_dir):
    events = normalise_usgs(load_fixture(eventful_dir, "usgs"))
    assert len(events) == 19
    by_id = {e["event_id"]: e for e in events}

    mandalay = by_id["usgs-us7000pn9s"]
    # Epoch-ms becomes aware UTC.
    assert mandalay["occurred_at"] == "2025-03-28T06:20:52.715000+00:00"
    # Identity is the union of `ids`, all four aliases stored.
    assert mandalay["ids"] == ["us7000pn9s", "usauto7000pn9s", "pt25087002", "at00sttln4"]
    # Depth captured from the third coordinate.
    assert mandalay["depth_km"] == 10
    assert mandalay["magnitude"] == 7.7
    assert mandalay["pager"] == "red"
    assert mandalay["sig"] == 2910

    for event in events:
        assert event["occurred_at"].endswith("+00:00")
        assert event["hazard"] == "EQ"
        assert event["ids"], "identity set must never be empty"
