"""Typed verdict models — the project's invariants live here as validation.

These are the source of truth the tool guards check against (ADR-006): the LLM cannot
route around a constraint that pydantic enforces at construction time.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

TriageCategory = Literal["drift", "regression", "flake", "data"]
HealSignal = Literal["role_name", "text", "nearby_testid", "structural"]


class TriageVerdict(BaseModel):
    category: TriageCategory
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: str


class HealCandidate(BaseModel):
    selector: str
    signal: HealSignal
    rank: int
    rationale: str


class HealProposal(BaseModel):
    # AC-003: a proposal must offer the judge a real choice — at least two candidates.
    candidates: list[HealCandidate] = Field(min_length=2)


class HealVerdict(BaseModel):
    approved: bool
    chosen_selector: str | None
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    step_passed: bool
    assertion_held: bool  # false-heal guard: step green but assertion hollow -> False
