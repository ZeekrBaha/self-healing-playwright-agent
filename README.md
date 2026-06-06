# Self-Healing Playwright Agent — Triage → Heal → Judge

> **Status: work in progress.** Core safety logic is built and test-driven (30 tests green);
> the LangGraph runtime, SUT, and eval plane are next. The full README (architecture diagram,
> metrics, demo) is the final deliverable — see [`PLAN.md`](PLAN.md) Phase 8.

A [LangGraph](https://github.com/langchain-ai/langgraph) agent that, when a Playwright test
fails, decides **why** it failed (selector drift / genuine regression / flake / data change),
heals **only** true selector drift, and validates every heal with an LLM judge before applying
it.

**The core principle:** the agent must never make a test green by masking a real regression.
A dedicated triage step and a false-heal guard exist to enforce exactly that.

## Two planes

- **Runtime** — a Guarded ReAct loop (one assistant ↔ tools) traced in **Langfuse**. Safety
  invariants live as code guards inside the tools, not in the prompt, so the LLM cannot route
  around them.
- **Eval** — **Promptfoo** fixtures gated in CI on any healer/judge prompt change.

## Stack

LangGraph · Playwright · Pydantic · OpenAI (triage/heal) · DeepSeek (independent judge) ·
Langfuse (observability) · Promptfoo (eval) · pytest.

## Built so far (test-driven)

| Module | Guarantees |
|---|---|
| `agent/state.py` | typed verdicts; ≥2 heal candidates; bounded confidence |
| `agent/guards.py` | never heal a regression; never apply a hollow/low-confidence heal; per-run attempt cap |
| `memory/store.py` | zero-LLM replay of known fixes |
| `tools/apply_fix.py` | single-match patch; writes only under the SUT test dir |
| `agent/routing.py` | the assistant-loop conditional edge |

## Develop

```bash
uv venv && uv pip install -e . --group dev
uv run pytest                       # 30 green
cp .env.example .env                # then fill in keys (never committed)
uv run python scripts/smoke_providers.py   # verifies OpenAI + DeepSeek + Langfuse
```

See [`PLAN.md`](PLAN.md) for the full phased plan and [`docs/implementation/`](docs/implementation)
for research, requirements, design, architecture, and the implementation plan.

## License

MIT
