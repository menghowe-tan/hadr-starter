"""Unit: the deterministic ranking comparator (design §4).

Escalations first (newest on top), then alert level Red → Orange → the
rest, then modeled exposure — stable across runs.
"""

from conftest import make_gdacs_event, make_usgs_event
from pipeline.rank import sitrep_order


def _record(event_id, **overrides):
    record = make_gdacs_event(event_id=event_id)
    record.update(status="active", **overrides)
    return record


def test_escalations_lead_newest_first():
    old_escalation = _record(
        "gdacs-EQ-old", alert_level="red", updated_at="2025-03-28T01:00:00+00:00"
    )
    new_escalation = _record(
        "gdacs-EQ-new", alert_level="orange", updated_at="2025-03-28T09:00:00+00:00"
    )
    plain_red = _record("gdacs-EQ-red", alert_level="red", alert_score=3)
    changes = {
        "gdacs-EQ-old": {"event_id": "gdacs-EQ-old", "change": "escalated"},
        "gdacs-EQ-new": {"event_id": "gdacs-EQ-new", "change": "escalated"},
    }
    ordered = sitrep_order([plain_red, old_escalation, new_escalation], changes)
    # Both escalations outrank the plain Red — even the Orange one.
    assert [r["event_id"] for r in ordered] == ["gdacs-EQ-new", "gdacs-EQ-old", "gdacs-EQ-red"]


def test_level_then_exposure_then_stable_tiebreak():
    orange = _record("gdacs-FL-orange", hazard="FL", alert_level="orange")
    red = _record("gdacs-EQ-red", alert_level="red")
    pager_red = make_usgs_event(event_id="usgs-red", pager="red")
    big_orange = _record("gdacs-DR-big", hazard="DR", alert_level="orange", alert_score=2.5)
    ordered = sitrep_order([orange, big_orange, pager_red, red], {})
    ids = [r["event_id"] for r in ordered]
    # PAGER red ranks with Reds; higher modeled exposure wins within a level.
    assert ids.index("gdacs-EQ-red") < ids.index("gdacs-FL-orange")
    assert ids.index("usgs-red") < ids.index("gdacs-FL-orange")
    assert ids.index("gdacs-DR-big") < ids.index("gdacs-FL-orange")
    # Deterministic: same input, same order, every run.
    assert ids == [r["event_id"] for r in sitrep_order([red, pager_red, orange, big_orange], {})]
