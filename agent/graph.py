"""The agent graph (ADR-006): deterministic backbone + a bounded heal loop over 3 tools.

Topology:
    triage ─┬─ regression/data ─► report   (no heal)
            ├─ flake ───────────► retry
            └─ drift ──────────► heal ─┬─ can_apply ─► apply
                                       └─ else ──────► escalate

All side-effecting safety actions (apply/escalate/report) are deterministic nodes gated by
the pure guards — the LLMs only run *inside* triage / propose_candidates / judge_heal.

The heal loop is code-orchestrated (not LLM-tool-routed) for determinism and safety: it calls
the 3 heal tools (check_memory → propose_candidates → judge_heal) and is bounded by
MAX_HEAL_ATTEMPTS. No assistant is bound to more than 3 tools (ADR-006a).

`run_step(selector) -> (step_passed, assertion_held)` is the injected Playwright boundary.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, TypedDict

from langgraph.graph import END, StateGraph

from agent import config
from agent.guards import can_apply, can_propose, should_force_escalate
from agent.llm import agent_complete, judge_complete
from agent.nodes import classify_triage
from agent.state import FailureSnapshot, HealProposal, HealVerdict, TriageVerdict
from memory.store import HealMemoryStore
from tools.apply_fix import ensure_in_test_dir, replace_locator
from tools.judge_heal import judge_heal
from tools.memory_io import check_memory, remember_fix
from tools.propose_candidates import propose_candidates

CompleteFn = Callable[..., dict]
RunStepFn = Callable[[str], tuple[bool, bool]]


class AgentState(TypedDict, total=False):
    test_id: str
    step_id: str
    test_file: str
    test_intent: str
    failure: FailureSnapshot
    triage: TriageVerdict
    proposal: HealProposal
    verdict: HealVerdict
    chosen_selector: Optional[str]
    attempts: int
    outcome: str
    artifact_path: Optional[str]


def _need_run_step(_selector: str) -> tuple[bool, bool]:
    raise NotImplementedError("inject Deps.run_step (Playwright boundary)")


@dataclass
class Deps:
    triage_complete: CompleteFn = agent_complete
    propose_complete: CompleteFn = agent_complete
    judge_complete: CompleteFn = judge_complete
    run_step: RunStepFn = _need_run_step
    store: HealMemoryStore | None = None
    test_dir: Path = field(default_factory=lambda: Path("sut/tests"))
    artifacts_dir: Path = field(default_factory=lambda: Path("runs"))

    def __post_init__(self):
        self.test_dir = Path(self.test_dir)
        self.artifacts_dir = Path(self.artifacts_dir)
        if self.store is None:
            self.store = HealMemoryStore(self.artifacts_dir / "heal_memory.json")


# --- nodes (closures over deps via build_graph) ----------------------------------------


def _triage_node(deps: Deps):
    def node(state: AgentState) -> dict:
        verdict = classify_triage(
            state["failure"], state["test_intent"], complete=deps.triage_complete
        )
        return {"triage": verdict}

    return node


def _heal_node(deps: Deps):
    """check_memory → (propose → judge)* bounded. Sets verdict + chosen_selector on success."""

    def node(state: AgentState) -> dict:
        failure: FailureSnapshot = state["failure"]
        triage: TriageVerdict = state["triage"]
        test_id, step_id = state["test_id"], state["step_id"]
        broken = failure.broken_selector or ""

        # 1) memory first — zero-LLM replay
        fixed = check_memory(deps.store, test_id=test_id, step_id=step_id, broken_selector=broken)
        if fixed:
            sp, ah = deps.run_step(fixed)
            if sp and ah:
                return {
                    "chosen_selector": fixed,
                    "verdict": HealVerdict(
                        approved=True, chosen_selector=fixed, confidence=1.0,
                        reason="memory replay", step_passed=True, assertion_held=True,
                    ),
                    "attempts": 0,
                }
            deps.store.invalidate(_key(test_id, step_id, broken))  # stale, fall through

        # 2) defensive guard, then propose + judge each candidate
        if not can_propose(triage):
            return {"attempts": 0}  # routes to escalate

        proposal = propose_candidates(failure, triage, complete=deps.propose_complete)
        attempts = 0
        last: HealVerdict | None = None
        for cand in proposal.candidates:
            if should_force_escalate(attempts=attempts, max_attempts=config.MAX_HEAL_ATTEMPTS):
                break
            attempts += 1
            sp, ah = deps.run_step(cand.selector)
            verdict = judge_heal(cand, step_passed=sp, assertion_held=ah, complete=deps.judge_complete)
            last = verdict
            if can_apply(verdict, tau=config.TAU):
                return {"proposal": proposal, "verdict": verdict,
                        "chosen_selector": cand.selector, "attempts": attempts}
        return {"proposal": proposal, "verdict": last, "attempts": attempts}

    return node


def _apply_node(deps: Deps):
    def node(state: AgentState) -> dict:
        test_file = Path(state["test_file"])
        ensure_in_test_dir(test_file, deps.test_dir)
        broken = state["failure"].broken_selector or ""
        fixed = state["chosen_selector"]
        patched = replace_locator(test_file.read_text(), broken=broken, fixed=fixed)
        test_file.write_text(patched)
        remember_fix(deps.store, test_id=state["test_id"], step_id=state["step_id"],
                     broken_selector=broken, fixed_selector=fixed)
        return {"outcome": "healed"}

    return node


def _write_artifact(deps: Deps, kind: str, state: AgentState) -> str:
    deps.artifacts_dir.mkdir(parents=True, exist_ok=True)
    path = deps.artifacts_dir / f"{kind}_{state['test_id']}_{state['step_id']}.md"
    triage = state.get("triage")
    verdict = state.get("verdict")
    path.write_text(
        f"# {kind.upper()}: {state['test_id']} / {state['step_id']}\n\n"
        f"- intent: {state.get('test_intent')}\n"
        f"- triage: {triage.category if triage else 'n/a'} "
        f"(conf {triage.confidence if triage else 'n/a'})\n"
        f"- evidence: {triage.evidence if triage else ''}\n"
        f"- verdict: {verdict.reason if verdict else 'no approved heal'}\n"
    )
    return str(path)


def _report_node(deps: Deps):
    def node(state: AgentState) -> dict:
        return {"outcome": "reported", "artifact_path": _write_artifact(deps, "report", state)}

    return node


def _escalate_node(deps: Deps):
    def node(state: AgentState) -> dict:
        return {"outcome": "escalated", "artifact_path": _write_artifact(deps, "escalation", state)}

    return node


def _retry_node(_deps: Deps):
    def node(_state: AgentState) -> dict:
        return {"outcome": "retried"}

    return node


# --- routing ---------------------------------------------------------------------------


def _route_after_triage(state: AgentState) -> str:
    cat = state["triage"].category
    if cat == "drift":
        return "heal"
    if cat == "flake":
        return "retry"
    return "report"  # regression / data


def _route_after_heal(state: AgentState) -> str:
    verdict = state.get("verdict")
    if state.get("chosen_selector") and verdict and can_apply(verdict, tau=config.TAU):
        return "apply"
    return "escalate"


def _key(test_id: str, step_id: str, broken: str) -> str:
    from memory.store import make_key

    return make_key(test_id, step_id, broken)


def build_graph(deps: Deps | None = None):
    deps = deps or Deps()
    g = StateGraph(AgentState)
    g.add_node("triage", _triage_node(deps))
    g.add_node("heal", _heal_node(deps))
    g.add_node("apply", _apply_node(deps))
    g.add_node("escalate", _escalate_node(deps))
    g.add_node("report", _report_node(deps))
    g.add_node("retry", _retry_node(deps))

    g.set_entry_point("triage")
    g.add_conditional_edges("triage", _route_after_triage,
                            {"heal": "heal", "retry": "retry", "report": "report"})
    g.add_conditional_edges("heal", _route_after_heal, {"apply": "apply", "escalate": "escalate"})
    for terminal in ("apply", "escalate", "report", "retry"):
        g.add_edge(terminal, END)
    return g.compile()
