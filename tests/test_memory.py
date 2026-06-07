"""TDD: keyed JSON heal-memory store. Backs zero-LLM replay of known fixes (REQ-008)."""

from memory.store import HealMemoryStore, make_key


def test_make_key_is_stable_for_test_step_and_broken_selector():
    k1 = make_key("login_test", "click_submit", "#old")
    k2 = make_key("login_test", "click_submit", "#old")
    assert k1 == k2
    assert make_key("login_test", "click_submit", "#different") != k1


def test_get_unknown_key_returns_none(tmp_path):
    store = HealMemoryStore(tmp_path / "mem.json")
    assert store.get(make_key("t", "s", "#x")) is None


def test_put_then_get_roundtrips_the_fixed_selector(tmp_path):
    store = HealMemoryStore(tmp_path / "mem.json")
    key = make_key("t", "s", "#old")
    store.put(key, fixed_selector="#new")
    entry = store.get(key)
    assert entry is not None
    assert entry.fixed_selector == "#new"


def test_invalidate_removes_the_entry(tmp_path):
    store = HealMemoryStore(tmp_path / "mem.json")
    key = make_key("t", "s", "#old")
    store.put(key, fixed_selector="#new")
    store.invalidate(key)
    assert store.get(key) is None


def test_entries_persist_across_store_instances(tmp_path):
    path = tmp_path / "mem.json"
    HealMemoryStore(path).put(make_key("t", "s", "#old"), fixed_selector="#new")
    reopened = HealMemoryStore(path)
    assert reopened.get(make_key("t", "s", "#old")).fixed_selector == "#new"
