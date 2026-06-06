# Design

Date: 2026-06-06
Status: Draft

## Product Flow

- **Entry:** A Playwright test fails (in CI or local). The runner hands the failure
  context to the agent graph (`run_agent(failure_context)`).
- **Main workflow:** `detect_failure` → `triage` → conditional route:
  - `drift` → `check_memory` → (hit) `apply_fix` / (miss) `heal_candidates` → `judge` →
    (≥τ) `apply_fix` / (<τ) `escalate`.
  - `regression` / `data` → `report` (terminal, no heal).
  - `flake` → `retry_with_backoff` → re-enter `detect_failure` (bounded retries).
- **States (agent run outcomes):**
  - *Healed (auto):* fix applied, step + assertion green, trace + memory updated.
  - *Escalated:* PR / review artifact written, no source mutated.
  - *Reported:* regression/data verdict, report artifact written, suite stays red on purpose.
  - *Retried→resolved* or *Retried→exhausted→escalate*.
  - *Error/degraded:* snapshot capture or LLM call fails → escalate with diagnostic.
- **Mobile/desktop:** N/A (headless agent). The only human surfaces are the escalation PR
  and Langfuse dashboards.

## Screens / Views

This project has **no application UI of its own**. The human-facing surfaces are:

### Escalation PR / review artifact
- Purpose: let a human approve an uncertain heal.
- Data shown: failing test+step, triage verdict, ranked candidates + rationale, judge
  verdict + confidence, before/after a11y diff, link to the Langfuse trace.
- Actions: approve (merge) / reject / edit the selector.
- Error states: if PR creation fails, fall back to a `escalations/<id>.md` artifact on disk.
- Tests: artifact content assertions; PR body contains the trace link and a11y diff.

### Langfuse dashboard (native)
- Purpose: evidence — the metrics in REQ-011 over a run batch.
- Data shown: `heal_success_rate`, `false_heal_rate`, `mean_attempts_per_heal`,
  `cost_per_heal` (incl. p99), `auto_vs_escalated_ratio`; per-trace triage/heal/judge spans.
- Tests: metrics populate from a real batch (manual verification + screenshot for README).

### README + demo recording (portfolio)
- Purpose: 60-second legibility. Two-plane diagram, the "never mask a regression" decision,
  before/after screenshots, the v1→v2 recording.

## System Architecture

- **Frontend:** none (the agent is headless; SUT UI is external/forked).
- **Backend / orchestration:** LangGraph **Guarded ReAct loop** (ADR-006) — one `assistant`
  LLM node ↔ `ToolNode`, looping thought→action→observation until `finish()` or an iteration
  cap. The detect/triage/heal/judge/apply/escalate/report/retry actions are **tools**; safety
  invariants are code guards inside the tools (checked against typed state, not the chat).
  `interrupt()` for HITL escalation.
- **Browser/heal execution:** Playwright (Python) — drives the SUT, captures DOM + a11y
  snapshots, re-runs steps for the judge.
- **Storage:** heal-memory store (keyed JSON to start; SQLite/mem0 optional later);
  per-run artifacts on disk (`runs/<id>/...`, `escalations/<id>.md`, `reports/<id>.md`).
- **External services:** Langfuse (traces/scores), OpenAI (triage/heal) + DeepSeek (judge),
  GitHub (escalation PRs), SUT host (saucedemo / RealWorld v1+v2).
- **AI/model layer:** triage classifier, heal proposer, heal judge — each a traced LLM call
  with Pydantic structured output, `temperature=0`, pinned model id.
- **Tool/function calls:** snapshot capture, step re-run, selector patch, memory get/put,
  PR open, retry-with-backoff.

## Data Model

