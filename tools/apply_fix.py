"""apply_fix core (ADR-002): single-match locator replacement + test-dir write guard.

Pure logic here so it is fully testable; the @tool wrapper composes these with the
HealVerdict guard (can_apply) and a dry-run diff before touching disk.
"""

from __future__ import annotations

import difflib
import re
from pathlib import Path

# Matches the contents of a single- or double-quoted string literal (with escapes).
_QUOTED = re.compile(r'"(?:[^"\\]|\\.)*"' r"|'(?:[^'\\]|\\.)*'")


class LocatorNotFound(ValueError):
    """The broken selector was not present inside any string literal."""


class AmbiguousLocator(ValueError):
    """The broken selector appears in more than one literal — refuse rather than guess."""


class OutsideTestDir(ValueError):
    """Refused: apply_fix may only write under the SUT test dir."""


def _quoted_ranges(source: str) -> list[tuple[int, int]]:
    return [(m.start(), m.end()) for m in _QUOTED.finditer(source)]


def replace_locator(source: str, *, broken: str, fixed: str) -> str:
    """Replace `broken` with `fixed` — but only where it occurs INSIDE a quoted string
    literal (a real locator argument), never in comments or surrounding code. Abort on
    0 or >1 such occurrences so we never guess or touch unrelated text.
    """
    ranges = _quoted_ranges(source)
    positions: list[int] = []
    start = 0
    while (i := source.find(broken, start)) != -1:
        end = i + len(broken)
        if any(lo <= i and end <= hi for lo, hi in ranges):
            positions.append(i)
        start = i + 1
    if not positions:
        raise LocatorNotFound(broken)
    if len(positions) > 1:
        raise AmbiguousLocator(f"{broken} appears in {len(positions)} string literals")
    i = positions[0]
    return source[:i] + fixed + source[i + len(broken):]


def make_diff(path: str | Path, before: str, after: str) -> str:
    """Unified diff of a locator patch — written as an artifact before the file is touched."""
    return "".join(difflib.unified_diff(
        before.splitlines(keepends=True), after.splitlines(keepends=True),
        fromfile=f"{path} (before)", tofile=f"{path} (after)",
    ))


def ensure_in_test_dir(target: Path | str, test_dir: Path | str) -> None:
    """Raise OutsideTestDir unless `target` resolves inside `test_dir`."""
    target_p = Path(target).resolve()
    test_dir_p = Path(test_dir).resolve()
    if not target_p.is_relative_to(test_dir_p):
        raise OutsideTestDir(f"{target_p} is not under {test_dir_p}")
