# Architecture

Date: 2026-06-06
Status: Draft

## Current Architecture

- Repository facts: greenfield. Only `PLAN.md` exists at design time. No code, no CI yet.
- Important existing patterns: none. The conventions defined here become the baseline.

## Proposed Architecture

### Module layout

```text
self-healing-playwright-agent/
  agent/
    graph.py            # LangGraph wiring: deterministic backbone + heal_agent loop (ADR-006)
    heal_agent.py       # the ONE assistant: ReAct loop bound to exactly 3 heal tools
    nodes.py            # deterministic nodes: detect_failure, triage, apply_fix, escalate, report, retry
    routing.py          # backbone edges + heal-loop route (guards decide)
    guards.py           # can_propose / can_apply / should_force_escalate (pure)
    state.py            # AgentState (messages + typed artifacts) + Pydantic models
    config.py           # model ids, τ thresholds, attempt/recursion caps, env loading
    llm.py              # traced OpenAI/DeepSeek client wrapper (Langfuse), temperature=0
  tools/                # the 3 heal_agent tools (guards live here) + apply_fix core
    memory_io.py        # check_memory (replay known fix, 0 LLM) — tool 1
    propose_candidates.py # GUARD: drift only -> HealProposal (>=2 ranked) — tool 2
    judge_heal.py       # re-run step + re-check assertion -> HealVerdict — tool 3
    apply_fix.py        # core: single-match replace + test-dir guard (used by the apply node)
  sut/
    capture.py          # DOM/a11y/error-class snapshot (used by detect_failure node)
    harness.py          # Option A: addInitScript DOM-mutation injector
    profiles.py         # mutation profiles: testid-rename/role-change/text-change/structural-wrap
    realworld/          # Option B: fork pointers, v1/v2 deploy notes, a11y-diff fixture gen
    tests/              # baseline Playwright tests (green on un-mutated SUT) + intent strings
  memory/
    store.py            # keyed JSON store (SQLite/mem0 swappable behind interface)
  eval/
    promptfooconfig.yaml
    fixtures/           # snapshot->expected category/selector (mutation + replayed traces + v1->v2 diff)
    gen_fixtures.py     # build fixtures from v1->v2 a11y-tree diff
  tests/                # pytest: node unit tests, graph integration, negative suites
  runs/ reports/ escalations/   # per-run artifacts (git-ignored except samples)
  .github/workflows/eval-gate.yml
  .env.example
  PLAN.md
  TASK.md
```

### Runtime topology — deterministic backbone + small stage agent (ADR-006)

**Tool-count rule (ADR-006a): no assistant node sees more than 3 tools.** A single ReAct
assistant bound to ~10 tools picks badly. So the runtime is a small graph: a **deterministic
backbone** for the linear, safety-critical steps, and **one scoped ReAct sub-agent** for the
only step that genuinely needs iteration (healing). Side-effecting safety actions
(`apply_fix`, `escalate`, `report`, `retry`) are **deterministic nodes gated by code guards**,
never LLM-invoked.

```text
  detect_failure (node, Playwright)          # no tools — deterministic
        │
        ▼
  triage (node, 1 LLM call -> TriageVerdict) # no tool-choosing
        │ route on category
        ├── regression / data ─► report  (node)            -> outcome=reported
        ├── flake ─────────────► retry   (node) ─► detect_failure (bounded)
        │
        ▼ drift
  ┌───────────────────────────────┐
  │ heal_agent  ⇄  heal_tools      │   ReAct loop, <=3 tools:
  │  (assistant)   (ToolNode)      │   { check_memory, propose_candidates, judge_heal }
  └──────────────┬────────────────┘   loops until an approved verdict or attempt cap
                 │ route via guards
                 ├── can_apply(verdict, τ) ─► apply_fix (node) -> outcome=healed
                 └── else / cap reached ────► escalate  (node) -> outcome=escalated
```

Why this shape:
- **≤3 tools per assistant** (only `heal_agent` is an assistant; it has exactly 3). Triage is
  a single classification call — a plain node, not a tool-choosing loop. Detect is deterministic.
- **Safety is even stronger than the all-in-one loop:** `apply_fix`/`escalate`/`report` are
  deterministic graph edges driven by the `can_apply` / `can_propose` guards, so the LLM never
  *chooses* to apply or skip the judge — the graph + guards do.
