# Design System

Date: 2026-06-06
Status: Draft (UI mostly out of scope)

> This project is a **headless Python agent**. It has no application UI of its own, so the
> full visual token system does not apply. The skill's design-system step is recorded here
> honestly: the only human-facing surfaces are (1) the escalation PR / Markdown artifact,
> (2) Langfuse-native dashboards, and (3) the README + demo recording. Tokens below govern
> only those surfaces. The SUT (saucedemo / forked RealWorld) keeps its own existing look —
> we do not restyle it.

## References (taste anchors)

- Escalation PR body: reads like a thoughtful human reviewer's PR — GitHub-flavored Markdown,
  scannable, evidence-linked (think a clean Linear/GitHub PR).
- README: like a strong OSS infra README (clear diagram up top, metrics table, before/after
  screenshots).

## In-scope surfaces and their rules

### Escalation PR / `escalations/<id>.md`
- Structure (fixed order): **Summary → Failing test+step → Triage verdict → Heal candidates
  (table) → Judge verdict → Before/after a11y diff → Langfuse trace link.**
- Plain language; no emoji-as-icons in headings; fenced code blocks for selectors and diffs.
- Candidate table columns: rank | signal | selector | rationale.

### README
- Top: the two-plane architecture diagram (ASCII or SVG), then the one-line "never mask a
  regression" principle, then the metrics table, then before/after screenshots.
- Use real measured numbers from a run batch — never placeholder/"target" values.

### Langfuse dashboards
- Native Langfuse views; no custom UI to build. Saved view per REQ-011 metric. Screenshot
  these for the README.

## Typography / Color / Spacing / Icons / Motion

- N/A — no custom rendered UI. Markdown + GitHub/Langfuse default rendering only.
- If a metrics image is generated for the README, use a neutral background (not pure `#fff`),
  one accent color for the highlighted metric, and a single sans family — but prefer just
  screenshotting Langfuse rather than building a chart.

## States (artifacts must cover)

- **Healed:** report shows applied selector + confirmation step+assertion both green.
- **Escalated:** PR/artifact with full evidence (the in-scope structure above).
- **Reported (regression):** report artifact stating category, evidence, and explicitly that
  no heal was attempted.
- **Error/degraded:** escalation artifact carrying the diagnostic + trace link.

## Accessibility

- N/A to the agent. The SUT's accessibility tree is an **input signal** for healing, not a
  deliverable we own.
