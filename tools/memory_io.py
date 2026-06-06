"""Heal tool #1: check_memory / remember_fix — zero-LLM replay of known fixes (REQ-008)."""

from __future__ import annotations

from memory.store import HealMemoryStore, make_key


def check_memory(
    store: HealMemoryStore, *, test_id: str, step_id: str, broken_selector: str
) -> str | None:
    """Return a previously-healed fixed selector for this break, or None."""
    entry = store.get(make_key(test_id, step_id, broken_selector))
    return entry.fixed_selector if entry else None


def remember_fix(
    store: HealMemoryStore,
    *,
    test_id: str,
    step_id: str,
    broken_selector: str,
    fixed_selector: str,
) -> None:
    """Persist a successful heal so the next occurrence replays with no LLM call."""
    store.put(make_key(test_id, step_id, broken_selector), fixed_selector=fixed_selector)
