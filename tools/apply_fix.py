"""apply_fix core (ADR-002): single-match locator replacement + test-dir write guard.

Pure logic here so it is fully testable; the @tool wrapper composes these with the
HealVerdict guard (can_apply) and a dry-run diff before touching disk.
"""

from __future__ import annotations

from pathlib import Path


class LocatorNotFound(ValueError):
    """The broken selector was not present in the source."""


class AmbiguousLocator(ValueError):
    """The broken selector appears more than once — refuse rather than guess."""


class OutsideTestDir(ValueError):
    """Refused: apply_fix may only write under the SUT test dir."""


def replace_locator(source: str, *, broken: str, fixed: str) -> str:
    """Replace exactly one occurrence of `broken` with `fixed`. Abort on 0 or >1."""
    count = source.count(broken)
    if count == 0:
        raise LocatorNotFound(broken)
    if count > 1:
        raise AmbiguousLocator(f"{broken} appears {count} times")
    return source.replace(broken, fixed)


def ensure_in_test_dir(target: Path | str, test_dir: Path | str) -> None:
    """Raise OutsideTestDir unless `target` resolves inside `test_dir`."""
    target_p = Path(target).resolve()
    test_dir_p = Path(test_dir).resolve()
    if not target_p.is_relative_to(test_dir_p):
        raise OutsideTestDir(f"{target_p} is not under {test_dir_p}")
