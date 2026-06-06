# Validation Plan

Date: 2026-06-06
Status: Draft

Defines the checks **before** coding. Nothing is "done" from a clean build alone — runtime
behavior (real graph runs, real traces, real heals) is the bar.

## Commands (stack)

- Typecheck: `uv run mypy agent nodes sut memory eval` (or `pyright`)
- Lint: `uv run ruff check .`
- Format: `uv run ruff format --check .`
- Unit + integration tests: `uv run pytest -q`
- Single suites: `uv run pytest tests/test_triage.py`, `tests/test_judge.py`, `tests/test_memory.py`, ...
- SUT smoke: `uv run pytest tests/test_smoke.py`
- Browser deps: `playwright install chromium` (one-time)
- Eval plane: `npx promptfoo eval -c eval/promptfooconfig.yaml`
- CI: `.github/workflows/eval-gate.yml` runs pytest + promptfoo on prompt changes.

## Functional coverage (map to AC)

- [ ] AC-001 detect_failure captures snapshot + correct error class per profile.
- [ ] AC-002 triage routes drift→heal, regression→report, flake→retry (four-class suite).
- [ ] AC-003 healer returns ≥2 ranked candidates, strongest first, per profile.
- [ ] AC-004 judge approves a correct heal; rejects the false-heal trap.
- [ ] AC-005 ≥τ auto-applies + patches test file; <τ opens PR / writes artifact (no patch).
- [ ] AC-006 second run of a known break uses 0 LLM calls.
- [ ] AC-007 heal-attempt cap circuit-breaks to escalate.
- [ ] AC-008 every REQ-011 metric populates in Langfuse over a batch.
- [ ] AC-009 prompt regression fails CI; good change passes; false_heal_rate enforced.
- [ ] AC-010 v1→v2 demo: drift heals, planted regression reports; recorded.

## AI behavior coverage

- [ ] Triage prompt regression cases (drift vs regression boundary).
- [ ] Judge false-heal trap (step green / assertion hollow) → rejected.
- [ ] Tool-call failure: snapshot capture fails → escalate with diagnostic.
- [ ] Degraded mode: LLM timeout → bounded retry → escalate, traced.
- [ ] Determinism: same input → same verdict (temperature=0, pinned ids).
- [ ] Memory replay failure → invalidate → fresh heal (no stale-fix loop).

## Anti-slop / safety gate (project-specific)

This is a backend agent, so the visual anti-slop gate is N/A. The equivalent safety gate:

- [ ] No untraced LLM/tool calls (grep + Langfuse spot-check).
- [ ] `apply_fix` cannot write outside the SUT test dir (unit test the guard).
- [ ] No secrets committed (`.env` ignored; only `.env.example` present).
- [ ] Verdicts are Pydantic models, never free-form strings (type-checked).
- [ ] Escalation never silently commits to app source (PR/artifact only).
- [ ] README metrics are real measured numbers, not placeholders.

## CI / release gate

- [ ] CI green (pytest + promptfoo).
- [ ] Promptfoo pass-rate ≥ threshold AND false_heal_rate ≤ threshold.
- [ ] A deliberate prompt-regression branch is shown to fail CI (negative proof).

## Sign-off

- Do not mark a phase complete from compile/build success; require the phase's AC commands to
  pass and (where relevant) a real Langfuse trace.
- Final completion requires `validation-report.md` filled with commands run, results, skips,
  and unresolved risks.
