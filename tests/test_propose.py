"""TDD: propose_candidates heal tool. Multi-signal ranked selectors -> HealProposal.

Defensive: refuses anything but drift (belt-and-suspenders with graph topology).
Unit tests stub the LLM; one live test hits OpenAI.
"""

import os

import pytest

from agent.state import FailureSnapshot, HealProposal, TriageVerdict
from tools.propose_candidates import NotDriftError, propose_candidates


def make_failure():
    return FailureSnapshot(
        failing_step="click the login button",
        error_class="selector_resolution",
        broken_selector="#login-btn",
        dom_html="<button id='signin' aria-label='Login'>Login</button>",
        a11y_tree={"role": "button", "name": "Login"},
    )


DRIFT = TriageVerdict(category="drift", confidence=0.9, evidence="testid renamed")

GOOD_RAW = {
    "candidates": [
        {"selector": "#signin", "signal": "nearby_testid", "rank": 1, "rationale": "id changed"},
        {"selector": "role=button[name='Login']", "signal": "role_name", "rank": 2, "rationale": "stable role+name"},
    ]
}


def test_propose_returns_a_heal_proposal_from_the_llm():
    proposal = propose_candidates(make_failure(), DRIFT, complete=lambda m, *, name: GOOD_RAW)
    assert isinstance(proposal, HealProposal)
    assert len(proposal.candidates) >= 2


def test_propose_refuses_non_drift_without_calling_the_llm():
    called = {"n": 0}

    def spy(messages, *, name):
        called["n"] += 1
        return GOOD_RAW

    regression = TriageVerdict(category="regression", confidence=0.9, evidence="wrong price")
    with pytest.raises(NotDriftError):
        propose_candidates(make_failure(), regression, complete=spy)
    assert called["n"] == 0  # guard fires BEFORE spending an LLM call


def test_propose_prompt_includes_the_a11y_signal():
    seen = {}

    def spy(messages, *, name):
        seen["m"] = messages
        return GOOD_RAW

    propose_candidates(make_failure(), DRIFT, complete=spy)
    assert "Login" in str(seen["m"])  # accessible name surfaced to the proposer


@pytest.mark.live
def test_propose_live_openai_returns_two_or_more_candidates():
    from dotenv import load_dotenv

    load_dotenv()
    if not os.environ.get("OPENAI_API_KEY"):
        pytest.skip("no OPENAI_API_KEY")
    proposal = propose_candidates(make_failure(), DRIFT)
    assert len(proposal.candidates) >= 2
