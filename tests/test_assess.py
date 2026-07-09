"""Unit: the model may add an editorial Green but never remove or invent
(PRD §5) — enforced deterministically on its output."""

import json

import pytest
from agent.assess import RecordedAssessor, validate_assessment, validate_news_items

CONTEXT = {
    "events": [{"event_id": "gdacs-EQ-1"}],
    "candidate_greens": [{"event_id": "gdacs-VO-9"}],
}


def _assessment(**overrides):
    assessment = {
        "summary": "A morning.",
        "change_notes": {},
        "editorial_greens": [],
        "news_items": [],
    }
    assessment.update(overrides)
    return assessment


def test_valid_assessment_passes_through():
    assessment = _assessment(
        change_notes={"gdacs-EQ-1": "It moved."},
        editorial_greens=[{"event_id": "gdacs-VO-9", "reason": "notable"}],
    )
    assert validate_assessment(assessment, CONTEXT) is assessment


def test_summary_is_mandatory():
    with pytest.raises(ValueError, match="no summary"):
        validate_assessment(_assessment(summary=""), CONTEXT)


def test_change_notes_cannot_invent_events():
    with pytest.raises(ValueError, match="unknown event"):
        validate_assessment(
            _assessment(change_notes={"gdacs-EQ-invented": "…"}), CONTEXT
        )


def test_editorial_promotion_only_from_the_candidate_greens():
    with pytest.raises(ValueError, match="non-candidate"):
        validate_assessment(
            _assessment(editorial_greens=[{"event_id": "gdacs-EQ-1", "reason": "big"}]),
            CONTEXT,
        )


def test_editorial_promotion_requires_a_reason():
    with pytest.raises(ValueError, match="without a reason"):
        validate_assessment(
            _assessment(editorial_greens=[{"event_id": "gdacs-VO-9", "reason": ""}]),
            CONTEXT,
        )


def test_recorded_assessor_normalises_the_wire_shape(tmp_path):
    """Recorded files use the model's structured-output shape (lists of
    {event_id, ...}); assessors return the internal keyed form."""
    path = tmp_path / "assessment.json"
    path.write_text(
        json.dumps(
            {
                "summary": " A morning. ",
                "change_notes": [{"event_id": "gdacs-EQ-1", "note": "It moved."}],
                "editorial_greens": [{"event_id": "gdacs-VO-9", "reason": "notable"}],
            }
        )
    )
    assessment = RecordedAssessor(path)({})
    assert assessment == {
        "summary": "A morning.",
        "change_notes": {"gdacs-EQ-1": "It moved."},
        "editorial_greens": [{"event_id": "gdacs-VO-9", "reason": "notable"}],
        "news_items": [],
    }


def test_news_item_requires_attribution_to_survive_normalisation(tmp_path):
    """skills/news-summary/SKILL.md: no source + url, no item — dropped
    silently at normalise time, same as an incomplete change note."""
    path = tmp_path / "assessment.json"
    path.write_text(
        json.dumps(
            {
                "summary": "A morning.",
                "change_notes": [],
                "editorial_greens": [],
                "news_items": [
                    {"headline": "No source", "source": "", "url": "https://x.example"},
                    {"headline": "No url", "source": "Reuters", "url": ""},
                    {
                        "headline": "Fully attributed",
                        "source": "Reuters",
                        "url": "https://reuters.example/a",
                        "published_at": "2026-07-09",
                        "event_id": "gdacs-EQ-1",
                        "note": "Corroborates the quake.",
                    },
                ],
            }
        )
    )
    assessment = RecordedAssessor(path)({})
    assert len(assessment["news_items"]) == 1
    assert assessment["news_items"][0]["headline"] == "Fully attributed"


def test_news_item_may_stand_alone_or_corroborate_a_known_event():
    assessment = _assessment(
        news_items=[
            {
                "headline": "Quake felt across region",
                "source": "Reuters",
                "url": "https://reuters.example/a",
                "published_at": "2026-07-09",
                "event_id": "gdacs-EQ-1",
                "note": "Corroborates the quake.",
            }
        ]
    )
    assert validate_assessment(assessment, CONTEXT) is assessment


def test_news_item_cannot_reference_an_unknown_event():
    with pytest.raises(ValueError, match="unknown event"):
        validate_assessment(
            _assessment(
                news_items=[
                    {
                        "headline": "Unrelated",
                        "source": "Reuters",
                        "url": "https://reuters.example/a",
                        "event_id": "gdacs-EQ-invented",
                    }
                ]
            ),
            CONTEXT,
        )


def test_news_item_without_attribution_fails_validation():
    with pytest.raises(ValueError, match="attribution"):
        validate_assessment(
            _assessment(news_items=[{"headline": "No source", "source": "", "url": ""}]),
            CONTEXT,
        )


def test_validate_news_items_standalone_matches_the_embedded_checks():
    """skills/news-summary/SKILL.md's always-runs call reuses the exact
    same invention guard as the gated assessment, factored out so both
    paths stay in sync."""
    good = [
        {
            "headline": "Quake felt across region",
            "source": "Reuters",
            "url": "https://reuters.example/a",
            "event_id": "gdacs-EQ-1",
        }
    ]
    assert validate_news_items(good, CONTEXT) is good
    with pytest.raises(ValueError, match="unknown event"):
        validate_news_items(
            [{"source": "Reuters", "url": "https://x.example", "event_id": "invented"}],
            CONTEXT,
        )
    with pytest.raises(ValueError, match="attribution"):
        validate_news_items([{"source": "", "url": ""}], CONTEXT)


def test_recorded_assessor_search_news_replays_the_same_fixture(tmp_path):
    """The always-runs news path (agent/daily.py's search_news branch)
    needs a fixture-replay lane too, so quiet-morning news can be tested
    offline the same way the gated assessment already is."""
    path = tmp_path / "assessment.json"
    path.write_text(
        json.dumps(
            {
                "news_items": [
                    {
                        "headline": "Standalone development",
                        "source": "Reuters",
                        "url": "https://reuters.example/b",
                        "published_at": "2026-07-09",
                        "event_id": "",
                        "note": "Not tied to any known event.",
                    }
                ]
            }
        )
    )
    result = RecordedAssessor(path).search_news({})
    assert result["searched"] is None  # unknowable from a static recording
    assert result["items"][0]["headline"] == "Standalone development"
    assert result["items"][0]["event_id"] is None