- **The loop stays where it earns its keep:** `heal_agent` iterates over candidates and the
  judge (propose → judge → maybe re-propose) until approved or the attempt cap fires.

Key guards (in tool/node code, checked against typed state):
- `heal_agent` is only reached when `triage.category == "drift"` (graph topology) AND
  `propose_candidates` re-checks `can_propose(triage)` defensively.
- `apply_fix` edge requires `can_apply(verdict, τ)` (approved ∧ conf≥τ ∧ assertion_held);
  the node also does the single-match dry-run and test-dir-only write.
- `report` is the only node reachable for `regression`/`data`.
- Termination: every branch ends in a terminal node setting `outcome`; `heal_agent` loop is
  bounded by `MAX_HEAL_ATTEMPTS` + LangGraph `recursion_limit` → forced escalate.

> Splitting further later: if `heal_agent` ever needs a 4th tool, split it into two agents
> (e.g. `signal_agent` {gather_a11y, gather_text} → `verify_agent` {judge_heal}) each with its
> own ToolNode, rather than growing one agent past 3 tools.

### Boundaries

- **≤3 tools per assistant (ADR-006a):** only `heal_agent` is an assistant, with exactly the
  3 healing tools. Detect and triage are deterministic nodes; apply/escalate/report/retry are
  deterministic nodes. Grow past 3 → split into another agent + ToolNode.
- **Side effects live in tools/nodes behind thin adapters** (`agent/llm.py`, `sut/harness.py`,
  `memory/store.py`, `tools/escalate.py`).
- **State has two channels:** `messages` (the heal_agent ReAct trail, `add_messages` reducer)
  drives that sub-loop; typed artifacts (`failure/triage/proposal/verdict/attempts/outcome`)
  are what the guards and backbone routing read.
- **LLM access only via `agent/llm.py`** so every call is traced + deterministic.
- **`apply_fix` may write only files under the SUT test dir** — an explicit allow-path guard;
  it can never touch application source.

### Dependencies

- Runtime: `langgraph`, `playwright`, `langfuse`, `pydantic`, `openai` (one SDK covers
  DeepSeek too via `DEEPSEEK_BASE_URL`).
- Dev/eval: `pytest`, `promptfoo` (via `npx`), optional `deepeval`.
- Python 3.11+, managed with `uv` (fallback pip+venv). `playwright install chromium`.

### Data flow

```text
runner ─► run_agent(failure_context)
  detect_failure ─► AgentState.failure
  triage ─► AgentState.triage ──┬─ regression/data ─► report ─► outcome=reported
                                ├─ flake ─► retry ─► (loop / exhaust ─► escalate)
                                └─ drift ─► check_memory
        check_memory ─ hit ─► apply_fix (0 LLM)            ─► outcome=healed
                     └ miss ─► heal_candidates ─► judge ──┬─ ≥τ ─► apply_fix ─► outcome=healed
                                                          └─ <τ / reject ─► escalate ─► outcome=escalated
```

### API contracts

- `run_agent(ctx: FailureContext) -> AgentResult` — single public entry point.
- Each node: `def node(state: AgentState) -> dict` (LangGraph partial-state update).
- `llm.complete(prompt, schema: type[BaseModel], *, model, name) -> BaseModel` — traced,
  structured, `temperature=0`.
- `store.get(key) -> HealMemoryEntry | None`, `store.put(entry)`, `store.invalidate(key)`.

## Decisions

### ADR-001: SUT strategy — A first, B for the demo, keep both
- Context: need reproducible drift for CI **and** a believable demo.
- Options: A (harness only), B (fork only), both.
- Decision: build A (saucedemo + DOM-mutation harness) for the MVP and CI fixtures;
  add B (RealWorld v1→v2) for Phase 8 polish; reuse the v1→v2 a11y diff to auto-generate
  Phase 7 fixtures.
- Consequences: slightly more SUT code, but A gives determinism and B gives realism, and the
  fixture generator unifies them.

