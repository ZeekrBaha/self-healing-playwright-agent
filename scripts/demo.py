"""Run-once demo / final validation (Phase 8).

Real browser + OpenAI (triage/propose) + DeepSeek (judge) + Langfuse tracing. Heals a real
selector drift on the bundled fixture and patches a test file. Prints the decision trail.

Run: uv run python scripts/demo.py
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from agent.graph import Deps, build_graph  # noqa: E402
from memory.store import HealMemoryStore  # noqa: E402
from sut.runner import LiveRunner, fixture_url  # noqa: E402


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="heal_demo_"))
    test_dir = tmp / "sut" / "tests"
    test_dir.mkdir(parents=True)
    test_file = test_dir / "login_test.py"
    original = 'page.locator("#login-button").click()\n'
    test_file.write_text(original)

    with LiveRunner(fixture_url()) as runner:
        failure = runner.capture(broken_selector="#login-button", failing_step="click the login button")
        deps = Deps(run_step=runner.run_step, store=HealMemoryStore(tmp / "mem.json"),
                    test_dir=test_dir, artifacts_dir=tmp / "runs")
        state = {
            "test_id": "login_test", "step_id": "click_login", "test_file": str(test_file),
            "test_intent": "user clicks login and sees the welcome message",
            "failure": failure, "attempts": 0,
        }
        out = build_graph(deps).invoke(state)

    print("\n=== Self-Healing Playwright Agent — demo run ===")
    print(f"  error class   : {failure.error_class}")
    print(f"  triage        : {out['triage'].category} (conf {out['triage'].confidence}) — {out['triage'].evidence}")
    if out.get("verdict"):
        v = out["verdict"]
        print(f"  judge         : approved={v.approved} conf={v.confidence} step={v.step_passed} assertion={v.assertion_held}")
    print(f"  chosen selector: {out.get('chosen_selector')}")
    print(f"  OUTCOME       : {out['outcome'].upper()}")
    print(f"  attempts      : {out.get('attempts')}")
    print("\n  test file BEFORE: " + original.strip())
    print("  test file AFTER : " + test_file.read_text().strip())
    print("\n  Langfuse: traces 'triage' / 'propose_candidates' / 'judge_heal' under your project.")


if __name__ == "__main__":
    main()
