"""Unit: diff verdicts and the ids-union identity rule (PRD §6, §8)."""

from conftest import make_usgs_event
from pipeline.diff import diff_and_update

NOW = "2026-07-08T00:00:00+00:00"
LATER = "2026-07-08T00:05:00+00:00"


def _event(**overrides):
    return make_usgs_event(pager="red", **overrides)


def test_new_event_is_changed():
    verdict, changes, store = diff_and_update({}, [_event()], NOW)
    assert verdict == "CHANGED"
    assert changes == [{"event_id": "usgs-test1", "change": "new"}]
    assert store["usgs-test1"]["status"] == "active"
    assert store["usgs-test1"]["first_seen"] == NOW


def test_unchanged_event_is_quiet():
    _, _, store = diff_and_update({}, [_event()], NOW)
    verdict, changes, store = diff_and_update(store, [_event()], LATER)
    assert verdict == "QUIET"
    assert changes == []
    assert store["usgs-test1"]["last_seen"] == LATER
    assert store["usgs-test1"]["first_seen"] == NOW


def test_revised_event_is_changed():
    _, _, store = diff_and_update({}, [_event()], NOW)
    revised = _event(magnitude=6.0, updated_at="2025-03-28T09:00:00+00:00")
    verdict, changes, _ = diff_and_update(store, [revised], LATER)
    assert verdict == "CHANGED"
    assert changes == [{"event_id": "usgs-test1", "change": "updated"}]


def test_vanished_event_ages_out_once_never_withdrawn():
    _, _, store = diff_and_update({}, [_event()], NOW)
    verdict, changes, store = diff_and_update(store, [], LATER)
    assert verdict == "CHANGED"
    assert changes == [{"event_id": "usgs-test1", "change": "aged-out"}]
    # Aged-out, not deleted: the record survives (PRD §7).
    assert store["usgs-test1"]["status"] == "aged-out"
    # Still absent next run: no longer news.
    verdict, changes, _ = diff_and_update(store, [], "2026-07-08T00:10:00+00:00")
    assert verdict == "QUIET"
    assert changes == []


def test_reappearing_aged_out_event_is_an_update():
    _, _, store = diff_and_update({}, [_event()], NOW)
    _, _, store = diff_and_update(store, [], LATER)
    verdict, changes, store = diff_and_update(store, [_event()], "2026-07-08T00:10:00+00:00")
    assert verdict == "CHANGED"
    assert changes == [{"event_id": "usgs-test1", "change": "updated"}]
    assert store["usgs-test1"]["status"] == "active"


def test_ids_union_matches_preferred_id_flip():
    """An event whose preferred id flipped networks is the same event."""
    first = _event(event_id="usgs-ci41287863", ids=("ci41287863", "us6000tafd"))
    _, _, store = diff_and_update({}, [first], NOW)

    flipped = _event(event_id="usgs-us6000tafd", ids=("us6000tafd", "nc999"))
    verdict, changes, store = diff_and_update(store, [flipped], LATER)

    assert verdict == "QUIET"
    assert changes == []
    # The canonical id never flips; the alias union grows.
    assert set(store) == {"usgs-ci41287863"}
    assert store["usgs-ci41287863"]["ids"] == ["ci41287863", "us6000tafd", "nc999"]
