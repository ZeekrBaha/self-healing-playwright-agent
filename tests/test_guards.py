"""TDD: the safety guards. These encode the two non-negotiable invariants.

They are pure functions so the tool layer (ADR-006) can call them and the LLM cannot
route around them.
"""

from agent.guards import can_apply, can_propose, should_force_escalate
from agent.state import HealVerdict, TriageVerdict


def _verdict(approved=True, confidence=0.95, assertion_held=True):
    return HealVerdict(
        approved=approved,
        chosen_selector="#a",
        confidence=confidence,
        reason="r",
        step_passed=True,
        assertion_held=assertion_held,
    )


# --- can_propose: never heal anything but drift -----------------------------------

def test_can_propose_true_only_for_drift():
    assert can_propose(TriageVerdict(category="drift", confidence=0.9, evidence="e")) is True


def test_can_propose_false_for_regression():
    assert can_propose(TriageVerdict(category="regression", confidence=0.9, evidence="e")) is False


def test_can_propose_false_for_flake_and_data():
    for cat in ("flake", "data"):
        assert can_propose(TriageVerdict(category=cat, confidence=0.9, evidence="e")) is False


# --- can_apply: only an approved, confident, assertion-preserving heal -------------

TAU = 0.8


def test_can_apply_true_when_approved_confident_and_assertion_held():
    assert can_apply(_verdict(), tau=TAU) is True


def test_can_apply_false_when_not_approved():
    assert can_apply(_verdict(approved=False), tau=TAU) is False


def test_can_apply_false_below_threshold():
    assert can_apply(_verdict(confidence=0.5), tau=TAU) is False


def test_can_apply_false_when_assertion_hollow_even_if_confident():
    # the false-heal trap: step green, assertion meaningless -> must NOT apply
    assert can_apply(_verdict(assertion_held=False), tau=TAU) is False


# --- cost guardrail: cap LLM heal attempts per run (REQ-009) -----------------------

def test_should_force_escalate_false_below_cap():
    assert should_force_escalate(attempts=1, max_attempts=3) is False


def test_should_force_escalate_true_at_cap():
    assert should_force_escalate(attempts=3, max_attempts=3) is True


def test_should_force_escalate_true_above_cap():
    assert should_force_escalate(attempts=4, max_attempts=3) is True
