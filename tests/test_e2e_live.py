"""Live end-to-end (Phase 8 final validation, automated).

Real browser + real OpenAI (triage/propose) + real DeepSeek (judge) + Langfuse tracing.
A test references the v1 id `#login-button`; the page drifted it to `#signin-button`. The
agent must triage=drift, heal via the stable role/name, and patch the test file.

Run: uv run pytest -m live tests/test_e2e_live.py
"""

import os

import pytest

from agent.graph import Deps, build_graph
from agent.state import FailureSnapshot
from memory.store import HealMemoryStore
from sut.runner import LiveRunner, fixture_url


@pytest.mark.live
def test_agent_heals_real_drift_on_the_fixture(tmp_path):
    from dotenv import load_dotenv

    load_dotenv()
    if not (os.environ.get("OPENAI_API_KEY") and os.environ.get("DEEPSEEK_API_KEY")):
        pytest.skip("needs OPENAI_API_KEY + DEEPSEEK_API_KEY")

    test_dir = tmp_path / "sut" / "tests"
    test_dir.mkdir(parents=True)
    test_file = test_dir / "login_test.py"
    test_file.write_text('page.locator("#login-button").click()\n')

    with LiveRunner(fixture_url()) as runner:
        failure: FailureSnapshot = runner.capture(
            broken_selector="#login-button", failing_step="click the login button"
        )
        deps = Deps(
            run_step=runner.run_step,
            store=HealMemoryStore(tmp_path / "mem.json"),
            test_dir=test_dir,
            artifacts_dir=tmp_path / "runs",
        )
        state = {
            "test_id": "login_test",
            "step_id": "click_login",
            "test_file": str(test_file),
            "test_intent": "user clicks login and sees the welcome message",
            "failure": failure,
            "attempts": 0,
        }
        out = build_graph(deps).invoke(state)

    assert out["outcome"] == "healed", f"expected healed, got {out['outcome']}"
    patched = test_file.read_text()
    assert "#login-button" not in patched  # the broken selector is gone
