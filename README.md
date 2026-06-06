# Self-Healing Playwright Agent — Triage → Heal → Judge

A [LangGraph](https://github.com/langchain-ai/langgraph) agent that, when a Playwright test
fails, decides **why** it failed (selector drift / genuine regression / flake / data change),
heals **only** true selector drift, and validates every heal with an independent LLM judge
before applying it.

> **The core principle that makes this QA and not a footgun:**
> the agent must never make a test green by masking a real regression.
> A first-class triage step and a code-enforced *false-heal guard* exist to guarantee that.

Verified end-to-end with real models: a drifted login button (`#login-button` →
`#signin-button`) is triaged as drift, healed via its stable accessibility name, and the test
file is patched `#login-button` → `button[aria-label='Login']` — **OUTCOME: HEALED** in ~6s.

---

## 1. Mental model — two planes

- **Runtime plane** (LangGraph, traced in Langfuse): a deterministic backbone
  (`triage → {heal | report | retry}`) plus one scoped heal step. Every LLM/tool call is traced.
- **Eval plane** (Promptfoo, in CI): fixtures gate the triage/judge prompts on every change.

```
detect_failure ─► triage ─┬─ regression / data ─► report      (NEVER heal)
                          ├─ flake ─────────────► retry
                          └─ drift ─► heal ─┬─ approved (≥τ, assertion held) ─► apply_fix
                                            └─ else ────────────────────────► escalate (HITL)
```

## 2. Where the SUT lives

The agent heals tests for a **system under test**. Two options (see `PLAN.md`):
- **A (default, in this repo):** a reproducible drifted HTML fixture
  (`sut/fixtures/login_v2.html`) + a DOM-mutation harness (`sut/profiles.py`) that injects
  controlled drift. Deterministic, no network, feeds the eval plane.
- **B (portfolio polish):** fork Conduit/RealWorld and version it v1→v2 for an organic
  "the frontend team refactored" demo.

## 3. What the agent does

1. **detect** — capture the failing step, error class (selector-resolution vs assertion),
   and a DOM + accessibility snapshot (`sut/capture.py`).
2. **triage** — classify *why* it failed using the snapshot **and the test's intent**
   (`agent/nodes.py`). This is the centerpiece.
3. **heal** (drift only) — `check_memory` → `propose_candidates` (≥2 ranked, role/name + testid
   first) → `judge_heal`. Bounded by an attempt cap.
4. **judge** — re-run the step **and** re-check the downstream assertion; approve only if both
   hold (the false-heal guard).
5. **apply or escalate** — high confidence → patch the locator (single-match, test-dir only);
   low confidence → escalate to a human (PR / artifact).

## 4. The two invariants (enforced in code, not prompts)

| Invariant | Where | Test |
|---|---|---|
| Never heal a regression | `agent/guards.can_propose` + graph topology | `tests/test_guards.py`, `tests/test_graph.py` |
| Never apply a heal that hollows the assertion | `agent/guards.can_apply` + `tools/judge_heal` override | `tests/test_judge.py`, `tests/test_graph.py` |

The LLM never *chooses* to apply or skip the judge — the graph edges + pure guards do. A
0.99-confidence "approve" is rejected if `assertion_held` is false.

*(Langfuse trace of a real heal run — `triage` / `propose_candidates` / `judge_heal` spans:
`docs/assets/langfuse-flow.png`.)*

## 5. The metric stack

- **Deterministic:** expected selector present; valid JSON; cost ceiling per call.
- **Model-graded (`llm-rubric`):** rationale quality of the triage evidence.
- **Runtime scores (Langfuse):** `heal_success_rate`, `false_heal_rate`,
  `mean_attempts_per_heal`, `cost_per_heal`, `auto_vs_escalated_ratio`.

## 6. Findings (this build)

| Check | Result |
|---|---|
| Unit + integration suite (`pytest`) | **65 passed** (live deselected) |
| Live triage (OpenAI) | ✓ valid category |
| Live propose (OpenAI) | ✓ ≥2 candidates |
| Live judge (DeepSeek) | ✓ verdict |
| Live end-to-end heal (`tests/test_e2e_live.py`) | ✓ **HEALED**, file patched, ~6.4s |
| Promptfoo triage gate (`eval/`) | ✓ **4/4 pass** |

Demo run (`scripts/demo.py`): triage **drift** (conf 0.9) → judge approved (step ✓, assertion ✓)
→ chosen `button[aria-label='Login']` → **HEALED** in 1 attempt.

## 7. Models (independent judge)

- **Agent** (triage + heal): OpenAI `gpt-4o-mini`
- **Judge**: DeepSeek `deepseek-chat` — a *different vendor* than the agent, to reduce
  self-preference bias on the false-heal call.
- `temperature=0`, pinned ids (`agent/config.py`) for stable eval thresholds.

## 8. How to run

```bash
uv venv && uv pip install -e ".[runtime]" pytest
uv run playwright install chromium

uv run pytest                    # 65 green, live deselected (free, deterministic)
cp .env.example .env             # then add keys (never committed)
uv run python scripts/smoke_providers.py    # OpenAI + DeepSeek + Langfuse connectivity

uv run pytest -m live            # the live tests (real API calls)
uv run python scripts/demo.py    # run-once heal demo (real browser + models + Langfuse)

# eval gate (needs node >=22.22, OPENAI_API_KEY)
npx -y promptfoo@latest eval -c eval/promptfooconfig.yaml
```

## 9. Keys / env

`.env` (gitignored — only `.env.example` is committed):
`OPENAI_API_KEY`, `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL`, `LANGFUSE_PUBLIC_KEY`,
`LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`.

## 10. Repo map

```
agent/      state.py (typed verdicts) · guards.py (invariants) · routing.py · config.py
            llm.py (traced OpenAI/DeepSeek boundary) · nodes.py (triage) · graph.py (the graph)
tools/      memory_io · propose_candidates · judge_heal · apply_fix   (the 3 heal tools + patch core)
memory/     store.py (keyed JSON, zero-LLM replay)
sut/        capture.py · profiles.py (DOM mutations) · runner.py (live Playwright) · fixtures/
eval/       promptfooconfig.yaml · triage_prompt.json     (Phase 7 gate)
scripts/    smoke_providers.py · demo.py
tests/      11 test files (unit + integration + live)
docs/       implementation/ (research→validation) · prompts/ (role prompts)
```

## 11. Why this stack

- **LangGraph** — explicit, inspectable control flow; deterministic safety edges.
- **Langfuse** — every call traced with cost/latency/scores; the evidence layer.
- **Promptfoo** — prompt regression gate in CI before a healer change ships.
- **Independent judge (DeepSeek)** — credibility for the false-heal guard.

## 12. Architecture decision: ≤3 tools per assistant (ADR-006a)

A single ReAct agent bound to ~10 tools picks badly. So the runtime is a deterministic
backbone + one scoped heal step over exactly 3 tools, with all side-effecting safety actions
as deterministic, guard-gated nodes. See `docs/implementation/architecture.md`.

## 13. Limitations / next steps

- SUT Option B (RealWorld v1→v2) is documented but not deployed here (fixture covers the loop).
- Langfuse metric dashboards + the trace screenshot are a manual capture step (no Langfuse MCP).
- Escalation currently writes an artifact; the GitHub-PR `interrupt()` path is specced.

## License

MIT
