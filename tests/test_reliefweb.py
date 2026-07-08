"""Integration: the ReliefWeb RSS lane and event↔umbrella links (PRD §6, §9)."""

from pathlib import Path

import pytest
from conftest import make_gdacs_event
from pipeline.reliefweb import ReliefWebAPI, ReliefWebRSS, link_umbrellas, parse_rss

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_rss_fixture_parses_glide_and_country_from_escaped_html():
    umbrellas = parse_rss((FIXTURES / "morning-2" / "reliefweb.xml").read_text())
    assert len(umbrellas) == 3
    myanmar = umbrellas[0]
    assert myanmar["title"] == "Myanmar: Earthquakes - Mar 2025"
    assert myanmar["glide"] == "EQ-2025-000043-MMR"
    assert myanmar["country"] == "Myanmar"
    assert myanmar["hazard"] == "EQ"  # from the GLIDE prefix
    assert myanmar["umbrella_id"] == "eq-2025-000043-mmr"  # link slug
    assert myanmar["published_at"] == "2025-03-28T00:00:00+00:00"
    assert "7.7 magnitude earthquake" in myanmar["summary"]
    assert "<" not in myanmar["summary"]  # tags stripped


def test_rss_adapter_replays_the_fixture_and_reports_health():
    umbrellas, fetched_at, status = ReliefWebRSS().fetch(FIXTURES / "quiet")
    assert status == "ok"
    assert len(umbrellas) == 2
    # A fixture without reliefweb.xml is a down feed, not a crash.
    umbrellas, _, status = ReliefWebRSS().fetch(FIXTURES / "does-not-exist")
    assert (umbrellas, status) == ([], "down")


def test_api_lane_is_a_slot_awaiting_the_appname():
    with pytest.raises(NotImplementedError):
        ReliefWebAPI(appname="pending").fetch()


def _umbrella(**overrides):
    umbrella = {
        "umbrella_id": "eq-2025-000043-mmr",
        "title": "Myanmar: Earthquakes - Mar 2025",
        "url": "https://reliefweb.int/disaster/eq-2025-000043-mmr",
        "glide": "EQ-2025-000043-MMR",
        "hazard": "EQ",
        "country": "Myanmar",
        "published_at": "2025-03-28T00:00:00+00:00",
        "summary": None,
    }
    umbrella.update(overrides)
    return umbrella


def test_umbrella_links_one_to_many_without_collapsing_events():
    """One country-level umbrella may cover several physical events; the
    events stay separate and each carries its own link confidence."""
    mainshock = make_gdacs_event(event_id="gdacs-EQ-1", title="Mainshock")
    mainshock.update(country="Myanmar", occurred_at="2025-03-28T06:20:54+00:00", glide=None)
    aftershock = make_gdacs_event(event_id="gdacs-EQ-2", title="Aftershock")
    aftershock.update(
        country="Myanmar",
        occurred_at="2025-03-28T06:32:04+00:00",
        glide="EQ-2025-000043-MMR",
    )
    link_umbrellas([mainshock, aftershock], [_umbrella()])

    # GLIDE equality is tier 1: confirmed. Hazard+country in-window: possible.
    assert [u["confidence"] for u in mainshock["umbrellas"]] == ["possible"]
    assert [u["confidence"] for u in aftershock["umbrellas"]] == ["confirmed"]
    assert mainshock["event_id"] != aftershock["event_id"]  # still two events


def test_umbrella_outside_window_or_hazard_does_not_link():
    event = make_gdacs_event(event_id="gdacs-EQ-1")
    event.update(country="Myanmar", occurred_at="2025-03-30T06:20:54+00:00", glide=None)
    link_umbrellas([event], [_umbrella()])  # two days after publication
    assert event["umbrellas"] == []

    flood = make_gdacs_event(event_id="gdacs-FL-9", hazard="FL")
    flood.update(country="Myanmar", occurred_at="2025-03-28T06:20:54+00:00", glide=None)
    link_umbrellas([flood], [_umbrella()])  # right window, wrong hazard
    assert flood["umbrellas"] == []
