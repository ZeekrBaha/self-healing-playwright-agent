"""Failure capture (Phase 1).

`classify_error` is pure (keyword rules) so it is unit-tested without a browser.
`capture_failure` builds a FailureSnapshot from a live Playwright page (live test only).
"""

from __future__ import annotations

from agent.state import ErrorClass, FailureSnapshot

# Order matters: assertion check first (an expect failure can mention a selector), then
# selector-resolution, then bare timeout, else other.
_ASSERTION = ("assertionerror", "expect(", ".tohavetext", ".tobevisible", ".toequal")
_SELECTOR = ("strict mode violation", "resolved to 0 elements", "no node found",
             "waiting for locator", "waiting for selector", "no element")
_TIMEOUT = ("timeout",)


def classify_error(message: str) -> ErrorClass:
    m = message.lower()
    if any(k in m for k in _ASSERTION):
        return "assertion"
    if any(k in m for k in _SELECTOR):
        return "selector_resolution"
    if any(k in m for k in _TIMEOUT):
        return "timeout"
    return "other"


def capture_failure(page, *, failing_step: str, broken_selector: str | None, error_message: str) -> FailureSnapshot:
    """Build a snapshot from a live Playwright page. Used by detect_failure in real runs."""
    try:
        dom_html = page.content()
    except Exception:  # noqa: BLE001 - capture must never raise over a degraded page
        dom_html = ""
    try:
        a11y_tree = page.accessibility.snapshot() or {}
    except Exception:  # noqa: BLE001
        a11y_tree = {}
    return FailureSnapshot(
        failing_step=failing_step,
        error_class=classify_error(error_message),
        broken_selector=broken_selector,
        dom_html=dom_html,
        a11y_tree=a11y_tree,
    )
