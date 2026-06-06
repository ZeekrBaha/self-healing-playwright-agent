"""TDD: DOM-mutation profiles (Phase 1). Each profile yields a deterministic addInitScript
JS string that breaks selectors in a controlled way."""

import pytest

from sut.profiles import PROFILES, build_init_script

EXPECTED = {"testid-rename", "role-change", "text-change", "structural-wrap"}


def test_all_four_profiles_exist():
    assert set(PROFILES) == EXPECTED


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_build_init_script_is_nonempty_js_for_each_profile(name):
    js = build_init_script(name)
    assert isinstance(js, str) and len(js) > 0


def test_testid_rename_targets_data_testid():
    assert "data-testid" in build_init_script("testid-rename")


def test_unknown_profile_raises():
    with pytest.raises(KeyError):
        build_init_script("does-not-exist")
