"""End-to-end: the V2 definition of done, over the two-morning fixtures.

Morning 1 (2025-03-28, 06:30 UTC snapshot): Mandalay at Orange, PAGER
pending; DRC flood at Red. Morning 2 (the real final capture): Mandalay
Red on both feeds — the sitrep must lead with the ▲ ESCALATED card — and
the flood at Orange, landing in "Noted, quieter".
"""

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from agent import daily
from agent.assess import RecordedAssessor
from pipeline import store
from pipeline.render import validate_sitrep

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"
MORNING_1 = FIXTURES / "morning-1"
MORNING_2 = FIXTURES / "morning-2"


class SpyAssessor:
    """Counts invocations; replays the recorded output when asked."""

    def __init__(self, path=None):
        self.calls = 0
        self.recorded = RecordedAssessor(path) if path else None

    def __call__(self, context):
        self.calls += 1
        return self.recorded(context)


class NewsSpy:
    """A minimal assessor stand-in exposing only ``search_news`` — for
    testing the always-runs news path in isolation from the sitrep gate
    (``SpyAssessor`` above deliberately has no ``search_news``, so the
    quiet-morning test doesn't accidentally start exercising it)."""

    def __init__(self, path):
        self.calls = 0
        self.recorded = RecordedAssessor(path)

    def search_news(self, context):
        self.calls += 1
        return self.recorded.search_news(context)


def _run_morning(fixture_dir, data_dir, out_path):
    spy = SpyAssessor(fixture_dir / "assessment.json")
    manifest = daily.run_daily(fixture_dir, data_dir, out_path, spy)
    return manifest, spy


def test_two_morning_escalation_replay(tmp_path):
    data_dir = tmp_path / "data"

    manifest, spy = _run_morning(MORNING_1, data_dir, tmp_path / "sitrep-1.html")
    assert manifest["verdict"] == "CHANGED"
    assert spy.calls == 1

    manifest, spy = _run_morning(MORNING_2, data_dir, tmp_path / "sitrep-2.html")
    assert manifest["verdict"] == "CHANGED"
    changes = {c["event_id"]: c for c in manifest["changes"]}
    assert changes["gdacs-EQ-1474477"]["change"] == "escalated"
    assert changes["gdacs-FL-1103210"]["change"] == "downgraded"

    page = (tmp_path / "sitrep-2.html").read_text()

    # The ▲ ESCALATED card leads the event list.
    first_card = re.search(r'<article id="([^"]+)"[^>]*>', page)
    assert first_card.group(1) == "gdacs-EQ-1474477"
    card_body = page[first_card.start() : page.find("</article>", first_card.start())]
    assert "▲ ESCALATED" in card_body and "orange → red" in card_body

    # The GDACS+USGS pair is one card with audited merge evidence.
    assert re.search(r"merge: high \(Δt \d+ s · Δd \d+ km\)", card_body)
    assert "us7000pn9s" in card_body and "gdacs-EQ-1474477" in card_body

    # The downgrade lands in "Noted, quieter".
    quieter = page.split('data-quieter="1"')[1]
    assert "▽ DOWNGRADED" in quieter and "red → orange" in quieter

    # Every impact figure carries a provenance label; no external requests.
    validate_sitrep(page)
    impact_lines = re.findall(r'<li data-impact="1"', page)
    labels = re.findall(r'data-label="(Estimated|Reported|Reported: none)"', page)
    assert len(impact_lines) == len(labels) > 0
    assert 'data-label="Reported"' in page  # the ReliefWeb umbrellas landed

    # Editorial Green renders only with its companion chip.
    assert ">GREEN<" in page and ">EDITORIAL<" in page

    # Single column that holds under 720 px: one centred max-width container.
    assert "max-width:720px" in page


def test_model_wakes_only_when_the_gate_says_changed(tmp_path):
    quiet_spy = SpyAssessor()
    manifest = daily.run_daily(FIXTURES / "quiet", tmp_path / "data", tmp_path / "quiet.html", quiet_spy)
    assert manifest["verdict"] == "QUIET"
    assert quiet_spy.calls == 0  # deterministic layers decide; the model sleeps

    page = (tmp_path / "quiet.html").read_text()
    assert "All quiet" in page
    for feed in ("GDACS", "USGS", "RELIEFWEB"):
        assert f"<strong>{feed}</strong> ok" in page


def test_news_summary_runs_on_a_quiet_morning_too(tmp_path):
    """The one exception to "the model never decides whether to wake up"
    (agent/daily.py's docstring, by request): news search runs every day,
    independent of the sitrep gate — a quiet morning by the feeds' own
    thresholds can still be the morning a story breaks that none of them
    have caught."""
    fixture = tmp_path / "quiet-with-news"
    shutil.copytree(FIXTURES / "quiet", fixture)
    (fixture / "assessment.json").write_text(
        json.dumps(
            {
                "news_items": [
                    {
                        "headline": "Volcano activity increasing nearby",
                        "source": "Reuters",
                        "url": "https://reuters.example/volcano",
                        "published_at": "2025-04-09",
                        "event_id": "",
                        "note": "A standalone development the feeds haven't caught.",
                    }
                ]
            }
        )
    )

    data_dir = tmp_path / "data"
    spy = NewsSpy(fixture / "assessment.json")
    manifest = daily.run_daily(fixture, data_dir, tmp_path / "quiet.html", spy)
    assert manifest["verdict"] == "QUIET"
    assert spy.calls == 1  # the news check ran even though the model "slept"

    news = store.load_news(data_dir)
    assert news["items"][0]["headline"] == "Volcano activity increasing nearby"

    page = (tmp_path / "quiet.html").read_text()
    assert "Volcano activity increasing nearby" in page


