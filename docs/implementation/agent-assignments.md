# Agent Assignments

Date: 2026-06-06
Status: Draft

Maps the role prompts in `docs/prompts/` to the tasks in `implementation-plan.md`. Run one
phase at a time; the Team Lead gates advancement on each phase's acceptance criteria.

## Roles

| Role | Prompt | Responsibility |
|------|--------|----------------|
| Team Lead | `docs/prompts/team-lead.md` | Sequences phases, enforces acceptance gates, owns CI/release gate, never lets a phase advance with failing negative tests. |
| Developer | `docs/prompts/developer.md` | Builds nodes, graph wiring, harness, memory, eval plane. Owns ADR decisions in code. |
| Junior Developer | `docs/prompts/junior-developer.md` | Well-scoped mechanical tasks: mutation profiles, baseline tests + intent strings, fixture wiring. |
| Tester | `docs/prompts/tester.md` | Builds the four-class triage suite, the false-heal trap fixture, and verifies every AC by command. |
| Reviewer | `docs/prompts/reviewer.md` | Guards determinism, the apply_fix allow-path, no untraced LLM calls, no silent commits, spec drift. |

## Task → role map

| Task (PLAN phase) | Primary | Support |
|---|---|---|
| 0 Setup & SUT | Developer | Reviewer (env/secrets) |
| 1 Harness + detect_failure | Developer | Junior (profiles, baseline tests) |
| 2 Triage (centerpiece) | Developer | Tester (four-class suite), Reviewer |
| 3 Healer | Developer | — |
| 4 Judge + apply/escalate | Developer | Tester (trap fixture), Reviewer (apply guard) |
| 5 Memory + cost guardrail | Developer | Reviewer (replay correctness) |
| 6 Metrics | Developer | Tester (batch populates metrics) |
| 7 Eval plane + CI | Developer | Tester (regression branch), Team Lead (gate thresholds) |
| 8 SUT Option B + polish | Developer | Junior (v2 refactor), Team Lead (demo signoff) |

## Hard gates (Team Lead enforces)

1. **No advance past Task 2** until the four-class triage suite passes (a genuine bug must
   route to report, never heal).
2. **No advance past Task 4** until the false-heal trap fixture is rejected by the judge.
3. **Task 7 CI must enforce `false_heal_rate`**, not only pass-rate.
4. **No untraced LLM/tool calls** at any phase from Task 1 onward.
5. **`apply_fix` writes only under the SUT test dir** — verified before merge.
