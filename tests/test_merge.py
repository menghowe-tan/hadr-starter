"""Integration: the tiered cross-feed merge (PRD §6)."""

from conftest import make_gdacs_event, make_usgs_event
from pipeline.merge import annotate_possible_related, countries_overlap, merge_records

# Real coordinates/times from the Mandalay morning fixture.
MAINSHOCK_GDACS = dict(lat=22.0128, lon=95.9216, occurred_at="2025-03-28T06:20:54+00:00")
MAINSHOCK_USGS = dict(lat=22.011, lon=95.9363, occurred_at="2025-03-28T06:20:52+00:00")
AFTERSHOCK_GDACS = dict(lat=21.7073, lon=95.9692, occurred_at="2025-03-28T06:32:04+00:00")


def gdacs(event_id="gdacs-EQ-1", **overrides):
    event = make_gdacs_event(event_id=event_id, alert_level="red", episode_alert_level="red")
    event["ids"] = [event_id.rsplit("-", 1)[-1]]
    event.update(overrides)
    return event


def usgs(event_id="usgs-usX", **overrides):
    event = make_usgs_event(event_id=event_id, ids=(event_id.removeprefix("usgs-"),))
    event.update(overrides)
    return event


def test_tier2_spatiotemporal_merge_with_evidence():
    merged = merge_records(
        [gdacs(**MAINSHOCK_GDACS), usgs(pager="red", magnitude=7.7, **MAINSHOCK_USGS)]
    )
    assert len(merged) == 1
    event = merged[0]
    assert event["merge"]["confidence"] == "high"
    # The evidence is kept so the report can show its working (design §5).
    assert event["merge"]["evidence"]["dt_seconds"] == 2
    assert 1.0 < event["merge"]["evidence"]["dd_km"] < 3.0
    # Canonical identity: GDACS is primary; the ids union spans both feeds.
    assert event["event_id"] == "gdacs-EQ-1"
    assert event["ids"] == ["1", "usX"]
    assert event["sources"] == ["gdacs", "usgs"]
    # Field provenance: GDACS keeps alerts/country; USGS keeps physics.
    assert event["alert_level"] == "red"
    assert event["country"] == "Testland"
    assert event["magnitude"] == 7.7
    assert event["pager"] == "red"
    assert (event["lat"], event["lon"]) == (MAINSHOCK_USGS["lat"], MAINSHOCK_USGS["lon"])


def test_tier1_glide_merge_is_confirmed():
    a = gdacs(glide="EQ-2025-000043-MMR", **MAINSHOCK_GDACS)
    # Far outside tier-2 thresholds: GLIDE alone must carry the merge.
    b = usgs(glide="EQ-2025-000043-MMR", lat=10.0, lon=90.0, occurred_at="2025-03-29T09:00:00+00:00")
    merged = merge_records([a, b])
    assert len(merged) == 1
    assert merged[0]["merge"]["confidence"] == "confirmed"
    assert merged[0]["merge"]["evidence"]["glide"] == "EQ-2025-000043-MMR"


def test_same_feed_records_never_merge():
    """Mainshock and aftershock are 11 min and ~35 km apart — inside tier-2
    thresholds — but a feed's own event ids are distinct physical events."""
    merged = merge_records(
        [gdacs("gdacs-EQ-1", **MAINSHOCK_GDACS), gdacs("gdacs-EQ-2", **AFTERSHOCK_GDACS)]
    )
    assert len(merged) == 2
    assert all(event["merge"]["confidence"] == "single-source" for event in merged)


def test_ambiguity_resolves_to_closest_origin_time():
    """The USGS mainshock is within tier-2 range of *both* GDACS Myanmar
    quakes; it must claim the mainshock (Δt 2 s), not the aftershock."""
    merged = merge_records(
        [
            gdacs("gdacs-EQ-1", **MAINSHOCK_GDACS),
            gdacs("gdacs-EQ-2", **AFTERSHOCK_GDACS),
            usgs("usgs-usX", magnitude=7.7, **MAINSHOCK_USGS),
        ]
    )
    by_id = {event["event_id"]: event for event in merged}
    assert by_id["gdacs-EQ-1"]["sources"] == ["gdacs", "usgs"]
    assert by_id["gdacs-EQ-2"]["sources"] == ["gdacs"]


def test_tier3_is_cross_reference_never_a_merge():
    a = gdacs("gdacs-EQ-1", country="Myanmar", **MAINSHOCK_GDACS)
    b = gdacs("gdacs-EQ-2", country="Myanmar", **AFTERSHOCK_GDACS)
    merged = merge_records([a, b])
    annotate_possible_related(merged)
    assert len(merged) == 2  # shown, not merged silently (PRD §6)
    assert merged[0]["possible_related"] == ["gdacs-EQ-2"]
    assert merged[1]["possible_related"] == ["gdacs-EQ-1"]


def test_tier3_requires_hazard_and_country():
    flood = gdacs("gdacs-FL-3", hazard="FL", country="Myanmar", **MAINSHOCK_GDACS)
    elsewhere = gdacs("gdacs-EQ-4", country="Peru", **AFTERSHOCK_GDACS)
    quake = gdacs("gdacs-EQ-1", country="Myanmar", **MAINSHOCK_GDACS)
    merged = merge_records([quake, flood, elsewhere])
    annotate_possible_related(merged)
    assert all(event["possible_related"] == [] for event in merged)


def test_countries_overlap_handles_lists_and_parentheticals():
    assert countries_overlap("Thailand, Myanmar", "Myanmar")
    assert countries_overlap("Venezuela", "Venezuela (Bolivarian Republic of)")
    assert not countries_overlap("Democratic Republic of Congo", "Congo")
    assert not countries_overlap(None, "Myanmar")
