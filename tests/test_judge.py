"""TDD: judge_heal heal tool. Approves a heal only if the step passes AND the downstream
assertion still holds. The assertion_held=False override is the false-heal guard in code:
no LLM 'approve' can overturn a hollow assertion.

Unit tests stub the judge LLM; one live test hits DeepSeek.
"""

import os

import pytest

from agent.state import HealCandidate, HealVerdict
from tools.judge_heal import judge_heal

CANDIDATE = HealCandidate(selector="role=button[name='Login']", signal="role_name", rank=1, rationale="r")


def test_judge_approves_when_step_and_assertion_hold_and_llm_approves():
    stub = lambda m, *, name: {"approved": True, "confidence": 0.95, "reason": "looks right"}
    v = judge_heal(CANDIDATE, step_passed=True, assertion_held=True, complete=stub)
    assert isinstance(v, HealVerdict)
    assert v.approved is True
    assert v.chosen_selector == CANDIDATE.selector


def test_judge_rejects_when_assertion_hollow_even_if_llm_approves_confidently():
    # the false-heal trap: step green, assertion meaningless. Code overrides the LLM.
    stub = lambda m, *, name: {"approved": True, "confidence": 0.99, "reason": "passes!"}
    v = judge_heal(CANDIDATE, step_passed=True, assertion_held=False, complete=stub)
    assert v.approved is False
    assert v.assertion_held is False


def test_judge_rejects_when_step_did_not_pass():
    stub = lambda m, *, name: {"approved": True, "confidence": 0.9, "reason": "x"}
    v = judge_heal(CANDIDATE, step_passed=False, assertion_held=True, complete=stub)
    assert v.approved is False


def test_judge_rejects_when_llm_declines():
    stub = lambda m, *, name: {"approved": False, "confidence": 0.4, "reason": "wrong element"}
    v = judge_heal(CANDIDATE, step_passed=True, assertion_held=True, complete=stub)
    assert v.approved is False


@pytest.mark.live
def test_judge_live_deepseek_returns_a_verdict():
    from dotenv import load_dotenv

    load_dotenv()
    if not os.environ.get("DEEPSEEK_API_KEY"):
        pytest.skip("no DEEPSEEK_API_KEY")
    v = judge_heal(CANDIDATE, step_passed=True, assertion_held=True)
    assert isinstance(v.approved, bool)
    assert 0.0 <= v.confidence <= 1.0
