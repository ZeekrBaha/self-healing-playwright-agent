"""TDD: apply_fix core logic — single-match replacement + test-dir write guard (ADR-002).

A heal patch must touch exactly one locator occurrence and may only write under the SUT
test dir. 0 or >1 matches => abort (escalate), never a partial/ambiguous edit.
"""

import pytest

from tools.apply_fix import (
    AmbiguousLocator,
    LocatorNotFound,
    OutsideTestDir,
    ensure_in_test_dir,
    replace_locator,
)

SRC = 'page.locator("#login-old").click()\npage.locator("#other").fill("x")\n'


def test_replace_locator_swaps_the_single_occurrence():
    out = replace_locator(SRC, broken="#login-old", fixed="#login-new")
    assert "#login-new" in out
    assert "#login-old" not in out
    assert '#other' in out  # untouched


def test_replace_locator_raises_when_not_found():
    with pytest.raises(LocatorNotFound):
        replace_locator(SRC, broken="#nope", fixed="#x")


def test_replace_locator_raises_when_ambiguous():
    dup = 'a("#dup")\nb("#dup")\n'
    with pytest.raises(AmbiguousLocator):
        replace_locator(dup, broken="#dup", fixed="#x")


def test_ensure_in_test_dir_allows_path_inside(tmp_path):
    test_dir = tmp_path / "sut" / "tests"
    target = test_dir / "login_test.py"
    # should not raise
    ensure_in_test_dir(target, test_dir)


def test_ensure_in_test_dir_blocks_path_outside(tmp_path):
    test_dir = tmp_path / "sut" / "tests"
    outside = tmp_path / "agent" / "graph.py"  # app source — must be refused
    with pytest.raises(OutsideTestDir):
        ensure_in_test_dir(outside, test_dir)
