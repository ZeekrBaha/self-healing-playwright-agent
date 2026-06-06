"""TDD: error classification (pure). Splits selector-resolution from assertion failures so
detect_failure can tag the snapshot correctly (Phase 1)."""

import pytest

from sut.capture import classify_error


@pytest.mark.parametrize("msg", [
    "locator.click: Timeout 30000ms exceeded waiting for locator(\"#login\")",
    "Error: strict mode violation: locator resolved to 0 elements",
    "no node found for selector: #submit",
])
def test_selector_resolution_errors(msg):
    assert classify_error(msg) == "selector_resolution"


@pytest.mark.parametrize("msg", [
    "AssertionError: expected 'Logged in' to equal 'Error'",
    "expect(received).toHaveText(expected) failed",
])
def test_assertion_errors(msg):
    assert classify_error(msg) == "assertion"


def test_plain_timeout_without_selector_is_timeout():
    assert classify_error("Timeout 5000ms exceeded waiting for navigation") == "timeout"


def test_unknown_is_other():
    assert classify_error("kernel panic") == "other"
