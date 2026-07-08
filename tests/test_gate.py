"""The severity gate (PRD §5): fixture behaviour + threshold edges."""

from conftest import load_fixture, make_gdacs_event, make_usgs_event
from pipeline.gate import apply_gate, gate_reason
from pipeline.normalise import normalise_gdacs, normalise_usgs


def _gated_ids(fixture_dir):
    events = normalise_gdacs(load_fixture(fixture_dir, "gdacs")) + normalise_usgs(
        load_fixture(fixture_dir, "usgs")
    )
    return {e["event_id"] for e in apply_gate(events)}


def test_eventful_fixture_admits_exactly_the_severe_events(eventful_dir):
    assert _gated_ids(eventful_dir) == {
        "gdacs-EQ-1474477",  # Red — Mandalay M 7.7
        "gdacs-EQ-1474479",  # Red — the M 6.7 aftershock
        "gdacs-FL-1103210",  # Orange — DRC floods
        "usgs-us7000pn9s",  # PAGER red
        "usgs-us7000pn9z",  # PAGER red
        "usgs-us7000pn8m",  # M 5.7 at 37 km
        "usgs-us7000pn7g",  # M 6.1 at 10 km
    }


def test_quiet_fixture_admits_nothing(quiet_dir):
    assert _gated_ids(quiet_dir) == set()


def test_gate_rejects_greens_and_temporaries():
    assert gate_reason(make_gdacs_event(alert_level="green")) is None
    assert gate_reason(make_gdacs_event(alert_level="orange", is_temporary=True)) is None
    assert gate_reason(make_gdacs_event(alert_level="red", is_temporary=True)) is None


def test_gate_admits_orange_at_event_or_episode_level():
    assert gate_reason(make_gdacs_event(alert_level="orange")) == "GDACS alert orange"
    # Event still green, but the episode escalated — in (PRD §5, §9 GDACS 1).
    assert (
        gate_reason(make_gdacs_event(alert_level="green", episode_alert_level="orange"))
        == "GDACS episode alert orange"
    )


def test_usgs_magnitude_depth_edges():
    assert gate_reason(make_usgs_event(magnitude=5.5, depth_km=69)) is not None
    assert gate_reason(make_usgs_event(magnitude=5.5, depth_km=71)) is None
    assert gate_reason(make_usgs_event(magnitude=5.4, depth_km=10)) is None
    assert gate_reason(make_usgs_event(magnitude=5.5, depth_km=None)) is None


def test_usgs_sig_edges():
    assert gate_reason(make_usgs_event(sig=599)) is None
    assert gate_reason(make_usgs_event(sig=600)) is not None


def test_usgs_pager_yellow_admits():
    assert gate_reason(make_usgs_event(pager="yellow")) == "PAGER yellow"
    assert gate_reason(make_usgs_event(pager="green")) is None


def test_apply_gate_annotates_reason():
    gated = apply_gate([make_usgs_event(pager="red"), make_usgs_event(sig=100)])
    assert len(gated) == 1
    assert gated[0]["gate_reason"] == "PAGER red"
