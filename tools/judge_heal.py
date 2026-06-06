"""Heal tool #3: judge_heal — approve a heal only if the step passes AND the downstream
assertion still holds (false-heal guard).

The LLM (DeepSeek, independent vendor) reasons about whether the heal is semantically right;
but `assertion_held` / `step_passed` are OBSERVED facts from re-running, and the code makes the
final call: approved = llm_approved AND step_passed AND assertion_held. No LLM 'approve' can
overturn a hollow assertion.
"""

from __future__ import annotations

from collections.abc import Callable

from agent.llm import judge_complete
from agent.state import HealCandidate, HealVerdict

CompleteFn = Callable[..., dict]

JUDGE_SYSTEM = (
    "You judge a proposed Playwright selector heal. You are told whether re-running the step "
    "with the candidate made the step pass and whether the original downstream assertion still "
    "held. Approve ONLY if the heal restores the intended behavior — a step that passes while "
    "the assertion is hollow is a FALSE HEAL and must be rejected. "
    "Return JSON only: {\"approved\": bool, \"confidence\": 0..1, \"reason\": short}."
)


def _prompt(candidate: HealCandidate, step_passed: bool, assertion_held: bool) -> str:
    return (
        f"CANDIDATE SELECTOR: {candidate.selector} (signal={candidate.signal})\n"
        f"OBSERVED step_passed: {step_passed}\n"
        f"OBSERVED assertion_held: {assertion_held}\n"
    )


def judge_heal(
    candidate: HealCandidate,
    *,
    step_passed: bool,
    assertion_held: bool,
    complete: CompleteFn = judge_complete,
) -> HealVerdict:
    messages = [
        {"role": "system", "content": JUDGE_SYSTEM},
        {"role": "user", "content": _prompt(candidate, step_passed, assertion_held)},
    ]
    raw = complete(messages, name="judge_heal")
    # Code has the final say: observed facts gate the LLM's opinion (false-heal guard).
    approved = bool(raw.get("approved")) and step_passed and assertion_held
    return HealVerdict(
        approved=approved,
        chosen_selector=candidate.selector,
        confidence=float(raw.get("confidence", 0.0)),
        reason=str(raw.get("reason", "")),
        step_passed=step_passed,
        assertion_held=assertion_held,
    )
