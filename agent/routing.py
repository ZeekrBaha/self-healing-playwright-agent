"""Assistant-loop routing (ADR-006). Kept langgraph-free so it is unit-testable.

`END` mirrors langgraph's sentinel value; graph.py maps it to the real END.
"""

from __future__ import annotations

END = "__end__"


def route(state: dict) -> str:
    """assistant -> tools while the assistant keeps calling tools; -> END when an outcome
    is set (finish()) or the assistant stops emitting tool_calls."""
    if state.get("outcome"):
        return END
    messages = state.get("messages") or []
    if messages and getattr(messages[-1], "tool_calls", None):
        return "tools"
    return END
