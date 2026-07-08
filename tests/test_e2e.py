"""End-to-end: the definition of done, exercised over the fixtures."""

import subprocess
import sys
from pathlib import Path

from pipeline.runner import run_once

ROOT = Path(__file__).resolve().parent.parent
RUN_PY = ROOT / "scripts" / "run.py"


def test_eventful_replay_changes_then_stays_quiet(tmp_path, eventful_dir):
    data_dir = tmp_path / "data"
    page = tmp_path / "dashboard.html"

    manifest = run_once(eventful_dir, data_dir, page)
    assert manifest["verdict"] == "CHANGED"
    assert len(manifest["active_events"]) == 7
    # data/ written: one file per event + the run manifest.
    assert (data_dir / "manifest.json").is_file()
    assert len(list((data_dir / "events").glob("*.json"))) == 7

    html = page.read_text()
    assert "Mandalay" in html
    assert "Flood in Democratic Republic of Congo" in html
    assert "All quiet" not in html

    # Same fixture again: the diff runs against our own stored state.
    manifest = run_once(eventful_dir, data_dir, page)
    assert manifest["verdict"] == "QUIET"
    assert manifest["changes"] == []
    # The dashboard still shows the current events, now with a QUIET verdict.
    html = page.read_text()
    assert "Mandalay" in html
    assert "QUIET" in html


def test_quiet_replay_from_fresh_state(tmp_path, quiet_dir):
    data_dir = tmp_path / "data"
    page = tmp_path / "dashboard.html"

    manifest = run_once(quiet_dir, data_dir, page)
    assert manifest["verdict"] == "QUIET"
    assert manifest["active_events"] == []
    assert manifest["feeds"]["gdacs"]["count_fetched"] > 0
    assert manifest["feeds"]["usgs"]["count_fetched"] > 0

    html = page.read_text()
    assert "All quiet" in html
    assert "No events cleared the gate" in html


def test_cli_prints_the_verdict(tmp_path, eventful_dir):
    def run_cli():
        result = subprocess.run(
            [
                sys.executable,
                str(RUN_PY),
                "--replay",
                str(eventful_dir),
                "--data-dir",
                str(tmp_path / "data"),
                "--out",
                str(tmp_path / "dashboard.html"),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip().splitlines()[-1]

    assert run_cli() == "CHANGED"
    assert run_cli() == "QUIET"
