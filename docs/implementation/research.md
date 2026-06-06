# Research

Date: 2026-06-06
Status: Draft

## Goal

A LangGraph agent that, when a Playwright test fails, decides **why** it failed
(selector drift / genuine regression / flake / data change), heals **only** true
selector drift, and validates every heal with an LLM judge before applying it — so
the suite is repaired without ever masking a real bug. Success = the agent
auto-fixes drift, escalates ambiguous cases to a PR, and provably refuses to heal a
genuine regression.

## Users

- **Primary — QA / test-infra engineer:** owns a Playwright suite that goes red after
  a frontend refactor. Wants the drift fixed automatically and the real bugs surfaced,
  not hidden. Workflow: suite runs in CI → reds → agent triages → applies safe heals,
  opens PRs for the rest, reports regressions.
- **Secondary — hiring manager / reviewer (portfolio context):** evaluates the project
  in ~60s. Needs to see the triage decision, the false-heal guard, and measured
  heal/false-heal numbers without running anything.

## Evidence

- Repository fact: `PLAN.md` defines the two-plane architecture (runtime: LangGraph +
  Langfuse; eval: Promptfoo + CI) and an 8-phase build order.
- Repository fact: this is a greenfield project — folder `self-healing-playwright-agent`
  contains only `PLAN.md` at research time.
- External source (knowledge, 2026-01 cutoff): LangGraph supports conditional edges and
  `interrupt()` for human-in-the-loop; Langfuse provides traces + scores; Promptfoo
  supports deterministic + `llm-rubric` model-graded assertions; RealWorld/Conduit is a
  public, forkable reference app. Verify exact APIs against current docs at build time.
- Assumption: saucedemo.com and the-internet remain reachable and stable for Option A.
- Assumption: OpenAI runs the agent (triage + heal) and DeepSeek runs the judge (independent
  vendor → less judge bias). Verify model ids/pricing in OpenAI + DeepSeek docs before Phase 2.

## Constraints

- **Stack (overrides the skill default of Next.js — this is a headless Python agent, no
  web UI of its own):**
  - Language: Python 3.11+ (LangGraph + Playwright-Python are the paved path).
  - Orchestration: LangGraph.
  - Browser/heal execution: Playwright (Python), accessibility tree; Playwright MCP optional.
  - Structured output / verdicts: Pydantic v2.
  - LLM: OpenAI for triage/heal, DeepSeek for the judge (OpenAI-API-compatible via
    `DEEPSEEK_BASE_URL`); `temperature=0`, fixed model ids. See ADR-003.
  - Runtime observability: Langfuse (traces, scores, cost, latency).
  - Eval plane: Promptfoo via `npx`; optional DeepEval pytest gate.
  - Tests: pytest. CI: GitHub Actions.
  - Package manager: `uv` (fallback `pip` + venv).
- **SUT (system under test) — two options:**
  - **A (MVP, default):** saucedemo.com + a Playwright `addInitScript` DOM-mutation harness
    that injects deterministic, reproducible selector drift.
  - **B (portfolio polish):** forked Conduit/RealWorld deployed at v1 and v2, where v2 is a
    real frontend refactor — organic drift, the believable end-to-end demo.
- **Existing architecture:** none (greenfield).
- **Environment/secrets:** `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`,
  `OPENAI_API_KEY`, `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL`. Never committed; `.env` +
  `.env.example` only.
- **Budget/performance:** hard cap on LLM heal attempts per run (circuit-break to
  escalate); memoized heals cost zero LLM calls on replay; target `cost_per_heal` tracked
  (incl. p99).
- **Accessibility/privacy/security:** no PII (SUT uses fictional/demo accounts); the agent
  patches test files only, never application source; escalations go through a PR, never a
  silent commit.

## Unknowns

- [ ] Exact LangGraph `interrupt()` / checkpointer API for the HITL escalation path (verify current docs).
- [ ] Whether `apply_fix` patches the test file via AST rewrite or regex locator replacement — pick in design.
- [ ] Heal-memory backing store: keyed JSON vs SQLite vs mem0 — start simplest.
- [ ] Promptfoo provider config for OpenAI + DeepSeek + how to feed snapshot fixtures as test cases.
- [ ] For Option B: hosting two RealWorld versions (docker compose ports vs feature flag).
- [ ] Confidence threshold τ for auto-apply vs escalate — must be tuned against Phase 7 fixtures, not guessed.

## Risks

- **False heal (the central risk):** a heal makes the step green but the downstream
  assertion becomes meaningless → real bug masked. Mitigation: judge re-checks the
  downstream assertion; dedicated trap fixtures; `false_heal_rate` gated in CI.
- **Triage misclassification:** drift labeled regression (suite stays red) or regression
  labeled drift (bug masked). Mitigation: triage gets the test **intent** string, not just
  the snapshot; four-class negative test suite; triage scored in Langfuse.
- **Non-deterministic grader:** LLM judge/triage vary run-to-run → CI flakes on the grader,
  not the code. Mitigation: `temperature=0`, pinned model ids, seeds where available.
- **Cost blowup:** pathological drift loops the healer. Mitigation: per-run attempt cap +
  circuit break; heal memory.
- **Patching the wrong file / corrupting tests:** Mitigation: `apply_fix` scoped to test
  files, dry-run diff first, version-controlled, reversible.
- **SUT availability (Option A):** third-party site changes/blocks. Mitigation: pin
  flows; Option B fork removes the dependency for the demo.

## Options Considered

1. **SUT Option A — stable site + DOM-mutation harness.** Pros: deterministic, lowest ops,
   feeds the eval plane cleanly, fast to stand up. Cons: synthetic drift ("you broke it on
   purpose"). Choose for: MVP and CI fixtures.
2. **SUT Option B — forked Conduit/RealWorld v1→v2.** Pros: organic, believable "frontend
   team refactored" narrative; best recorded demo. Cons: two deploys + a maintained v2
   branch. Choose for: Phase 8 portfolio polish. **Decision: do A first, graduate to B;
   keep both** (A = breadth/determinism for CI, B = headline demo). The v1→v2 a11y-tree
   diff also auto-generates Phase 7 fixtures.
3. **Heal strategy — single best-guess selector vs multi-candidate ranked.** Multi-candidate
   chosen: more robust, gives the judge real choices, ranks role/name + testid over brittle
   CSS/XPath.
4. **Escalation — silent auto-commit vs HITL PR.** HITL PR chosen: low-confidence heals must
   be reviewable; PR body links the Langfuse trace + before/after a11y diff.
