"""Unit: the sitrep document's hard rendering rules (design §§3–5, 9)."""

import pytest
from conftest import make_gdacs_event
from pipeline.render import (
    RenderError,
    impact_line,
    render_sitrep,
    validate_sitrep,
)

RUN_AT = "2025-03-28T00:35:00+00:00"


def _manifest(**overrides):
    manifest = {
        "run_at": RUN_AT,
        "run_number": 2,
        "mode": "replay:test",
        "verdict": "QUIET",
        "feeds": {
            "gdacs": {"status": "ok", "fetched_at": RUN_AT, "count_fetched": 10, "count_gated": 0},
            "usgs": {"status": "ok", "fetched_at": RUN_AT, "count_fetched": 5, "count_gated": 0},
            "reliefweb": {"status": "ok", "fetched_at": RUN_AT, "count_fetched": 3, "count_gated": 0},
        },
        "changes": [],
    }
    manifest.update(overrides)
    return manifest


def _record(**overrides):
    record = make_gdacs_event(alert_level="orange", episode_alert_level="orange")
    record.update(status="active", gate_reason="GDACS alert orange")
    record.update(overrides)
    return record


def test_a_bare_impact_figure_is_a_rendering_bug():
    with pytest.raises(RenderError, match="bare impact figure"):
        impact_line("", "180,000 people affected")
    with pytest.raises(RenderError):
        impact_line("Roughly", "180,000 people affected")
    assert "Estimated" in impact_line("Estimated", "GDACS alert score 2")


def test_validation_rejects_external_requests():
    page = render_sitrep({}, _manifest())
    validate_sitrep(page)  # the real page is self-contained
    for poison in (
        '<img src="https://tile.example/x.png">',
        '<link rel="stylesheet" href="https://cdn.example/a.css">',
        '<script src="https://cdn.example/a.js"></script>',
        "<style>@import url(https://cdn.example/a.css);</style>",
    ):
        with pytest.raises(RenderError, match="self-contained"):
            validate_sitrep(page.replace("</body>", poison + "</body>"))


def test_validation_rejects_a_bare_figure_in_the_output():
    page = render_sitrep({}, _manifest())
    poisoned = page.replace(
        "</body>", '<ul><li data-impact="1">180,000 people affected</li></ul></body>'
    )
    with pytest.raises(RenderError, match="bare impact figure"):
        validate_sitrep(poisoned)


def test_all_quiet_page_is_first_class():
    page = render_sitrep({}, _manifest())
    assert "All quiet" in page
    assert "No events cleared the gate" in page
    # Feed-health chips with last-success stamps account for the silence.
    for feed in ("GDACS", "USGS", "RELIEFWEB"):
        assert f"<strong>{feed}</strong> ok" in page
    assert "What this report cannot see" in page  # blindness footer, always


def test_degraded_morning_names_the_lost_hazards():
    manifest = _manifest()
    manifest["feeds"]["gdacs"] = {"status": "down", "fetched_at": None, "count_fetched": 0, "count_gated": 0}
    page = render_sitrep({}, manifest)
    assert 'data-degraded-banner="1"' in page
    # Readers think in hazards, not feeds (design §3).
    assert "cyclone, flood, volcano, drought and wildfire coverage is blind" in page
    assert "earthquake coverage continues via USGS" in page
    assert "<strong>GDACS</strong> down" in page
    assert "no successful fetch yet" in page


def test_editorial_green_carries_its_mandatory_companion_chip():
    candidate = make_gdacs_event(event_id="gdacs-VO-9", hazard="VO", title="Eruption Poas")
    candidate["merge"] = {"confidence": "single-source", "evidence": None}
    assessment = {
        "summary": "A quiet morning, with one volcano worth a line.",
        "change_notes": {},
        "editorial_greens": [{"event_id": "gdacs-VO-9", "reason": "erupting near visitors"}],
    }
    page = render_sitrep({}, _manifest(), assessment, [candidate])
    assert ">GREEN<" in page and ">EDITORIAL<" in page
    assert "erupting near visitors" in page
    # Without the model's promotion, no Green chip exists at all.
    bare = render_sitrep({}, _manifest())
    assert ">GREEN<" not in bare


def test_content_is_escaped_and_stays_self_contained():
    record = _record(title='<script src="https://evil.example/x.js"></script>')
    manifest = _manifest(verdict="CHANGED", changes=[{"event_id": record["event_id"], "change": "new"}])
    page = render_sitrep({record["event_id"]: record}, manifest)
    assert "<script" not in page  # escaped, and validate_sitrep already ran


def test_downgrade_lands_in_noted_quieter():
    record = _record(alert_level="green", episode_alert_level="green", status="below-gate")
    manifest = _manifest(
        verdict="CHANGED",
        changes=[{"event_id": record["event_id"], "change": "downgraded", "detail": "orange → green"}],
    )
    page = render_sitrep({record["event_id"]: record}, manifest)
    quieter = page.split('data-quieter="1"')[1]
    assert "▽ DOWNGRADED" in quieter
    assert "orange → green" in quieter


def test_news_zone_states_it_has_never_run():
    # Absence would read as "nothing to see"; the zone must say so instead
    # (goal.md's "all quiet is a statement, not an absence" principle).
    page = render_sitrep({}, _manifest())
    assert "News mentions" in page
    assert "has not run yet" in page


def test_news_zone_says_so_when_nothing_was_found():
    page = render_sitrep(
        {}, _manifest(), news={"checked_at": RUN_AT, "searched": True, "items": []}
    )
    assert "News mentions" in page
    assert "No relevant coverage found" in page


def test_news_zone_distinguishes_not_searched_from_searched_and_empty():
    # searched=False (the model never called web_search this run) must not
    # be confused with searched=True and nothing worth surfacing turned up.
    page = render_sitrep(
        {}, _manifest(), news={"checked_at": RUN_AT, "searched": False, "items": []}
    )
    assert "did not search this run" in page


def test_news_item_is_attributed_and_links_its_related_event():
    record = _record()
    news = {
        "checked_at": RUN_AT,
        "items": [
            {
                "headline": "Strong quake shakes central region",
                "source": "Reuters",
                "url": "https://reuters.example/a",
                "published_at": "2025-03-28",
                "event_id": record["event_id"],
                "note": "Wire coverage matches the reported epicentre.",
            }
        ],
    }
    page = render_sitrep({record["event_id"]: record}, _manifest(), news=news)
    news_zone = page.split('data-news="1"')[1]
    assert "Strong quake shakes central region" in news_zone
    assert 'href="https://reuters.example/a"' in news_zone
    assert "Reuters" in news_zone and "2025-03-28" in news_zone
    assert f'href="#{record["event_id"]}"' in news_zone
    assert "unverified external reporting" in page
    validate_sitrep(page)  # attribution links don't trip the no-network rule
