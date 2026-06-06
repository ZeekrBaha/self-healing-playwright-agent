"""TDD: the full agent graph (ADR-006). Deterministic integration tests with stub LLMs and a
fake browser runner prove the two headline flows + the safety routing end-to-end.

`run_step(selector) -> (step_passed, assertion_held)` is the injected browser boundary.
"""

from pathlib import Path

import pytest

from agent.graph import Deps, build_graph
from agent.state import FailureSnapshot
from memory.store import HealMemoryStore
from tools.memory_io import remember_fix


def base_state(test_file: Path):
    return {
        "test_id": "login_test",
        "step_id": "click_login",
        "test_file": str(test_file),
        "test_intent": "user logs in and reaches inventory",
        "failure": FailureSnapshot(
            failing_step="click login",
            error_class="selector_resolution",
            broken_selector="#login-old",
            dom_html="<button id='login-new'>Login</button>",
            a11y_tree={"role": "button", "name": "Login"},
        ),
        "attempts": 0,
    }


def make_test_file(tmp_path: Path) -> tuple[Path, Path]:
    test_dir = tmp_path / "sut" / "tests"
    test_dir.mkdir(parents=True)
    f = test_dir / "login_test.py"
    f.write_text('page.locator("#login-old").click()\n')
    return test_dir, f


def triage_as(category):
    return lambda m, *, name: {"category": category, "confidence": 0.9, "evidence": "e"}


PROPOSE_TWO = lambda m, *, name: {
    "candidates": [
        {"selector": "#login-new", "signal": "nearby_testid", "rank": 1, "rationale": "id changed"},
        {"selector": "role=button[name='Login']", "signal": "role_name", "rank": 2, "rationale": "stable"},
    ]
}
JUDGE_APPROVE = lambda m, *, name: {"approved": True, "confidence": 0.95, "reason": "ok"}


def test_drift_heals_and_patches_the_test_file(tmp_path):
    test_dir, f = make_test_file(tmp_path)
    deps = Deps(
        triage_complete=triage_as("drift"),
        propose_complete=PROPOSE_TWO,
        judge_complete=JUDGE_APPROVE,
        run_step=lambda sel: (True, True),  # step passes, assertion holds
        store=HealMemoryStore(tmp_path / "mem.json"),
        test_dir=test_dir,
        artifacts_dir=tmp_path / "runs",
    )
    out = build_graph(deps).invoke(base_state(f))
    assert out["outcome"] == "healed"
    assert "#login-new" in f.read_text()
    assert "#login-old" not in f.read_text()


def test_regression_is_reported_and_never_proposes_a_heal(tmp_path):
    test_dir, f = make_test_file(tmp_path)
    propose_calls = {"n": 0}

    def propose_spy(m, *, name):
        propose_calls["n"] += 1
        return PROPOSE_TWO(m, name=name)

    deps = Deps(
        triage_complete=triage_as("regression"),
        propose_complete=propose_spy,
        judge_complete=JUDGE_APPROVE,
        run_step=lambda sel: (True, True),
        store=HealMemoryStore(tmp_path / "mem.json"),
        test_dir=test_dir,
        artifacts_dir=tmp_path / "runs",
    )
    out = build_graph(deps).invoke(base_state(f))
    assert out["outcome"] == "reported"
    assert propose_calls["n"] == 0  # the healer is never reached for a regression
    assert f.read_text() == 'page.locator("#login-old").click()\n'  # file untouched


def test_false_heal_escalates_instead_of_applying(tmp_path):
    test_dir, f = make_test_file(tmp_path)
    deps = Deps(
        triage_complete=triage_as("drift"),
        propose_complete=PROPOSE_TWO,
        judge_complete=JUDGE_APPROVE,  # LLM would approve...
        run_step=lambda sel: (True, False),  # ...but the assertion is hollow
        store=HealMemoryStore(tmp_path / "mem.json"),
        test_dir=test_dir,
        artifacts_dir=tmp_path / "runs",
    )
    out = build_graph(deps).invoke(base_state(f))
    assert out["outcome"] == "escalated"
    assert "#login-old" in f.read_text()  # NOT patched


def test_memory_hit_replays_with_zero_llm_calls(tmp_path):
    test_dir, f = make_test_file(tmp_path)
    store = HealMemoryStore(tmp_path / "mem.json")
    remember_fix(store, test_id="login_test", step_id="click_login",
                 broken_selector="#login-old", fixed_selector="#login-new")
    llm_calls = {"n": 0}

    def no_llm(m, *, name):
        llm_calls["n"] += 1
        return {}

    deps = Deps(
        triage_complete=triage_as("drift"),
        propose_complete=no_llm, judge_complete=no_llm,
        run_step=lambda sel: (True, True),
        store=store, test_dir=test_dir, artifacts_dir=tmp_path / "runs",
    )
    out = build_graph(deps).invoke(base_state(f))
    assert out["outcome"] == "healed"
    assert llm_calls["n"] == 0  # replayed from memory, no proposer/judge calls


def test_flake_routes_to_retry(tmp_path):
    test_dir, f = make_test_file(tmp_path)
    deps = Deps(
        triage_complete=triage_as("flake"),
        propose_complete=PROPOSE_TWO, judge_complete=JUDGE_APPROVE,
        run_step=lambda sel: (True, True),
        store=HealMemoryStore(tmp_path / "mem.json"),
        test_dir=test_dir, artifacts_dir=tmp_path / "runs",
    )
    out = build_graph(deps).invoke(base_state(f))
    assert out["outcome"] == "retried"
