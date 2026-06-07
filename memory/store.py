"""Keyed JSON heal-memory store (ADR-004).

Persists broken_selector -> fixed_selector so a recurring break replays with zero LLM calls.
Swappable for SQLite/mem0 later behind the same get/put/invalidate interface.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel


class HealMemoryEntry(BaseModel):
    key: str
    fixed_selector: str
    hits: int = 0


def make_key(test_id: str, step_id: str, broken_selector: str) -> str:
    """Stable key for a (test, step, broken selector) triple."""
    return f"{test_id}::{step_id}::{broken_selector}"


class HealMemoryStore:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._data: dict[str, HealMemoryEntry] = {}
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            raw = json.loads(self._path.read_text())
            self._data = {k: HealMemoryEntry(**v) for k, v in raw.items()}

    def _flush(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        serializable = {k: v.model_dump() for k, v in self._data.items()}
        self._path.write_text(json.dumps(serializable, indent=2))

    def get(self, key: str) -> HealMemoryEntry | None:
        return self._data.get(key)

    def put(self, key: str, *, fixed_selector: str) -> None:
        self._data[key] = HealMemoryEntry(key=key, fixed_selector=fixed_selector)
        self._flush()

    def invalidate(self, key: str) -> None:
        if key in self._data:
            del self._data[key]
            self._flush()
