"""Safety guards — the project's two non-negotiable invariants as pure functions.

The tool layer (ADR-006) MUST call these before acting; they read typed verdicts, not the
chat, so a hallucinated or out-of-order tool call cannot bypass them.
"""

from __future__ import annotations

from agent.state import HealVerdict, TriageVerdict


def can_propose(triage: TriageVerdict) -> bool:
    """Heal candidates may only be proposed for selector drift.

    Never heal a regression, data change, or flake — that is how a real bug gets masked.
    """
    return triage.category == "drift"


def can_apply(verdict: HealVerdict, *, tau: float) -> bool:
    """A heal may be applied only if the judge approved it, it clears the confidence
    threshold, AND the downstream assertion still holds (false-heal guard).
    """
    return verdict.approved and verdict.confidence >= tau and verdict.assertion_held


def should_force_escalate(*, attempts: int, max_attempts: int) -> bool:
    """Cost guardrail (REQ-009): once heal attempts hit the cap, stop looping and escalate."""
    return attempts >= max_attempts
