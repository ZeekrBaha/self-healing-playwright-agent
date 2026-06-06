# Requirements

Date: 2026-06-06
Status: Draft

## Functional Requirements

- **REQ-001 — Detect failure:** On a Playwright test failure, the system captures the
  failing step, error class (distinguishing selector-resolution from assertion errors),
  and a DOM + accessibility snapshot at the point of failure.
- **REQ-002 — Triage:** The system classifies each failure as `drift`, `regression`,
  `flake`, or `data`, using the failure snapshot **and** the test's intent string, and
  emits a `TriageVerdict` (category, confidence, evidence).
- **REQ-003 — Route by triage:** `drift` → heal path; `regression`/`data` → report path
  (no heal); `flake`/timing → retry-with-backoff path.
- **REQ-004 — Heal candidates:** For drift, the system proposes ≥2 ranked candidate
  selectors derived from independent signals (a11y role+name, visible text, nearby
  `data-testid`, structural position), preferring role/name and testid over CSS/XPath,
  emitting a `HealProposal` with per-candidate rationale.
- **REQ-005 — Judge:** The system re-runs the failing step with a candidate **and**
  re-checks the downstream assertion; it emits a `HealVerdict` (approved, chosen_selector,
  confidence, reason). A heal that makes the step pass but the assertion meaningless is
  rejected (false-heal guard).
- **REQ-006 — Apply or escalate:** confidence ≥ τ → patch the locator in the test file
  (`apply_fix`); confidence < τ → `escalate` via a LangGraph interrupt that opens a PR /
  writes a review artifact (never a silent patch).
- **REQ-007 — Report regressions:** Genuine regressions/data changes produce a report
  artifact and are never sent to the healer.
- **REQ-008 — Heal memory:** The system persists `broken_selector → fixed_selector`
  mappings keyed by test+step; on detection it checks memory first and replays a known fix
  with **zero LLM calls**, invalidating stale entries when a replay fails.
- **REQ-009 — Cost guardrail:** A hard cap on LLM heal attempts per run; on exceeding it,
  circuit-break to escalate.
- **REQ-010 — Tracing:** Every LLM call and tool call is traced in Langfuse from Phase 1
  onward — no untraced calls. Triage and heal decisions are scored.
- **REQ-011 — Metrics:** Emit `heal_success_rate`, `false_heal_rate`,
  `mean_attempts_per_heal`, `cost_per_heal` (incl. p99), `auto_vs_escalated_ratio`, each
  viewable in Langfuse.
- **REQ-012 — Eval plane:** A Promptfoo fixture set (from mutation profiles, replayed
  Langfuse traces, and the v1→v2 a11y diff) with deterministic (expected selector present)
  + model-graded (`llm-rubric` rationale quality) assertions, gated by pass-rate and
  false-heal-rate thresholds.
- **REQ-013 — CI gate:** GitHub Actions runs Promptfoo on any change to healer/judge
  prompts and fails the build below threshold.
- **REQ-014 — SUT Option B demo:** Forked Conduit/RealWorld deployed at v1 and v2 (v2 a
  real refactor with a spectrum of planted issues), with a recorded end-to-end demo:
  drift → triage → heal → apply, and planted regression → triage → report.

## Non-Functional Requirements

- **Performance:** Memoized heal replays make zero LLM calls. Per-run LLM heal attempts
  bounded by the REQ-009 cap. Triage+heal+judge for one failure target < ~60s wall.
- **Reliability:** Nodes are pure and single-purpose; all shared state flows through the
  LangGraph state object. `apply_fix` is reversible (version-controlled, dry-run diff first).
- **Security/privacy:** No secrets committed (`.env` only; `.env.example` documents names).
  Agent patches **test files only**, never application source. No PII (fictional SUT data).
- **Accessibility:** N/A to the agent itself (headless). The SUT's a11y tree is an input
  signal, not a deliverable.
- **Observability:** Langfuse traces for every node; structured run logs; per-run artifacts
  (reports, escalation PR bodies, before/after a11y diffs).
- **Determinism:** Fixed model ids, `temperature=0`, seeds where supported, so eval-plane
  thresholds are stable.

## Non-Goals

- Building or restyling the SUT's UI (saucedemo is third-party; RealWorld is forked as-is).
- Healing anything other than selector drift (assertion logic, app bugs, test intent).
- Generating new tests from scratch (this repairs an existing suite).
- A custom metrics dashboard UI (Langfuse-native views are the dashboard).
- Cross-browser heal validation (stretch).
- Production deployment of the agent as a service (stretch).

## Acceptance Criteria

- **AC-001 → REQ-001:** Applying a mutation profile turns specific tests red; `detect_failure`
  records the snapshot and the correct error class for each.
- **AC-002 → REQ-002/003:** Drift routes to heal, an injected assertion-level regression
  routes to report, flaky waits route to retry. A genuine bug is never sent to the healer.
- **AC-003 → REQ-004:** For each mutation profile the healer returns ≥2 plausible candidates
  with the strongest signal ranked first.
- **AC-004 → REQ-005:** A correct candidate is approved; a false-heal trap fixture (step
  green, assertion hollow) is rejected with a reason.
- **AC-005 → REQ-006:** Heals with confidence ≥ τ auto-apply and patch the test file;
  confidence < τ opens a PR / writes a review artifact instead of patching.
- **AC-006 → REQ-008:** A previously-healed break resolves with zero LLM calls on the second run.
- **AC-007 → REQ-009:** Exceeding the per-run heal-attempt cap circuit-breaks to escalate
  (no infinite loop).
- **AC-008 → REQ-010/011:** Every metric populates from a real run batch and is viewable in
  Langfuse; no untraced LLM/tool calls appear.
- **AC-009 → REQ-012/013:** A deliberate prompt regression fails CI; a good prompt change
  passes; the false-heal-rate threshold is enforced.
- **AC-010 → REQ-014:** Pointing the v1 suite at v2 produces reds; the agent heals the drift,
  reports the planted regression, and the demo is recorded.
