# PLAN.md — Self-Healing Playwright Agent (Triage → Heal → Judge)

A LangGraph agent that detects Playwright test failures, **triages** them
(selector drift vs. genuine regression vs. flake), heals only true selector
drift, and validates every heal with an LLM judge before applying it.
Two planes: a **runtime plane** (the graph, traced in Langfuse) and an
**eval plane** (Promptfoo fixtures in CI).

> Core principle that makes this a QA project and not a footgun:
> **the agent must never make a test green by masking a real regression.**
> Triage exists to protect against exactly that.

---

## Working agreement (for Claude Code)

- Think before coding; smallest change that satisfies the phase.
- One phase at a time. Do not start the next phase until acceptance criteria pass.
- Verify every change by running it (tests, a real graph invocation, or a trace in Langfuse).
- Keep nodes pure and single-purpose; all shared state goes through the LangGraph state object.
- All LLM calls and tool calls are traced in Langfuse from Phase 1 onward — no untraced calls.
- Verdicts are Pydantic models, never free-form strings.
- Update this file's checkboxes as phases complete; checkpoint progress in `TASK.md`.

---

## Architecture

```
RUNTIME PLANE (LangGraph, traced in Langfuse)

  detect_failure
        │
        ▼
     triage ──────── genuine regression / data ──► report (do NOT heal)
        │                                             
        ├──────────── flake / timing ─────────────► retry_with_backoff
        │
        ▼ (selector drift)
   heal_candidates  ──►  judge  ──►  high confidence ──► apply_fix
                                 └─►  low confidence  ──► escalate (HITL interrupt → PR)

EVAL PLANE (CI, offline)

  DOM-mutation harness ─► fixture set ◄─ replayed Langfuse traces
                              │
                              ▼
                         Promptfoo (model-graded + deterministic assertions)
                              │
                              ▼
                     GitHub Actions gate on healer-prompt changes
```

## Runtime control flow — Guarded ReAct (ADR-006)

