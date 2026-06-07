"""TDD: the assistant-loop conditional edge (ADR-006). Pure, no langgraph import."""

from agent.routing import END, route


class FakeMsg:
    """Minimal stand-in for an AIMessage with/without tool_calls."""

    def __init__(self, tool_calls=None):
        self.tool_calls = tool_calls or []


def test_route_to_end_when_outcome_set_even_if_tool_calls_present():
    state = {"outcome": "healed", "messages": [FakeMsg(tool_calls=[{"name": "apply_fix"}])]}
    assert route(state) == END


def test_route_to_tools_when_last_message_has_tool_calls():
    state = {"outcome": None, "messages": [FakeMsg(tool_calls=[{"name": "classify_triage"}])]}
    assert route(state) == "tools"


def test_route_to_end_when_no_tool_calls():
    state = {"outcome": None, "messages": [FakeMsg(tool_calls=[])]}
    assert route(state) == END


def test_route_to_end_when_no_messages():
    assert route({"outcome": None, "messages": []}) == END
