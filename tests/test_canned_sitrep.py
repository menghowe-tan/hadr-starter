"""Model-free sitrep pages: all-quiet, canned assessment, degraded banner text."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
import render_canned_sitrep
import stub_pipeline

import agent.tools

FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime(2025, 7, 30, 0, 30, tzinfo=timezone.utc)


@pytest.fixture
def out_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(agent.tools, "OUT_DIR", tmp_path / "out")
    return tmp_path / "out"


def render(tmp_path, out_dir, scenario, mode):
    data = tmp_path / "data"
    stub_pipeline.run(scenario, data, FIXTURES, NOW)
    args = ["--mode", mode, "--data", str(data), "--now", NOW.isoformat()]
    assert render_canned_sitrep.main(args) == 0
    return (out_dir / "sitrep" / "index.html").read_text()


def test_all_quiet_is_a_first_class_page(tmp_path, out_dir):
    page = render(tmp_path, out_dir, "quiet", "quiet")
    assert "All quiet" in page and "pipeline ran and found nothing" in page
    assert "GDACS last success" in page  # quiet must be checkable
    assert "cannot see" in page


def test_canned_assessment_renders_the_store(tmp_path, out_dir):
    page = render(tmp_path, out_dir, "eventful", "canned")
    assert "Kamchatka" in page and "ESCALATED" in page
    assert "Estimated" in page and "Reported" in page
    assert 'id="us6000qw60"' in page  # sitrep card anchor the map links to


def test_degraded_morning_names_lost_hazards(tmp_path, out_dir):
    page = render(tmp_path, out_dir, "gdacs-down", "canned")
    assert "Degraded coverage this morning" in page
    assert "cyclone, flood, volcano" in page


def test_model_free_by_construction(monkeypatch, tmp_path, out_dir):
    # importing/calling the canned renderer must never construct an API client
    import anthropic

    def explode(*a, **k):
        raise AssertionError("model client constructed in a deterministic path")

    monkeypatch.setattr(anthropic, "Anthropic", explode)
    render(tmp_path, out_dir, "quiet", "quiet")
