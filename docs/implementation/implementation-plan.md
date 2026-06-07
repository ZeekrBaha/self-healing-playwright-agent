# Self-Healing Playwright Agent — Implementation Plan

Date: 2026-06-06
Status: Draft

## Goal

Ship the agent from `PLAN.md`: detect failure → triage → heal drift only → judge → apply
or escalate; with heal memory, Langfuse metrics, and a Promptfoo CI gate. Build SUT Option A
(harness) first; add Option B (RealWorld v1→v2) for the demo.

## Source Documents

- `docs/implementation/research.md`
- `docs/implementation/requirements.md`
- `docs/implementation/design.md`
- `docs/implementation/architecture.md`
- `PLAN.md` (phase narrative + acceptance per phase)

Tasks below map 1:1 onto PLAN.md Phases 0–8. One phase at a time; do not start the next until
its acceptance criteria pass.

## Task Checklist

### Task 0 — Setup & SUT (PLAN Phase 0)
Owner role: Developer

Files likely touched: `agent/config.py`, `agent/llm.py`, `.env.example`, `pyproject.toml`,
`sut/tests/`, `README.md`

Steps:
- [ ] Scaffold `agent/ nodes/ sut/ memory/ eval/ tests/` per architecture.
- [ ] Install deps (`uv`): langgraph, playwright, langfuse, pydantic, openai, pytest; `playwright install chromium`.
- [ ] `agent/llm.py`: OpenAI client (triage/heal) + DeepSeek via `DEEPSEEK_BASE_URL` (judge), Langfuse-wrapped, `temperature=0`, pinned model ids.
- [ ] Smoke test: log into saucedemo green; one traced "hello" LLM call visible in Langfuse.

Acceptance: AC-008 (partial — tracing live). Smoke test passes; one trace in Langfuse.
Tests: Unit (config loads env); E2E (saucedemo login smoke); AI eval (n/a).
Validation: `pytest tests/test_smoke.py`, manual Langfuse trace check.
Risks/rollback: SUT unreachable → pin flow / switch to the-internet.

### Task 1 — DOM-mutation harness & detect_failure (PLAN Phase 1)
Owner role: Developer

Files: `sut/harness.py`, `sut/profiles.py`, `sut/tests/*`, `nodes/detect_failure.py`

Steps:
- [ ] Harness via `addInitScript`: rename/remove `data-testid`, swap id↔class, wrap nodes, alter ARIA roles.
- [ ] Mutation profiles: `testid-rename`, `role-change`, `text-change`, `structural-wrap`.
- [ ] 4–6 baseline tests green on un-mutated SUT, each carrying a one-line **intent** string.
- [ ] `detect_failure`: capture failing step, error class (selector_resolution vs assertion), DOM + a11y snapshot.
- [ ] Trace every node run.

Acceptance: AC-001. Tests: Unit (snapshot fields, error-class split); Integration (each profile reds the right tests).
Validation: `pytest tests/test_detect.py`, run each profile.
Risks/rollback: snapshot too large → trim to relevant subtree.

### Task 1b — Graph backbone + heal_agent (ADR-006 / ADR-006a)
Owner role: Developer

Files: `agent/graph.py`, `agent/heal_agent.py`, `agent/nodes.py`, `agent/routing.py`, `agent/state.py` (add `messages`), `agent/config.py`, `tests/test_loop.py`

Steps:
- [ ] `AgentState` gains `messages: Annotated[list, add_messages]` (used by heal_agent only).
- [ ] Deterministic backbone nodes in `agent/nodes.py`: `detect_failure`, `triage` (1 LLM call),
      `apply_fix`, `escalate`, `report`, `retry`. Side-effecting nodes are NOT LLM-chosen.
- [ ] `heal_agent`: ReAct loop bound to **exactly 3 tools** (`check_memory`,
      `propose_candidates`, `judge_heal`); loops until an approved verdict or `MAX_HEAL_ATTEMPTS`.
- [ ] `graph.py` wiring: detect → triage → {drift→heal_agent, regression/data→report,
      flake→retry→detect}; heal_agent → {can_apply→apply_fix, else→escalate}.