The runtime plane is a **deterministic backbone** (detect → triage → branch; and the
side-effecting actions apply_fix/escalate/report/retry as plain nodes) plus **one scoped
ReAct sub-agent `heal_agent` bound to exactly 3 tools** (`check_memory`,
`propose_candidates`, `judge_heal`) for the only step that needs iteration. **No assistant
node sees more than 3 tools (ADR-006a)** — split into another agent + ToolNode before
growing one past 3. The safety invariants ("never heal a regression", "never apply an
unjudged or assertion-hollowing heal") are enforced as **code guards on graph edges + in
tools**, checked against typed state (`triage`, `proposal`, `verdict`), so the LLM never
chooses to apply or skip the judge — the graph does. Rationale in
`docs/implementation/architecture.md` (ADR-006 / ADR-006a).

## Stack

- **Orchestration:** LangGraph
- **Browser / heal execution:** Playwright (library + accessibility tree; Playwright MCP optional)
- **Judge / verdicts:** LLM-as-judge, Pydantic structured output
- **Runtime observability:** Langfuse (traces, scores, cost, latency)
- **Eval plane:** Promptfoo (CI), optional DeepEval pytest gating
- **SUT (two options, pick per goal):**
  - **A — Stable site + DOM-mutation harness (default, MVP):** saucedemo.com (or
    the-internet) with a Playwright `addInitScript` that injects controlled,
    reproducible selector drift. Lowest ops, deterministic, feeds the eval plane.
  - **B — Forked React app, versioned v1→v2 (portfolio polish, high fidelity):**
    fork Conduit / RealWorld, deploy two app versions where v2 is a real frontend
    refactor (renamed `data-testid`s, restructured DOM, changed ARIA roles). The
    drift is *organic* — "the frontend team shipped a refactor" — not injected.
    Higher ops (two deploys), most believable end-to-end demo.

---

## SUT Option B — Conduit/RealWorld v1→v2 (high-fidelity narrative)

**Why:** Option A's injected drift is deterministic but synthetic — a reviewer can
say "you broke it on purpose." Option B reproduces the real failure mode self-healing
exists for: a frontend refactor lands, selectors silently drift, the suite goes red.
The agent triages and heals against an *unscripted* diff. This is the demo that
convinces a hiring manager.

**Setup**
- Fork RealWorld (Conduit). Pin **v1** = baseline; author the 4–6 Playwright tests
  green against v1.
- Branch **v2** = a deliberate but realistic refactor:
  - rename `data-testid`s (e.g. `nav-login` → `header-auth-login`)
  - restructure DOM (wrap fields in new container divs)
  - swap `id`↔`class`, alter ARIA roles on a few controls
  - **a spectrum of planted issues** (see Improvement 2) — not a single regression.
- Deploy both: v1 and v2 on separate ports/URLs (docker compose: `conduit-v1:3001`,
  `conduit-v2:3002`), or v2 behind a feature flag.

**Demo flow**
1. Tests green on v1.
2. Point the suite at v2 → multiple reds.
3. Agent: `detect_failure` → `triage` →
   - selector drifts → heal → judge → apply/escalate
   - planted regression → **report, not heal** (proves the guard)
4. Diff the auto-applied locator patches; show the escalation PR for low-confidence cases.

**Maps onto existing phases:** v1→v2 diff replaces (or augments) the mutation
profiles. Each refactored selector = one fixture for the Phase 7 Promptfoo set.
The planted regression = the Phase 2 negative test, now organic instead of injected.

**Cost:** two deploys + maintaining the v2 branch. Do Option A first (MVP); graduate
to Option B for Phase 8 portfolio polish. Keep both — A gives breadth/determinism for
CI, B gives the believable recorded demo.

---

## Phase 0 — Setup & SUT

**Goal:** Repo scaffolded, dependencies installed, SUT reachable, Langfuse live.

- [ ] Repo scaffold: `agent/`, `nodes/`, `sut/`, `eval/`, `tests/`
- [ ] Install: `langgraph`, `playwright`, `langfuse`, `pydantic`, `pytest`; `promptfoo` via npx
- [ ] `playwright install chromium`
- [ ] Pick SUT (default: saucedemo.com — Option A) and write a smoke test that logs in green
- [ ] Langfuse project created, keys in `.env`, a single traced "hello" call confirmed
- [ ] Pin LLM determinism: fixed model id, `temperature=0`, seed where available (see Improvement 4)

**Acceptance:** smoke test passes against SUT; one trace visible in Langfuse.

---

## Phase 1 — DOM-mutation harness & break detection

**Goal:** Deterministically break selectors and detect the failure cleanly.

- [ ] DOM-mutation harness: Playwright `addInitScript` that, given a config,
      renames/removes `data-testid`, swaps `id`↔`class`, wraps nodes, alters ARIA roles
- [ ] Mutation profiles: `testid-rename`, `role-change`, `text-change`, `structural-wrap`
- [ ] 4–6 baseline Playwright tests (green on un-mutated SUT)
- [ ] Each test carries a one-line **intent** string (see Improvement 6)
- [ ] `detect_failure` node: capture failing step, error type, DOM + a11y snapshot at failure
- [ ] Distinguish selector-resolution errors from assertion errors at this stage
- [ ] All node runs traced in Langfuse

**Acceptance:** applying a mutation profile turns specific tests red; `detect_failure`
captures the snapshot and error class for each.

---

## Phase 2 — Triage node (first-class)

**Goal:** Decide *why* a test failed before doing anything. This is the centerpiece.

- [ ] `TriageVerdict` Pydantic model: `category` (`drift` | `regression` | `flake` | `data`),
      `confidence: float`, `evidence: str`
- [ ] Triage node uses the failure snapshot **+ the test intent string** to classify
- [ ] Conditional routing:
      - `drift` → heal path
      - `regression` / `data` → **report path (no heal)**
      - `flake` / timing → retry-with-backoff path
- [ ] Negative tests: inject all four failure classes (genuine bug, flake, data change,
      pure drift — one each) and confirm each routes correctly (see Improvement 2)
- [ ] Triage decisions scored in Langfuse

**Acceptance:** drift → heal, injected regression → report, flaky waits → retry.
A genuine bug is never sent to the healer.

---

## Phase 3 — Healer node (multi-candidate)

**Goal:** Propose robust selector fixes from several signals, not one guess.

- [ ] Capture a11y tree (role + accessible name), visible text, nearby `data-testid`,
      structural position
- [ ] Generate ranked candidate selectors per signal
- [ ] Prefer role/name and testid over brittle CSS/XPath
- [ ] Output `HealProposal` Pydantic model: ordered candidates + rationale per candidate

**Acceptance:** for each mutation profile, healer returns ≥2 plausible candidates
with the strongest signal ranked first.

---

## Phase 4 — Judge node, verdict & routing

**Goal:** Approve a heal only if it restores the step **and** the original assertion still holds.

- [ ] `HealVerdict` Pydantic model: `approved: bool`, `chosen_selector`, `confidence`, `reason`
- [ ] Judge re-runs the failing step with the candidate AND re-checks the downstream
      assertion (false-heal guard — a heal that makes the step pass but the assertion
      meaningless is rejected)
- [ ] Add a deliberate **false-heal trap** fixture and prove the judge rejects it (Improvement 3)
- [ ] Conditional edge: `confidence ≥ τ` → `apply_fix` (patch the locator in the test file);
      below `τ` → `escalate`
- [ ] `escalate` uses a LangGraph **interrupt** → opens a PR / writes a review artifact
      instead of silently patching; PR body links the Langfuse trace + before/after a11y
      diff (Improvement 7)
- [ ] Tune τ against Phase 7 fixtures

**Acceptance:** correct heals auto-apply; ambiguous ones escalate to a PR;
false heals (step green but assertion hollow) are rejected.

---

## Phase 5 — Heal memory

**Goal:** Make recurring breaks deterministic and cheap.

- [ ] Persist `broken_selector → fixed_selector` mappings (keyed by test + step)
- [ ] On detection, check memory first; replay known fix with no LLM call
- [ ] Invalidate stale entries when a replayed fix fails
- [ ] Hard cap: max LLM heal attempts per run; circuit-break to escalate (Improvement 5)
- [ ] (Optional) back with mem0; a keyed JSON/SQLite store is fine to start

**Acceptance:** a previously-healed break resolves with zero LLM calls on the second run.

---

## Phase 6 — Metrics & dashboards (Langfuse)

**Goal:** Turn the demo into evidence.

- [ ] Define and emit scores: `heal_success_rate`, `false_heal_rate`,
      `mean_attempts_per_heal`, `cost_per_heal` (incl. p99), `auto_vs_escalated_ratio`
- [ ] Dashboard / saved views per metric
- [ ] Capture before/after screenshots for the README

**Acceptance:** every metric populates from a real run batch and is viewable in Langfuse.

---

## Phase 7 — Eval plane (Promptfoo + CI)

**Goal:** Regression-gate the healer prompt before it ships.

- [ ] Build fixture set from mutation profiles + replayed real Langfuse traces
      (each fixture: failure snapshot → expected heal category / selector)
- [ ] Auto-generate fixtures from the v1→v2 a11y-tree diff (Improvement 1)
- [ ] `promptfooconfig.yaml`: deterministic assertions (expected selector present)
      + model-graded (`llm-rubric`) assertions for rationale quality
- [ ] Thresholds for pass rate and false-heal rate
- [ ] GitHub Actions: run Promptfoo on any change to healer/judge prompts; fail the build below threshold
- [ ] (Optional) DeepEval pytest gate for the same suite

**Acceptance:** a deliberate prompt regression fails CI; a good change passes.

---

## Phase 8 — Polish & portfolio

**Goal:** Make it legible to a hiring manager in 60 seconds.

- [ ] README: two-plane diagram, the "never mask a regression" decision, metrics screenshots
- [ ] Short demo recording: induce drift → triage → heal → apply; then induce a real bug → triage → report
- [ ] Architecture decision note on triage and the false-heal guard
- [ ] (Option B) Record the v1→v2 demo: deploy both versions, run the suite against
      v2, capture triage → heal → apply for drift and triage → report for the planted
      regression. This is the headline recording.
- [ ] **Descriptive README** (do at the end, once metrics exist). Model it on the
      `eval-hotel-bot-eval-deepeval` README structure, adapted to this project. Required
      sections:
      1. Title + one-line pitch ("heals selector drift, never masks a regression")
      2. Mental model — two planes (runtime: Guarded ReAct + Langfuse; eval: Promptfoo + CI)
      3. Where the SUT lives (Option A harness vs Option B RealWorld v1→v2)
      4. What the agent does — detect → triage → heal → judge → apply/escalate loop
      5. The metric stack (deterministic selector-present + LLM-rubric rationale)
      6. The differentiator — the false-heal guard ("never mask a regression")
      7. The findings (real numbers; full detail in a `REPORT.md`)
      8. Reproducibility note (pinned model ids, temperature=0, seeds)
      9. How to run (offline eval; live graph run; batch for metrics)
      10. Keys / env (`.env.example` names only)
      11. Repo map (what every dir/file is)
      12. Why LangGraph + Langfuse + Promptfoo (vs alternatives)
      13. Tech stack
      14. Limitations / next steps
- [ ] **Langfuse flow screenshot in README (via Langfuse MCP).** After a real run batch
      exists (Phase 6), use the Langfuse MCP to capture a screenshot of the application
      flow/trace tree **with the logs/spans** for one representative heal run, save it to
      `docs/assets/langfuse-flow.png`, and embed it in README §4 (and the metrics views in
      §7). Depends on Phase 6 (no runs = nothing to screenshot). If the Langfuse MCP cannot
      capture the view headlessly, fall back to a manual screenshot of the same trace.

- [ ] **Final end-to-end validation run (do this once everything is built).** Run the full
      graph live on (a) a real selector-drift case → confirm triage=drift → heal → judge →
      apply, suite green; and (b) a real planted regression → confirm triage=regression →
      report, NO heal, suite stays red on purpose. Confirm every step is traced in Langfuse.
      Record the outcomes + commands + screenshots in `docs/implementation/validation-report.md`
      (flip its status Draft → Passed). This is the "prove it actually works" gate before the
      README numbers are trusted.

**Acceptance:** a reader who doesn't run the code understands what it does, why the
triage node exists, can see the measured heal/false-heal numbers, **and sees the Langfuse
trace+logs screenshot of a real run in the README** — and the final end-to-end run is
recorded as Passed in `validation-report.md`.

---

## Improvements / refinements (folded into the phases above)

1. **v1→v2 as fixture generator, not just demo (Phase 7).** Script that diffs v1 vs v2
   accessibility trees → auto-emits the Promptfoo fixture set (old selector → new
   selector → expected triage category). Fork becomes a self-populating eval corpus:
   Option A's determinism + Option B's realism in one pipeline.

2. **Plant a spectrum of regressions in v2 (Phase 2).** Not one wrong-price case. Add
   one each of: genuine bug, flake/timing, data change, pure drift. Proves all four
   triage branches against an organic diff.

3. **Make the false-heal guard the headline (Phase 4).** Strongest differentiator vs
   every other "AI heals tests" demo. Add a trap fixture where a naive healer makes the
   step green but hollows the assertion (button now matches an element that submits
   nothing). Show the judge rejecting it — one screenshot = the whole pitch.

4. **Pin LLM determinism (Phase 0).** Fixed model id, `temperature=0`, seed where
   available. Otherwise Phase 7 thresholds drift run-to-run and CI flakes on the grader,
   not the code.

5. **Cost guardrail before heal memory (Phase 5).** Hard cap on LLM heal attempts per
   run; circuit-break to escalate. Prevents a pathological drift burning tokens in a
   loop. Feeds `cost_per_heal` p99 in Phase 6.

6. **Triage needs test intent, not just the snapshot (Phase 1/2).** Store a one-line
   intent string per test (`"user logs in and reaches inventory"`). A snapshot alone
   can't tell drift from regression; triage quality collapses without it.

7. **Escalation PR links evidence (Phase 4).** Pulled from stretch into Phase 4. PR
   body explains *why* it's uncertain and links the Langfuse trace + before/after a11y
   diff — the artifact a reviewer actually judges the project on.

---

## Stretch ideas (post-MVP)

- Phoenix alongside Langfuse for OTel-native trace comparison
- Online drift detection: alert when false-heal rate climbs in production runs
- Auto-PR body that explains the heal and links the Langfuse trace
- Cross-browser heal validation before apply