def test_news_summary_does_not_double_call_on_a_changed_morning(tmp_path):
    """When the gate already woke the model, its own news_items cover the
    day — search_news must not also fire (no duplicate model call)."""

    class TrackedRecordedAssessor(RecordedAssessor):
        def __init__(self, path):
            super().__init__(path)
            self.news_calls = 0

        def search_news(self, context):
            self.news_calls += 1
            return super().search_news(context)

    assessor = TrackedRecordedAssessor(MORNING_1 / "assessment.json")
    daily.run_daily(MORNING_1, tmp_path / "data", tmp_path / "sitrep.html", assessor)
    assert assessor.news_calls == 0


def test_identical_rerun_is_quiet_and_model_free(tmp_path):
    data_dir = tmp_path / "data"
    _run_morning(MORNING_2, data_dir, tmp_path / "sitrep.html")
    spy = SpyAssessor()
    manifest = daily.run_daily(MORNING_2, data_dir, tmp_path / "sitrep.html", spy)
    assert manifest["verdict"] == "QUIET"
    assert spy.calls == 0


def test_daily_run_writes_a_timestamped_backup(tmp_path):
    data_dir = tmp_path / "data"
    out_path = tmp_path / "sitrep.html"
    manifest, _ = _run_morning(MORNING_1, data_dir, out_path)

    from datetime import datetime, timezone

    tag = datetime.fromisoformat(manifest["run_at"]).astimezone(timezone.utc).strftime(
        "%Y%m%dT%H%M%SZ"
    )
    backup_path = out_path.parent / "history" / f"sitrep-{tag}-run{manifest['run_number']}.html"
    assert backup_path.is_file()
    assert backup_path.read_text() == out_path.read_text()


def test_backups_accumulate_and_survive_a_later_overwrite(tmp_path):
    data_dir = tmp_path / "data"
    out_path = tmp_path / "sitrep.html"
    _run_morning(MORNING_1, data_dir, out_path)
    history_dir = out_path.parent / "history"
    first_backups = list(history_dir.glob("*.html"))
    assert len(first_backups) == 1
    first_content = first_backups[0].read_text()

    _run_morning(MORNING_2, data_dir, out_path)
    backups = sorted(history_dir.glob("*.html"))
    assert len(backups) == 2
    # The first run's backup is untouched even though out_path itself
    # (the "live" sitrep) was overwritten by the second run.
    assert first_backups[0].read_text() == first_content
    assert first_backups[0].read_text() != out_path.read_text()


def test_both_realtime_feeds_down_aborts_loudly(tmp_path):
    """No sitrep exists — abort is an alert, not a page (PRD §7)."""
    blind = tmp_path / "blind-fixture"
    blind.mkdir()
    (blind / "reliefweb.xml").write_text((FIXTURES / "quiet" / "reliefweb.xml").read_text())
    out_path = tmp_path / "sitrep.html"
    with pytest.raises(daily.Abort, match="both unreachable"):
        daily.run_daily(blind, tmp_path / "data", out_path, SpyAssessor())
    assert not out_path.exists()  # the previous sitrep stays live instead


def test_news_summary_persists_and_carries_forward(tmp_path):
    """skills/news-summary/SKILL.md end to end: a run that wakes the model
    with news_items writes data/news.json and renders it; a later quiet run
    (the model asleep) still shows the carried-forward search."""
    fixture = tmp_path / "morning-1-with-news"
    shutil.copytree(MORNING_1, fixture)
    assessment = json.loads((fixture / "assessment.json").read_text())
    assessment["news_items"] = [
        {
            "headline": "Strong quake shakes central Myanmar",
            "source": "Reuters",
            "url": "https://reuters.example/mandalay-quake",
            "published_at": "2025-03-28",
            "event_id": "gdacs-EQ-1474477",
            "note": "Wire coverage matches the reported epicentre.",
        }
    ]
    (fixture / "assessment.json").write_text(json.dumps(assessment))

    data_dir = tmp_path / "data"
    manifest, spy = _run_morning(fixture, data_dir, tmp_path / "sitrep-news.html")
    assert manifest["verdict"] == "CHANGED"

    news = store.load_news(data_dir)
    assert news["items"][0]["headline"] == "Strong quake shakes central Myanmar"

    page = (tmp_path / "sitrep-news.html").read_text()
    assert "News mentions" in page
    assert "Strong quake shakes central Myanmar" in page
    validate_sitrep(page)

    # A later identical re-run is QUIET (model asleep) but the news search
    # still shows up — carried forward, not erased by a quiet morning.
    quiet_spy = SpyAssessor()
    quiet_manifest = daily.run_daily(
        fixture, data_dir, tmp_path / "sitrep-news-2.html", quiet_spy
    )
    assert quiet_manifest["verdict"] == "QUIET"
    assert quiet_spy.calls == 0
    quiet_page = (tmp_path / "sitrep-news-2.html").read_text()
    assert "Strong quake shakes central Myanmar" in quiet_page


def test_daily_cli_prints_the_verdict(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "agent" / "daily.py"),
            "--replay",
            str(MORNING_1),
            "--data-dir",
            str(tmp_path / "data"),
            "--out",
            str(tmp_path / "sitrep.html"),
            "--assess",
            "recorded",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip().splitlines()[-1] == "CHANGED"
    assert (tmp_path / "sitrep.html").is_file()
