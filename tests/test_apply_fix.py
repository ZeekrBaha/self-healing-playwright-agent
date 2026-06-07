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
    make_diff,
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


def test_replace_locator_ignores_matches_outside_quotes():
    # broken selector appears ONLY in a comment -> not a real locator -> abort, don't patch
    src = "# legacy selector #login-old was here\npage.locator('#login-new').click()\n"
    with pytest.raises(LocatorNotFound):
        replace_locator(src, broken="#login-old", fixed="#x")


def test_replace_locator_patches_quoted_occurrence_and_leaves_comment_alone():
    src = "# note: #login-old\npage.locator(\"#login-old\").click()\n"
    out = replace_locator(src, broken="#login-old", fixed="#login-new")
    assert 'page.locator("#login-new")' in out
    assert "# note: #login-old" in out  # the comment is untouched


def test_replace_locator_handles_selector_with_inner_quotes():
    src = "page.locator(\"#login-old\").click()\n"
    out = replace_locator(src, broken="#login-old", fixed="button[aria-label='Login']")
    assert "button[aria-label='Login']" in out


def test_make_diff_shows_before_and_after():
    diff = make_diff("t.py", "page.locator('#a')\n", "page.locator('#b')\n")
    assert "#a" in diff and "#b" in diff
    assert diff.startswith("---") or "@@" in diff


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