```text
# Graph state — Guarded ReAct (ADR-006): two channels
AgentState:
  messages: Annotated[list, add_messages]   # ReAct thought/action/observation trail (drives loop)
  test_id: str
  step_id: str
  test_intent: str                 # one-line: "user logs in and reaches inventory"
  failure: FailureSnapshot | None
  triage: TriageVerdict | None
  proposal: HealProposal | None
  verdict: HealVerdict | None
  outcome: Literal["healed","escalated","reported","retried","error"] | None
  attempts: int                    # LLM heal attempts this run (cap in REQ-009)
  trace_id: str

# Pydantic verdict/IO models (never free-form strings)
FailureSnapshot:
  failing_step: str
  error_class: Literal["selector_resolution","assertion","timeout","other"]
  broken_selector: str | None
  dom_html: str                    # trimmed/relevant subtree
  a11y_tree: dict                  # role + accessible-name tree at failure
  screenshot_path: str | None

TriageVerdict:
  category: Literal["drift","regression","flake","data"]
  confidence: float                # 0..1
  evidence: str

HealCandidate:
  selector: str
  signal: Literal["role_name","text","nearby_testid","structural"]
  rank: int
  rationale: str

HealProposal:
  candidates: list[HealCandidate]  # ordered, strongest first, len >= 2

HealVerdict:
  approved: bool
  chosen_selector: str | None
  confidence: float                # vs threshold τ
  reason: str
  step_passed: bool
  assertion_held: bool             # false-heal guard core field

# Persistence
HealMemoryEntry:
  key: str                         # f"{test_id}:{step_id}:{broken_selector}"
  fixed_selector: str
  last_verified: str               # ISO timestamp (passed in, not generated in-graph)
  hits: int
```

## Failure Modes

- **Snapshot capture fails:** log + `outcome=error` → escalate with diagnostic; never guess.
- **LLM call errors/timeouts:** bounded retry (provider-level), then escalate; trace the failure.
- **False heal (step green, assertion hollow):** judge sets `assertion_held=False` → reject,
  do not apply, route to escalate. Counted in `false_heal_rate`.
- **Triage low confidence:** below a triage-confidence floor → escalate rather than auto-route
  to heal (don't gamble a possible regression into the healer).
- **Memory replay fails:** invalidate the entry, fall through to fresh `heal_candidates`.
- **Heal-attempt cap exceeded:** circuit-break → escalate (REQ-009).
- **`apply_fix` patch mismatch:** dry-run diff doesn't match expected locator → abort apply,
  escalate; never write a partial patch.
- **PR creation fails:** fall back to on-disk `escalations/<id>.md`.

## Observability

- **Logs:** structured per-node logs to stderr + `runs/<id>/run.log`.
- **Metrics/events:** Langfuse spans per node; scores for triage correctness, heal success,
  false heal; the REQ-011 aggregate metrics over batches.
- **Error tracking:** `outcome=error` traces tagged; degraded-mode escalations carry the
  diagnostic and trace link.

## Security and Privacy

- **Secrets:** env vars only (`OPENAI_API_KEY`, `DEEPSEEK_API_KEY`, `LANGFUSE_*`); `.env` git-ignored;
  `.env.example` lists names. No client-side/committed secrets.
- **PII/data retention:** none — SUT uses fictional/demo accounts; snapshots contain no PII.
- **Auth/authorization:** agent writes to a test repo via a scoped GitHub token for PRs only.
- **Abuse prevention:** agent patches **test files only**, never app source; all mutations
  reversible and version-controlled; the false-heal guard is the core safety control.

## Design Review

PM: Problem is sharp and prioritized — triage + false-heal guard are the differentiators;
build A first, B for the demo. Approved direction.

Developer: Implementable on LangGraph + Playwright-Python. Open item: choose AST vs
regex for `apply_fix` (see architecture ADR-002). Keep nodes pure.

Tester: Acceptance criteria are testable; need the four-class triage fixtures and the
false-heal trap fixture explicitly built, not assumed.

Reviewer: Watch determinism (pin models/temp), and ensure `apply_fix` cannot touch app
source. Confirm escalation never silently commits.

Team Lead: Phase order matches risk: detection → triage → heal → judge → memory → metrics
→ eval gate → polish. Triage (Phase 2) and judge (Phase 4) are the gates; do not skip their
negative tests.