- [ ] Backbone routing uses `guards.can_propose`/`can_apply` — the LLM never routes the
      safety actions. `recursion_limit` backstop so the heal loop always terminates.
- [ ] **No assistant bound to >3 tools (ADR-006a).** If heal needs a 4th tool, split it.

Acceptance: graph runs end-to-end on one drift case (heal) and one regression case (report);
the apply edge is unreachable without an approving verdict (adversarial test). Tests: Unit
(route fns — done); Integration (loop terminates; regression never reaches heal_agent).
Validation: `pytest tests/test_loop.py`.
Risks/rollback: runaway loop → recursion_limit backstop; guard bypass → guard unit tests (done).

> Note: Tasks 2–5 below build the **heal_agent tools + their guards** (`tools/`) and the
> deterministic backbone nodes (`agent/nodes.py`). Acceptance criteria unchanged.

### Task 2 — Triage node (PLAN Phase 2) — CENTERPIECE
Owner role: Developer + Tester

Files: `nodes/triage.py`, `agent/state.py` (TriageVerdict), `agent/graph.py` (routing), `tests/test_triage.py`

Steps:
- [ ] `TriageVerdict` Pydantic model (category/confidence/evidence).
- [ ] Triage uses snapshot **+ test intent**; classify drift/regression/flake/data.
- [ ] Conditional routing: drift→heal, regression/data→report, flake→retry.
- [ ] Triage-confidence floor: below floor → escalate (don't gamble a regression into heal).
- [ ] Four-class negative suite: genuine bug, flake, data change, pure drift — assert correct route each.
- [ ] Score triage decisions in Langfuse.

Acceptance: AC-002. Tests: Unit (model); Integration (four-class routing); AI eval (triage accuracy on fixtures).
Validation: `pytest tests/test_triage.py`.
Risks/rollback: misclassification → strengthen intent prompt, add evidence requirement.

### Task 3 — Healer node (PLAN Phase 3)
Owner role: Developer

Files: `nodes/heal_candidates.py`, `agent/state.py` (HealProposal/HealCandidate), `tests/test_heal.py`

Steps:
- [ ] Gather signals: a11y role+name, visible text, nearby `data-testid`, structural position.
- [ ] Rank candidates; prefer role/name + testid over CSS/XPath; ≥2 candidates with rationale.
- [ ] Emit `HealProposal`.

Acceptance: AC-003. Tests: Unit (ranking, ≥2); Integration (per profile, strongest first).
Validation: `pytest tests/test_heal.py`.
Risks/rollback: weak candidates → add signal sources.

### Task 4 — Judge, verdict & routing (PLAN Phase 4)
Owner role: Developer + Reviewer

Files: `nodes/judge.py`, `nodes/apply_fix.py`, `nodes/escalate.py`, `agent/state.py` (HealVerdict), `agent/config.py` (τ), `tests/test_judge.py`, `tests/test_apply.py`

Steps:
- [ ] `HealVerdict` (approved/chosen_selector/confidence/reason + step_passed/assertion_held).
- [ ] Judge re-runs the step AND re-checks the downstream assertion (false-heal guard).
- [ ] False-heal **trap** fixture: step green, assertion hollow → assert rejection.
- [ ] Conditional edge: ≥τ → `apply_fix` (string-replace locator, single-match dry-run guard, reversible); <τ → `escalate`.
- [ ] `escalate` via `interrupt()` → PR / `escalations/<id>.md`, body links Langfuse trace + before/after a11y diff.
- [ ] Tune τ against Phase 7 fixtures (revisit after Task 7).

Acceptance: AC-004, AC-005. Tests: Unit (verdict, apply single-match guard); Integration (approve→apply, reject→escalate); AI eval (trap rejected).
Validation: `pytest tests/test_judge.py tests/test_apply.py`.
Risks/rollback: τ wrong → re-tune on fixtures; apply mismatch → abort+escalate (built in).

### Task 5 — Heal memory + cost guardrail (PLAN Phase 5)
Owner role: Developer

Files: `memory/store.py`, `nodes/check_memory.py`, `agent/graph.py`, `agent/config.py`, `tests/test_memory.py`

Steps:
- [ ] Keyed JSON store behind interface; `broken_selector→fixed_selector` keyed by test+step.
- [ ] `check_memory` before heal; replay known fix with **0 LLM calls**; invalidate on replay failure.
- [ ] Hard cap on LLM heal attempts/run; circuit-break to escalate.

Acceptance: AC-006, AC-007. Tests: Unit (get/put/invalidate); Integration (second run = 0 LLM calls; cap triggers escalate).
Validation: `pytest tests/test_memory.py`.
Risks/rollback: stale entry → invalidation path covers it.

### Task 6 — Metrics & dashboards (PLAN Phase 6)
Owner role: Developer

Files: `agent/llm.py`/`agent/graph.py` (score emission), `README.md`

Steps:
- [ ] Emit scores: heal_success_rate, false_heal_rate, mean_attempts_per_heal, cost_per_heal (+p99), auto_vs_escalated_ratio.
- [ ] Saved Langfuse view per metric; capture before/after screenshots for README.

Acceptance: AC-008. Tests: Integration (run batch populates every metric).
Validation: run batch script; manual Langfuse verification + screenshots.
Risks/rollback: missing scores → assert score emission in integration test.

### Task 7 — Eval plane (Promptfoo + CI) (PLAN Phase 7)
Owner role: Developer + Tester

Files: `eval/promptfooconfig.yaml`, `eval/fixtures/*`, `eval/gen_fixtures.py`, `.github/workflows/eval-gate.yml`

Steps:
- [ ] Fixtures from mutation profiles + replayed Langfuse traces + v1→v2 a11y diff (`gen_fixtures.py`).
- [ ] `promptfooconfig.yaml`: deterministic (expected selector present) + `llm-rubric` (rationale quality) assertions.
- [ ] Thresholds for pass-rate and **false_heal_rate**.
- [ ] GitHub Actions: run Promptfoo on healer/judge prompt changes; fail below threshold.
- [ ] (Optional) DeepEval pytest gate for the same suite.
- [ ] Re-tune τ (Task 4) against this fixture set.

Acceptance: AC-009. Tests: AI eval (prompt-regression fails CI; good change passes).
Validation: `npx promptfoo eval`; CI dry-run on a deliberate regression branch.
Risks/rollback: flaky grader → confirm temperature=0/pinned ids (ADR-003).

### Task 8 — SUT Option B + portfolio polish (PLAN Phase 8)
Owner role: Developer

Files: `sut/realworld/*`, `README.md`, demo recording

Steps:
- [ ] Fork RealWorld/Conduit; v1 baseline green; v2 refactor (testid renames, DOM wraps, role/id↔class changes) + **spectrum** of planted issues (genuine bug, flake, data change, pure drift).
- [ ] Deploy v1/v2 (docker compose ports or feature flag).
- [ ] README: two-plane diagram, "never mask a regression" decision, metrics table (real numbers), before/after screenshots; ADR note on triage + false-heal guard.
- [ ] Record headline demo: v1→v2, drift heals + applies, planted regression reports.

Acceptance: AC-010. Tests: E2E (v2 reds → heal drift, report regression).
Validation: run suite vs v2; capture recording.
Risks/rollback: two-deploy ops → fall back to feature-flag single deploy.

## Role Review Notes

PM: User problem (heal drift, never mask a bug) is clear and prioritized; Phase 2 + 4 carry
the value. Approved.

Developer: Architecture implementable on LangGraph + Playwright-Python; main open call is
`apply_fix` mechanism (ADR-002 — start with guarded string replace).

Junior Developer: Tasks are self-contained with explicit files and acceptance; the "must
reuse `agent/llm.py`" and "test files only for apply_fix" rules are stated so no hidden context.

Tester: Acceptance criteria all map to commands. The four-class triage suite and the
false-heal trap fixture must be built explicitly (Tasks 2, 4), not assumed.

Reviewer: Determinism (ADR-003) and the apply_fix allow-path guard are the risk hotspots;
verify no untraced LLM calls and no silent commits.

Team Lead: Sequencing matches risk. Gate: do not advance past Task 2 or Task 4 until their
negative tests pass. CI gate (Task 7) must enforce false_heal_rate, not just pass-rate.

## Approval Gate
- [ ] Research approved
- [ ] Design approved
- [ ] Plan approved
- [ ] Coding may begin
