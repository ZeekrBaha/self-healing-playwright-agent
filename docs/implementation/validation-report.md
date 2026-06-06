# Validation Report

Date: 2026-06-06
Status: Draft (not yet run — fill in after implementation)

## Summary
<To be completed after each phase. Record what was validated and the result. This file is a
stub until coding begins; the agent must update it as phases land.>

## Commands Run
- `uv run pytest -q`: Pending
- `uv run ruff check .`: Pending
- `uv run mypy agent nodes sut memory eval`: Pending
- `uv run pytest tests/test_smoke.py`: Pending
- `npx promptfoo eval -c eval/promptfooconfig.yaml`: Pending

## Functional Coverage
- [ ] AC-001 detect_failure snapshot + error class
- [ ] AC-002 triage four-class routing
- [ ] AC-003 ranked heal candidates
- [ ] AC-004 judge approves correct / rejects trap
- [ ] AC-005 apply vs escalate at τ
- [ ] AC-006 memory replay 0 LLM calls
- [ ] AC-007 attempt cap circuit-break
- [ ] AC-008 metrics populate in Langfuse
- [ ] AC-009 CI gate (regression fails / good passes)
- [ ] AC-010 v1→v2 demo recorded

## AI Behavior Coverage
- [ ] Triage prompt regression cases
- [ ] Judge false-heal trap rejected
- [ ] Tool-call failure → escalate
- [ ] Degraded mode (LLM timeout) → escalate, traced
- [ ] Determinism (same input → same verdict)

## CI / Release Gate
- [ ] CI green
- [ ] Promptfoo pass-rate ≥ threshold AND false_heal_rate ≤ threshold
- [ ] Deliberate prompt regression shown to fail CI

## Known Gaps
- <Gap, impact, owner — to be filled in.>

## Final Reviewer Notes
PM:
Developer:
Tester:
Reviewer:
Team Lead:
