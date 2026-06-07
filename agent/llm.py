"""Traced LLM boundary (ADR-003). All model calls go through here.

OpenAI for the agent (triage/heal), DeepSeek for the judge (OpenAI-API-compatible via
base_url). Langfuse-wrapped drop-in client => every call is traced. temperature=0.
Returns parsed JSON dicts; callers validate into Pydantic models.
"""

from __future__ import annotations

import json
import os

from langfuse.openai import OpenAI  # Langfuse-traced drop-in

from agent import config


def _complete_json(
    messages: list[dict], *, model: str, name: str, api_key: str, base_url: str | None = None
) -> dict:
    client = OpenAI(api_key=api_key, base_url=base_url)
    # `name=` is a Langfuse-drop-in extension (sets the trace span name); the OpenAI type
    # stubs don't know it, so this one call is exempted from the overload check.
    resp = client.chat.completions.create(  # type: ignore[call-overload]
        model=model,
        messages=messages,
        temperature=config.TEMPERATURE,
        response_format={"type": "json_object"},
        name=name,
    )
    return json.loads(resp.choices[0].message.content)


def agent_complete(messages, *, name: str) -> dict:
    """OpenAI — triage + heal."""
    return _complete_json(
        messages, model=config.MODEL_AGENT, name=name, api_key=os.environ["OPENAI_API_KEY"]
    )


def judge_complete(messages, *, name: str) -> dict:
    """DeepSeek — judge (independent vendor)."""
    return _complete_json(
        messages,
        model=config.MODEL_JUDGE,
        name=name,
        api_key=os.environ["DEEPSEEK_API_KEY"],
        base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    )
