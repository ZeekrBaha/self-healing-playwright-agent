"""TDD: check_memory / remember_fix — heal_agent's zero-LLM replay tool (REQ-008)."""

from memory.store import HealMemoryStore
from tools.memory_io import check_memory, remember_fix


def test_check_memory_returns_none_on_miss(tmp_path):
    store = HealMemoryStore(tmp_path / "m.json")
    assert check_memory(store, test_id="t", step_id="s", broken_selector="#old") is None


def test_remember_then_check_returns_fixed_selector(tmp_path):
    store = HealMemoryStore(tmp_path / "m.json")
    remember_fix(store, test_id="t", step_id="s", broken_selector="#old", fixed_selector="#new")
    assert check_memory(store, test_id="t", step_id="s", broken_selector="#old") == "#new"


def test_check_memory_is_keyed_by_the_broken_selector(tmp_path):
    store = HealMemoryStore(tmp_path / "m.json")
    remember_fix(store, test_id="t", step_id="s", broken_selector="#old", fixed_selector="#new")
    assert check_memory(store, test_id="t", step_id="s", broken_selector="#different") is None
