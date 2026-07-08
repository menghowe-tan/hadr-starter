"""Unit: the model may add an editorial Green but never remove or invent
(PRD §5) — enforced deterministically on its output."""

import json

import pytest
from agent.assess import RecordedAssessor, validate_assessment

CONTEXT = {
    "events": [{"event_id": "gdacs-EQ-1"}],
    "candidate_greens": [{"event_id": "gdacs-VO-9"}],
}


def _assessment(**overrides):
    assessment = {"summary": "A morning.", "change_notes": {}, "editorial_greens": []}
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
    }
