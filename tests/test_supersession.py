"""Unit: the supersession classifier — every ▲△▽✕ kind (PRD §4 #5, §7)."""

from conftest import make_gdacs_event, make_usgs_event
from pipeline.diff import classify, diff_and_update

NOW = "2026-07-08T00:00:00+00:00"
LATER = "2026-07-08T00:05:00+00:00"


def _orange(**overrides):
    event = make_gdacs_event(alert_level="orange", episode_alert_level="orange")
    event.update(overrides)
    return event


def test_escalated_when_the_alert_level_rises():
    kind, detail = classify(_orange(), _orange(alert_level="red", episode_alert_level="red"))
    assert (kind, detail) == ("escalated", "orange → red")


def test_episode_escalation_counts_too():
    """The gate watches episodealertlevel (PRD §9 GDACS 1); so does the diff."""
    kind, detail = classify(_orange(), _orange(episode_alert_level="red"))
    assert (kind, detail) == ("escalated", "orange → red")


def test_downgraded_when_the_alert_level_falls():
    kind, detail = classify(_orange(alert_level="red", episode_alert_level="red"), _orange())
    assert (kind, detail) == ("downgraded", "red → orange")


def test_revised_on_magnitude_pager_or_location():
    old = make_usgs_event(magnitude=7.6, pager=None)
    new = make_usgs_event(magnitude=7.7, pager="red")
    kind, detail = classify(old, new)
    assert kind == "revised"
    assert "magnitude 7.6 → 7.7" in detail
    assert "PAGER pending → red" in detail

    moved = make_usgs_event()
    moved.update(lat=1.0)  # ~111 km
    kind, detail = classify(make_usgs_event(), moved)
    assert kind == "revised"
    assert "epicentre moved" in detail


def test_updated_on_new_episode_of_a_continuing_event():
    kind, detail = classify(_orange(), _orange(episode_id=101))
    assert kind == "updated"
    assert "new episode" in detail


def test_updated_when_a_ground_report_is_linked():
    linked = _orange()
    linked["umbrellas"] = [{"umbrella_id": "x", "confidence": "confirmed"}]
    kind, detail = classify(_orange(), linked)
    assert (kind, detail) == ("updated", "ReliefWeb situation report linked")


def test_below_gate_downgrade_is_reported_once_then_dropped():
    """An event that falls below the gate is still in the feed — that is a
    downgrade (▽), not an aged-out; reported once, then dropped."""
    _, _, store = diff_and_update({}, [_orange()], NOW)
    green = _orange(alert_level="green", episode_alert_level="green")
    verdict, changes, store = diff_and_update(
        store, [], LATER, all_events=[green]
    )
    assert verdict == "CHANGED"
    assert changes == [
        {"event_id": "gdacs-EQ-1", "change": "downgraded", "detail": "orange → green"}
    ]
    assert store["gdacs-EQ-1"]["status"] == "below-gate"
    # Next run: no longer news.
    verdict, changes, _ = diff_and_update(
        store, [], "2026-07-08T00:10:00+00:00", all_events=[green]
    )
    assert (verdict, changes) == ("QUIET", [])


def test_withdrawn_only_with_detail_endpoint_confirmation():
    """Vanished ≠ deleted (PRD §7): without confirmation it is aged-out."""
    _, _, store = diff_and_update({}, [make_usgs_event(pager="red")], NOW)
    verdict, changes, updated = diff_and_update(
        store, [], LATER, all_events=[], confirm_withdrawal=lambda record: False
    )
    assert changes == [{"event_id": "usgs-test1", "change": "aged-out"}]
    assert updated["usgs-test1"]["status"] == "aged-out"

    verdict, changes, updated = diff_and_update(
        store, [], LATER, all_events=[], confirm_withdrawal=lambda record: True
    )
    assert changes[0]["change"] == "withdrawn"
    assert updated["usgs-test1"]["status"] == "withdrawn"
    assert updated["usgs-test1"]["withdrawn_at"] == LATER


def test_a_down_feed_never_ages_its_events_out():
    """Blindness is not absence (PRD §7): when a feed was not fetched, its
    stored events stay active rather than vanishing."""
    _, _, store = diff_and_update({}, [make_usgs_event(pager="red")], NOW)
    verdict, changes, updated = diff_and_update(
        store, [], LATER, all_events=[], fetched_sources={"gdacs"}
    )
    assert (verdict, changes) == ("QUIET", [])
    assert updated["usgs-test1"]["status"] == "active"