### ADR-002: `apply_fix` patch mechanism — AST vs regex
- Context: must replace a locator string in a Playwright test file safely and reversibly.
- Options: (a) regex/string replace of the exact broken selector; (b) Python AST rewrite.
- Decision: **locator-aware replacement** — replace `broken_selector` only where it occurs
  inside a quoted string literal (a real locator argument), never in comments or surrounding
  code; abort + escalate on 0 or >1 such occurrences. A unified **diff artifact** is written
  before the file is mutated (reviewable). Implemented in `tools/apply_fix.py`
  (`replace_locator`, `make_diff`). Full AST/codemod per language remains a future upgrade.
- Consequences: reversible + safe against collateral edits to comments/code; the single-match
  guard prevents guessing; the diff gives a human a reviewable record of every patch.

### ADR-003: LLM providers (split agent/judge) + determinism
- Context: triage/heal/judge need structured, repeatable output; the judge backs the
  false-heal guard, so it should not be the same model it is grading.
- Decision: **OpenAI for the agent (triage + heal); DeepSeek for the judge.** DeepSeek is
  OpenAI-API-compatible, so `agent/llm.py` is one wrapper with a base-url swap
  (`DEEPSEEK_BASE_URL`). Pin a current OpenAI model id for triage/heal and a current DeepSeek
  id for the judge (verify ids/pricing in OpenAI + DeepSeek docs via context7/web before
  Phase 2). `temperature=0`, pinned ids, Pydantic structured output, all Langfuse-wrapped.
- Rationale: an **independent judge vendor** reduces self-preference bias — a real
  credibility lever for the "never mask a regression" claim.
- Consequences: stable eval thresholds; two keys (`OPENAI_API_KEY`, `DEEPSEEK_API_KEY`);
  provider swap stays isolated to `agent/llm.py` + `agent/config.py`. Anthropic not used.

### ADR-004: Heal memory store — keyed JSON first
- Context: replay known fixes with zero LLM calls.
- Decision: keyed JSON behind a `store` interface; swap to SQLite/mem0 later without touching
  nodes.
- Consequences: trivial to start; interface keeps the upgrade path open.

### ADR-005: Escalation — HITL PR via LangGraph interrupt
- Context: low-confidence heals must be human-reviewed, never silently committed.
- Decision: `escalate` uses `interrupt()`; opens a PR (scoped token) with full evidence;
  falls back to `escalations/<id>.md` if PR creation fails.
- Consequences: requires a checkpointer for resumable interrupts; safe by construction.

### ADR-006: Runtime control flow — deterministic backbone + one scoped heal agent
- Context: choose between a fixed node chain (topology is the safety guarantee) and a single
  assistant looping over all tools (thought→action→observation). A single assistant bound to
  ~10 tools also picks tools poorly.
- Options: (a) one assistant with all tools (guarded ReAct); (b) deterministic backbone +
  small stage agents (≤3 tools each); (c) fully fixed node chain (no LLM routing).
- Decision: **(b).** Deterministic nodes for detect, triage, and all side-effecting safety
  actions (apply_fix/escalate/report/retry); **one ReAct sub-agent `heal_agent` with exactly 3
  tools** (`check_memory`, `propose_candidates`, `judge_heal`) for the only iterative step.
  Safety invariants are code guards (`can_propose`, `can_apply`) on graph edges + in tools.
- **ADR-006a (tool-count rule):** no assistant node may be bound to more than 3 tools. If a
  stage needs more, split it into another assistant + its own ToolNode.
- Consequences: better tool selection (small menus), and safety is *stronger* than the all-in-one
  loop — the LLM never chooses to apply/skip-judge; the graph + guards do. Cost: a few more graph
  nodes; the heal loop still needs an attempt cap + `recursion_limit` to always terminate. The
  guards must be unit-tested directly (done: `tests/test_guards.py`).

## Implementation Constraints

- **Do not touch:** SUT application source (saucedemo is third-party; RealWorld fork app code
  is changed only deliberately to create v2, never by the agent).
- **Must reuse:** `agent/llm.py` for every LLM call; `AgentState`/Pydantic models for all
  inter-node data; `memory/store` interface for persistence.
- **Must avoid:** untraced LLM/tool calls; free-form string verdicts; `apply_fix` writing
  outside the test dir; non-deterministic model settings; healing anything triaged as
  regression/data.
