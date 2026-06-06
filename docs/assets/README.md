# Assets

Place `langfuse-flow.png` here — a screenshot of one heal run's trace tree in Langfuse
(the `triage` / `propose_candidates` / `judge_heal` spans with cost/latency).

How to capture (no Langfuse MCP in this environment, so this is manual):
1. Run a real heal: `uv run python scripts/demo.py` (creates the trace).
2. Open https://us.cloud.langfuse.com → your project → Tracing → Traces.
3. Open the most recent trace, expand the spans, screenshot → save as `langfuse-flow.png`.

The README references this image in §4.
