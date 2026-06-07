"""Task 0 smoke: traced 'hello' through OpenAI (agent) + DeepSeek (judge), verify Langfuse.

Run: uv run python scripts/smoke_providers.py
Makes two tiny chat calls and flushes them to Langfuse. Prints OK/FAIL per provider.
Never prints secrets.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

from langfuse import get_client  # noqa: E402
from langfuse.openai import OpenAI  # noqa: E402  (Langfuse-traced drop-in)

PING = [{"role": "user", "content": "Reply with exactly: OK"}]


def try_openai() -> str:
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    r = client.chat.completions.create(
        model="gpt-4o-mini", messages=PING, max_tokens=5, temperature=0,
        name="smoke-openai-agent",
    )
    return r.choices[0].message.content.strip()


def try_deepseek() -> str:
    client = OpenAI(
        api_key=os.environ["DEEPSEEK_API_KEY"],
        base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    )
    r = client.chat.completions.create(
        model="deepseek-chat", messages=PING, max_tokens=5, temperature=0,
        name="smoke-deepseek-judge",
    )
    return r.choices[0].message.content.strip()


def main() -> None:
    results = {}
    for name, fn in (("OpenAI(agent)", try_openai), ("DeepSeek(judge)", try_deepseek)):
        try:
            results[name] = ("OK", fn())
        except Exception as e:  # noqa: BLE001 - smoke wants the raw provider error
            results[name] = ("FAIL", f"{type(e).__name__}: {e}")

    lf = get_client()
    lf.flush()
    auth = "OK" if lf.auth_check() else "FAIL"

    print("\n=== Provider smoke ===")
    for name, (status, detail) in results.items():
        print(f"  {status:4} {name:18} -> {detail}")
    print(f"  {auth:4} Langfuse auth_check -> host={os.environ.get('LANGFUSE_HOST')}")
    print("\nIf all OK: open Langfuse -> Traces; you should see smoke-openai-agent / smoke-deepseek-judge.")


if __name__ == "__main__":
    main()
