"""Heal tool #2: propose_candidates — multi-signal ranked selectors -> HealProposal.

Defensive guard: refuses anything but drift before spending an LLM call (the graph already
routes only drift here, but the tool double-checks against typed state).
"""

from __future__ import annotations

from collections.abc import Callable

from agent.guards import can_propose
from agent.llm import agent_complete
from agent.state import FailureSnapshot, HealProposal, TriageVerdict

CompleteFn = Callable[..., dict]


class NotDriftError(ValueError):
    """Refused: heal candidates may only be proposed for selector drift."""


PROPOSE_SYSTEM = (
    "You repair a broken Playwright selector. The element still exists; only its selector "
    "drifted. From the DOM and accessibility snapshot, propose at least TWO ranked candidate "
    "selectors, strongest first. Prefer role+accessible-name and nearby data-testid over "
    "brittle CSS/XPath. Return JSON only: {\"candidates\": [{\"selector\":..., "
    "\"signal\": one of role_name|text|nearby_testid|structural, \"rank\": int, "
    "\"rationale\": short}]}."
)


def _prompt(failure: FailureSnapshot) -> str:
    return (
        f"BROKEN SELECTOR: {failure.broken_selector}\n"
        f"FAILING STEP: {failure.failing_step}\n"
        f"DOM AT FAILURE: {failure.dom_html}\n"
        f"A11Y TREE (role + accessible name): {failure.a11y_tree}\n"
    )


def propose_candidates(
    failure: FailureSnapshot, triage: TriageVerdict, *, complete: CompleteFn = agent_complete
) -> HealProposal:
    if not can_propose(triage):
        raise NotDriftError(f"cannot heal triage category {triage.category!r}")
    messages = [
        {"role": "system", "content": PROPOSE_SYSTEM},
        {"role": "user", "content": _prompt(failure)},
    ]
    raw = complete(messages, name="propose_candidates")
    return HealProposal(**raw)
