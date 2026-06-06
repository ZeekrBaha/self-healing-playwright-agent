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
    graph.py            # LangGraph wiring: assistant <-> tools ReAct loop (ADR-006)
    assistant.py        # the single LLM node: reasons, emits tool_calls
    tools.py            # @tool defs (the guarded actions) + ToolNode registration
    state.py            # AgentState (messages + typed artifacts) + Pydantic models
    config.py           # model ids, τ thresholds, attempt/recursion caps, env loading
    llm.py              # traced OpenAI client wrapper (Langfuse), temperature=0, tools bound
  tools/                # implementations behind the @tool wrappers (guards live here)
    capture_snapshot.py # DOM/a11y/error-class snapshot -> failure
    classify_triage.py  # -> TriageVerdict (uses test intent)
    memory_io.py        # check_memory / save_memory (replay known fix, 0 LLM)
    propose_candidates.py # GUARD: drift only -> HealProposal (>=2 ranked)
    judge_heal.py       # re-run step + re-check assertion -> HealVerdict
    apply_fix.py        # GUARD: approved+>=τ+assertion_held, single-match, test-dir only
    report_regression.py # only path for regression/data
    retry_step.py       # bounded backoff for flake
    escalate.py         # interrupt -> PR / escalations/<id>.md
    finish.py           # set outcome -> route END
  sut/
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

### Runtime topology — Guarded ReAct loop (ADR-006)

One LLM `assistant` node loops with a `ToolNode` (`assistant → tools → assistant`) until the
assistant calls `finish()` (routes to END) or an iteration cap forces escalate. The assistant
chooses the next tool each step (thought → action → observation); **safety invariants are
enforced inside the tools as code, not by the model's routing.** The typed artifacts in state
(`triage`, `proposal`, `verdict`) are the source of truth the guards check — the LLM cannot
talk past a guard.

```text
        ┌──────────────┐
   ┌───►│  assistant   │  emits tool_calls?  ── no ─► END
   │    └──────┬───────┘
   │           ▼ yes
   │    ┌──────────────┐
   └────┤  tools (Node)│  execute -> ToolMessage observations
        └──────────────┘
```

Key guards (live in the tool implementations):
- `propose_candidates`: refuse unless `triage.category == "drift"`.
- `apply_fix`: refuse unless `verdict.approved and verdict.confidence >= τ and
  verdict.assertion_held`; single-match dry-run; writes only under the SUT test dir.
- `report_regression`: the only path enabled for `regression`/`data`.
- Termination: `finish(outcome)` → END; iteration/attempt cap (REQ-009) + LangGraph
  `recursion_limit` → forced escalate.

### Boundaries

- **Tools are the only actors:** the assistant node only reasons + emits tool_calls; every
  side effect (browser, LLM sub-calls, disk, PR) happens inside a tool behind a thin adapter
  (`agent/llm.py`, `sut/harness.py`, `memory/store.py`, `tools/escalate.py`).
- **State has two channels:** `messages` (ReAct trail, `add_messages` reducer) drives the
  loop; typed artifacts (`failure/triage/proposal/verdict/attempts/outcome`) are what guards
  read. Tools update the typed channel, not just the chat.
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
- Decision: **start with targeted string replacement** of the exact `broken_selector` within
  the identified test+step, guarded by a dry-run diff that must match a single occurrence;
  abort + escalate on 0 or >1 matches. Revisit AST only if string replace proves brittle.
- Consequences: simplest reversible mechanism; the single-match guard prevents collateral edits.

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

### ADR-006: Runtime control flow — single assistant + guarded-tool ReAct loop
- Context: choose between a fixed node chain (`triage→heal→judge→apply`) where topology is the
  safety guarantee, vs a single assistant node that loops over tools (thought→action→observation)
  until done.
- Options: (a) guarded ReAct (LLM routes freely, tools enforce invariants); (b) constrained
  ReAct (triage hard-branches the graph so heal tools are unreachable for regressions);
  (c) fixed node chain (no LLM routing).
- Decision: **(a) Guarded ReAct.** One `assistant` node ↔ `ToolNode`; the old nodes become
  tools; safety lives in code guards inside the tools (checked against typed state artifacts,
  not the chat). Loop ends on `finish()` or an iteration cap → escalate.
- Consequences: flexible/agentic and matches the "one assistant + tools loop" model, while the
  "never heal a regression / never apply an unjudged heal" invariants stay deterministic.
  Cost: must test the guards directly (a malicious/hallucinated tool-call sequence must be
  rejected), and set both an attempt cap and `recursion_limit` so the loop always terminates.

## Implementation Constraints

- **Do not touch:** SUT application source (saucedemo is third-party; RealWorld fork app code
  is changed only deliberately to create v2, never by the agent).
- **Must reuse:** `agent/llm.py` for every LLM call; `AgentState`/Pydantic models for all
  inter-node data; `memory/store` interface for persistence.
- **Must avoid:** untraced LLM/tool calls; free-form string verdicts; `apply_fix` writing
  outside the test dir; non-deterministic model settings; healing anything triaged as
  regression/data.
