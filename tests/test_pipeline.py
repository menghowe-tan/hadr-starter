"""The stage stub honours the §13 contract the workflows condition on."""

import json
from datetime import datetime, timezone
from pathlib import Path

import health
import stub_pipeline

FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime(2025, 7, 30, 0, 30, tzinfo=timezone.utc)


def run(scenario, data_dir, now=NOW):
    return stub_pipeline.run(scenario, data_dir, FIXTURES, now)


def test_eventful_writes_valid_store_and_machine_readable_verdict(tmp_path, capsys):
    assert run("eventful", tmp_path) == 0
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["verdict"] == "CHANGED"
    assert len(list((tmp_path / "events").glob("*.json"))) == 2
    verdict_line = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert verdict_line["verdict"] == "CHANGED"
    assert verdict_line["health"]["status"] == "ok"


def test_quiet_scenario(tmp_path, capsys):
    assert run("quiet", tmp_path) == 0
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["verdict"] == "QUIET" and manifest["changed_event_ids"] == []
    assert json.loads(capsys.readouterr().out.strip().splitlines()[-1])["verdict"] == "QUIET"


def test_both_down_aborts_and_touches_nothing(tmp_path):
    assert run("both-down", tmp_path) == health.ABORT_EXIT_CODE == 3
    assert not (tmp_path / "manifest.json").exists()


def test_gdacs_down_is_degraded_but_publishes(tmp_path, capsys):
    assert run("gdacs-down", tmp_path) == 0
    verdict_line = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert verdict_line["health"]["status"] == "degraded"
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["feeds"]["gdacs"]["status"] == "down"


def test_deploy_state_survives_reruns(tmp_path):
    run("eventful", tmp_path)
    manifest_path = tmp_path / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["deploy_state"] = {"out_hash": "abc123"}
    manifest_path.write_text(json.dumps(manifest))
    run("quiet", tmp_path)
    assert json.loads(manifest_path.read_text())["deploy_state"] == {"out_hash": "abc123"}
