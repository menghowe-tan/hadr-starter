"""The deterministic dashboard: markers, freshness, degraded banner, fallback."""

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import render_dashboard
from pipeline import runner

FIXTURES = Path(__file__).parent / "fixtures"

RED_EVENT = "gdacs-EQ-1474477"  # Mandalay M 7.7, GDACS Red
ORANGE_EVENT = "gdacs-FL-1103210"  # DRC flood, GDACS Orange


def build(tmp_path, replay_dir=FIXTURES / "eventful"):
    # run_cycle stamps fetched_at at the real current time (no --now hook),
    # so freshness must be evaluated against real "now" too.
    runner.run_cycle(replay_dir, tmp_path)
    manifest, events = render_dashboard.load_store(tmp_path)
    return render_dashboard.render(manifest, events, datetime.now(timezone.utc)), events


def gdacs_down_dir(tmp_path):
    """A replay dir missing gdacs.json — fetch.py reports it down."""
    down_dir = tmp_path / "gdacs-down-fixture"
    down_dir.mkdir()
    shutil.copy(FIXTURES / "eventful" / "usgs.json", down_dir / "usgs.json")
    shutil.copy(FIXTURES / "eventful" / "reliefweb.xml", down_dir / "reliefweb.xml")
    return down_dir


def payload(page):
    blob = page.split('<script id="store" type="application/json">')[1].split("</script>")[0]
    return json.loads(blob)


def test_map_data_derives_from_the_same_store(tmp_path):
    page, events = build(tmp_path)
    markers = payload(page)["markers"]
    assert {m["id"] for m in markers} == {e["event_id"] for e in events}


def test_marker_colours_follow_alert_levels(tmp_path):
    page, _ = build(tmp_path)
    markers = {m["id"]: m for m in payload(page)["markers"]}
    assert markers[RED_EVENT]["level"] == "Red"
    assert render_dashboard.ALERT_COLOURS["Red"] == "#C0392B"
    assert markers[ORANGE_EVENT]["level"] == "Orange"


def test_popup_anchors_use_the_canonical_event_id(tmp_path):
    page, _ = build(tmp_path)
    markers = {m["id"]: m for m in payload(page)["markers"]}
    assert markers[RED_EVENT]["anchor"] == RED_EVENT
    assert "sitrep/index.html#" in page


def test_events_without_a_track_draw_no_polyline(tmp_path):
    # V1/V2's canonical event has no forecast-track field yet; the dashboard
    # must degrade to no polyline rather than crash.
    page, _ = build(tmp_path)
    markers = {m["id"]: m for m in payload(page)["markers"]}
    assert markers[RED_EVENT]["track"] == []


def test_freshness_stamps_and_tile_fallback_present(tmp_path):
    page, _ = build(tmp_path)
    feeds = payload(page)["feeds"]
    assert feeds["gdacs"]["state"] == "fresh"
    assert "tile-notice" in page and "tileerror" in page


def test_degraded_run_shows_banner_and_red_chip(tmp_path):
    page, _ = build(tmp_path, replay_dir=gdacs_down_dir(tmp_path))
    assert "Degraded coverage" in page
    assert "cyclone, flood, volcano" in page
    assert payload(page)["feeds"]["gdacs"]["state"] == "down"


def test_unreadable_store_aborts_with_exit_3(tmp_path, capsys):
    assert render_dashboard.main(["--data", str(tmp_path / "nowhere")]) == 3
