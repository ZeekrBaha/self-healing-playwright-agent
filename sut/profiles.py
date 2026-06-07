"""DOM-mutation profiles (Phase 1).

Each profile is a JS snippet injected via Playwright `page.add_init_script(...)`. It runs
before the app's scripts and deterministically breaks selectors in one controlled way, so a
green test turns red in a known manner — the drift the agent must heal.
"""

from __future__ import annotations

# testid-rename: prefix every data-testid so `[data-testid="x"]` no longer resolves.
_TESTID_RENAME = """
(() => {
  const rename = () => document.querySelectorAll('[data-testid]').forEach(el => {
    const v = el.getAttribute('data-testid');
    el.setAttribute('data-testid', 'r_' + v);
  });
  new MutationObserver(rename).observe(document.documentElement, {childList:true, subtree:true});
  document.addEventListener('DOMContentLoaded', rename);
})();
"""

# role-change: strip ARIA roles so role-based locators miss.
_ROLE_CHANGE = """
(() => {
  const strip = () => document.querySelectorAll('[role]').forEach(el => el.removeAttribute('role'));
  new MutationObserver(strip).observe(document.documentElement, {childList:true, subtree:true});
  document.addEventListener('DOMContentLoaded', strip);
})();
"""

# text-change: append a zero-width-ish suffix to button text so exact text locators miss.
_TEXT_CHANGE = """
(() => {
  const tweak = () => document.querySelectorAll('button, a, [role=button]').forEach(el => {
    if (el.dataset._tw) return; el.dataset._tw = '1';
    el.textContent = el.textContent.trim() + '\\u200b';
  });
  new MutationObserver(tweak).observe(document.documentElement, {childList:true, subtree:true});
  document.addEventListener('DOMContentLoaded', tweak);
})();
"""

# structural-wrap: wrap form controls in an extra div so positional/structural locators miss.
_STRUCTURAL_WRAP = """
(() => {
  const wrap = () => document.querySelectorAll('input, button').forEach(el => {
    if (el.parentElement && el.parentElement.dataset._wrap) return;
    const d = document.createElement('div'); d.dataset._wrap = '1';
    el.parentElement && el.parentElement.insertBefore(d, el); d.appendChild(el);
  });
  document.addEventListener('DOMContentLoaded', wrap);
})();
"""

PROFILES: dict[str, str] = {
    "testid-rename": _TESTID_RENAME,
    "role-change": _ROLE_CHANGE,
    "text-change": _TEXT_CHANGE,
    "structural-wrap": _STRUCTURAL_WRAP,
}


def build_init_script(profile: str) -> str:
    """Return the init-script JS for a mutation profile. KeyError if unknown."""
    return PROFILES[profile]
