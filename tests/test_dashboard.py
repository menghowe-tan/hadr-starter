"""The deterministic dashboard: markers, freshness, degraded banner, fallback."""

import json
from datetime import datetime, timezone
from pathlib import Path

import render_dashboard
import stub_pipeline

FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime(2025, 7, 30, 0, 30, tzinfo=timezone.utc)


def build(tmp_path, scenario="eventful"):
    stub_pipeline.run(scenario, tmp_path, FIXTURES, NOW)
    manifest, events = render_dashboard.load_store(tmp_path)
    return render_dashboard.render(manifest, events, NOW), events


def payload(page):
    blob = page.split('<script id="store" type="application/json">')[1].split("</script>")[0]
    return json.loads(blob)


def test_map_data_derives_from_the_same_store(tmp_path):
    page, events = build(tmp_path)
    markers = payload(page)["markers"]
    assert {m["id"] for m in markers} == {e["id"] for e in events}


def test_marker_colours_follow_alert_levels(tmp_path):
    page, _ = build(tmp_path)
    markers = {m["id"]: m for m in payload(page)["markers"]}
    assert markers["EQ-2025-07-29-001"]["level"] == "Red"
    assert render_dashboard.ALERT_COLOURS["Red"] == "#C0392B"
    assert markers["TC-2025-07-27-001"]["level"] == "Orange"


def test_popup_anchors_use_feed_ids(tmp_path):
    page, _ = build(tmp_path)
    markers = {m["id"]: m for m in payload(page)["markers"]}
    assert markers["EQ-2025-07-29-001"]["anchor"] == "us6000qw60"
    assert markers["TC-2025-07-27-001"]["anchor"] == "1001129"
    assert "sitrep/index.html#" in page


def test_cyclone_draws_a_dashed_track(tmp_path):
    page, _ = build(tmp_path)
    markers = {m["id"]: m for m in payload(page)["markers"]}
    assert len(markers["TC-2025-07-27-001"]["track"]) == 5
    assert "dashArray" in page


def test_freshness_stamps_and_tile_fallback_present(tmp_path):
    page, _ = build(tmp_path)
    feeds = payload(page)["feeds"]
    assert feeds["gdacs"]["state"] == "fresh"
    assert "tile-notice" in page and "tileerror" in page


def test_degraded_run_shows_banner_and_red_chip(tmp_path):
    page, _ = build(tmp_path, scenario="gdacs-down")
    assert "Degraded coverage" in page
    assert "cyclone, flood, volcano" in page
    assert payload(page)["feeds"]["gdacs"]["state"] == "down"


def test_unreadable_store_aborts_with_exit_3(tmp_path, capsys):
    assert render_dashboard.main(["--data", str(tmp_path / "nowhere")]) == 3
