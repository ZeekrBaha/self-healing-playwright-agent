"""Deterministic backbone nodes (ADR-006). LLM calls are injectable for testability.

`classify_triage` is the triage node: one classification call using the failure snapshot
AND the test intent (the intent is what lets it tell drift from a real regression).
"""

from __future__ import annotations

from collections.abc import Callable

from agent.llm import agent_complete
from agent.state import FailureSnapshot, TriageVerdict

CompleteFn = Callable[..., dict]

TRIAGE_SYSTEM = (
    "You are a test-failure triage classifier for a Playwright suite. "
    "Given the failing step, the error class, the captured DOM/accessibility snapshot, and "
    "the test's INTENT, classify why the test failed into exactly one category:\n"
    "  drift      = the element still exists but its selector changed (rename/restructure)\n"
    "  regression = the app behavior is genuinely wrong (the test caught a real bug)\n"
    "  flake      = timing/transient; a retry would likely pass\n"
    "  data       = the underlying data changed, not the UI\n"
    "Return JSON only: {\"category\": <one>, \"confidence\": <0..1>, \"evidence\": <short reason>}."
)


def _triage_prompt(failure: FailureSnapshot, intent: str) -> str:
    return (
        f"TEST INTENT: {intent}\n"
        f"FAILING STEP: {failure.failing_step}\n"
        f"ERROR CLASS: {failure.error_class}\n"
        f"BROKEN SELECTOR: {failure.broken_selector}\n"
        f"DOM AT FAILURE: {failure.dom_html}\n"
        f"A11Y TREE: {failure.a11y_tree}\n"
    )


def classify_triage(
    failure: FailureSnapshot, intent: str, *, complete: CompleteFn = agent_complete
) -> TriageVerdict:
    messages = [
        {"role": "system", "content": TRIAGE_SYSTEM},
        {"role": "user", "content": _triage_prompt(failure, intent)},
    ]
    raw = complete(messages, name="triage")
    return TriageVerdict(**raw)
