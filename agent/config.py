"""Central config: pinned model ids, thresholds, caps. Determinism lives here (ADR-003)."""

from __future__ import annotations

import os

# Model ids — verified working in scripts/smoke_providers.py (2026-06-06).
MODEL_AGENT = os.environ.get("MODEL_AGENT", "gpt-4o-mini")      # triage + heal (OpenAI)
MODEL_JUDGE = os.environ.get("MODEL_JUDGE", "deepseek-chat")    # judge (DeepSeek)

TEMPERATURE = 0.0  # determinism for stable eval thresholds

# Routing / safety thresholds
TAU = 0.8                      # apply_fix confidence threshold (ADR-005); tune on Phase 7 fixtures
TRIAGE_CONFIDENCE_FLOOR = 0.6  # below this, escalate instead of trusting the triage route

# Loop bounds (REQ-009 cost guardrail + ADR-006 termination)
MAX_HEAL_ATTEMPTS = 3          # LLM-backed heal attempts per run before forced escalate
RECURSION_LIMIT = 25          # LangGraph hard backstop so the loop always terminates
