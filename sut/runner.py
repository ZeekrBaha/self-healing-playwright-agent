"""Live Playwright runner — the real `run_step` boundary the agent graph depends on.

`run_step(selector)` re-runs the failing step with a candidate selector on a real page and
reports (step_passed, assertion_held). The assertion here: after clicking the login control,
the #welcome element becomes visible — a candidate that clicks the wrong element leaves it
hidden, so a false heal is caught (assertion_held=False).
"""

from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright

from sut.capture import capture_failure
from agent.state import FailureSnapshot


class LiveRunner:
    def __init__(self, url: str):
        self.url = url

    def __enter__(self) -> "LiveRunner":
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch()
        self._page = self._browser.new_page()
        return self

    def __exit__(self, *exc) -> None:
        self._browser.close()
        self._pw.stop()

    def capture(self, *, broken_selector: str, failing_step: str) -> FailureSnapshot:
        self._page.goto(self.url)
        return capture_failure(
            self._page,
            failing_step=failing_step,
            broken_selector=broken_selector,
            error_message=f"no node found for selector: {broken_selector}",
        )

    def run_step(self, selector: str) -> tuple[bool, bool]:
        self._page.goto(self.url)
        try:
            self._page.locator(selector).first.click(timeout=1500)
            step_passed = True
        except Exception:  # noqa: BLE001 - any failure to act = step did not pass
            step_passed = False
        assertion_held = bool(step_passed and self._page.locator("#welcome").is_visible())
        return step_passed, assertion_held


def fixture_url(name: str = "login_v2.html") -> str:
    return (Path(__file__).parent / "fixtures" / name).resolve().as_uri()
