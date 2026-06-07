"""TDD: Pydantic verdict models encode the project's core invariants as validation."""

import pytest
from pydantic import ValidationError

from agent.state import HealCandidate, HealProposal, HealVerdict, TriageVerdict


def test_triage_verdict_rejects_unknown_category():
    with pytest.raises(ValidationError):
        TriageVerdict(category="banana", confidence=0.9, evidence="x")


def test_triage_verdict_accepts_the_four_known_categories():
    for cat in ("drift", "regression", "flake", "data"):
        v = TriageVerdict(category=cat, confidence=0.5, evidence="e")
        assert v.category == cat


def test_triage_verdict_confidence_must_be_within_zero_and_one():
    with pytest.raises(ValidationError):
        TriageVerdict(category="drift", confidence=1.4, evidence="e")


def test_heal_proposal_requires_at_least_two_candidates():
    one = [HealCandidate(selector="#a", signal="role_name", rank=1, rationale="r")]
    with pytest.raises(ValidationError):
        HealProposal(candidates=one)


def test_heal_proposal_accepts_two_or_more_candidates():
    cands = [
        HealCandidate(selector="#a", signal="role_name", rank=1, rationale="r1"),
        HealCandidate(selector="#b", signal="nearby_testid", rank=2, rationale="r2"),
    ]
    assert len(HealProposal(candidates=cands).candidates) == 2


def test_heal_verdict_carries_the_false_heal_guard_fields():
    v = HealVerdict(
        approved=True,
        chosen_selector="#a",
        confidence=0.95,
        reason="step + assertion both hold",
        step_passed=True,
        assertion_held=True,
    )
    assert v.approved and v.step_passed and v.assertion_held
