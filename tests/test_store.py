"""Integration: the committed-JSON store round-trips identically."""

from conftest import load_fixture
from pipeline import store
from pipeline.diff import diff_and_update
from pipeline.gate import apply_gate
from pipeline.normalise import normalise_gdacs, normalise_usgs

NOW = "2026-07-08T00:00:00+00:00"


def test_round_trip(tmp_path, eventful_dir):
    events = normalise_gdacs(load_fixture(eventful_dir, "gdacs")) + normalise_usgs(
        load_fixture(eventful_dir, "usgs")
    )
    _, changes, records = diff_and_update({}, apply_gate(events), NOW)
    manifest = {"run_at": NOW, "verdict": "CHANGED", "changes": changes}

    store.save(tmp_path, records, manifest)

    assert store.load_events(tmp_path) == records
    assert store.load_manifest(tmp_path) == manifest
    # One file per event, plus the manifest (CLAUDE.md).
    assert len(list((tmp_path / "events").glob("*.json"))) == len(records)
    assert (tmp_path / "manifest.json").is_file()


def test_empty_store_loads_empty(tmp_path):
    assert store.load_events(tmp_path) == {}
    assert store.load_manifest(tmp_path) is None
