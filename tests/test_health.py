"""PRD §7 truth table: quiet, degraded, down."""

from datetime import datetime, timedelta, timezone

import health

NOW = datetime(2025, 7, 30, 0, 30, tzinfo=timezone.utc)


def manifest(gdacs=1, usgs=1, reliefweb=20, down=()):
    """Feed ages in minutes; feeds named in `down` get status=down."""
    ages = {"gdacs": gdacs, "usgs": usgs, "reliefweb": reliefweb}
    return {
        "feeds": {
            name: {
                "last_success_utc": (NOW - timedelta(minutes=age)).isoformat(),
                "status": "down" if name in down else "ok",
            }
            for name, age in ages.items()
        }
    }


def test_all_fresh_is_ok():
    v = health.evaluate(manifest(), NOW)
    assert v["status"] == "ok" and not v["alert"] and not v["blind_hazards"]


def test_one_realtime_feed_down_is_degraded_and_names_hazards():
    v = health.evaluate(manifest(down=("gdacs",)), NOW)
    assert v["status"] == "degraded"
    assert "cyclone" in v["blind_hazards"][0] and "USGS" in v["blind_hazards"][0]
    assert v["alert"] is True  # ≥1h semantics: an explicit down raises the alert


def test_both_realtime_feeds_down_aborts():
    assert health.evaluate(manifest(down=("gdacs", "usgs")), NOW)["status"] == "abort"


def test_reliefweb_alone_never_blocks():
    v = health.evaluate(manifest(reliefweb=200, down=("reliefweb",)), NOW)
    assert v["status"] == "degraded"
    assert "Reported" in v["blind_hazards"][0]


def test_stale_at_three_times_cadence():
    # gdacs cadence 15 min -> stale past 45
    assert health.feed_state("gdacs", manifest(gdacs=44)["feeds"]["gdacs"], NOW) == "fresh"
    assert health.feed_state("gdacs", manifest(gdacs=46)["feeds"]["gdacs"], NOW) == "stale"
    # reliefweb cadence 60 min -> still fresh at 46
    assert health.feed_state("reliefweb", manifest(reliefweb=46)["feeds"]["reliefweb"], NOW) == "fresh"


def test_down_after_an_hour_of_silence():
    assert health.feed_state("usgs", manifest(usgs=61)["feeds"]["usgs"], NOW) == "down"
    v = health.evaluate(manifest(gdacs=61, usgs=61), NOW)
    assert v["status"] == "abort" and v["alert"]


def test_missing_last_success_counts_as_down():
    assert health.feed_state("gdacs", {"status": "ok", "last_success_utc": None}, NOW) == "down"
