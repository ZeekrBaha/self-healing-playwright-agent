"""TDD: triage node. Deterministic 1-LLM-call classification -> TriageVerdict.

Unit tests inject a stub `complete`; one live test (deselected by default) hits OpenAI.
"""

import os

import pytest

from agent.nodes import classify_triage
from agent.state import FailureSnapshot, TriageVerdict


def make_failure():
    return FailureSnapshot(
        failing_step="click the login button",
        error_class="selector_resolution",
        broken_selector="#login-btn",
        dom_html="<button id='signin'>Login</button>",
        a11y_tree={"role": "button", "name": "Login"},
    )


def test_classify_triage_returns_verdict_from_the_llm():
    def stub(messages, *, name):
        return {"category": "drift", "confidence": 0.91, "evidence": "testid renamed"}

    v = classify_triage(make_failure(), intent="user logs in", complete=stub)
    assert isinstance(v, TriageVerdict)
    assert v.category == "drift"
    assert v.confidence == 0.91


def test_classify_triage_feeds_the_test_intent_into_the_prompt():
    seen = {}

    def spy(messages, *, name):
        seen["messages"] = messages
        return {"category": "regression", "confidence": 0.8, "evidence": "x"}

    classify_triage(make_failure(), intent="UNIQUE_INTENT_TOKEN_42", complete=spy)
    assert "UNIQUE_INTENT_TOKEN_42" in str(seen["messages"])


@pytest.mark.parametrize("cat", ["drift", "regression", "flake", "data"])
def test_classify_triage_passes_through_each_category(cat):
    def stub(messages, *, name):
        return {"category": cat, "confidence": 0.7, "evidence": "e"}

    assert classify_triage(make_failure(), intent="i", complete=stub).category == cat


@pytest.mark.live
def test_classify_triage_live_openai_returns_a_valid_category():
    from dotenv import load_dotenv

    load_dotenv()
    if not os.environ.get("OPENAI_API_KEY"):
        pytest.skip("no OPENAI_API_KEY")
    v = classify_triage(make_failure(), intent="user logs in and reaches the inventory page")
    assert v.category in ("drift", "regression", "flake", "data")
    assert 0.0 <= v.confidence <= 1.0
