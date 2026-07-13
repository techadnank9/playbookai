"""
Shared helpers for the five LLM seams (docs/LLM_SEAMS.md).

All seams route through InsForgeClient.chat_json. Missing client / parse
failure → None so callers apply their documented fallbacks.
"""

from __future__ import annotations

from typing import Any

SYSTEM = (
    "You are a component in an automated pipeline. Return ONLY valid JSON "
    "matching the schema. No explanation, no markdown."
)


def call_json(store: Any | None, *, user: str) -> Any | None:
    if store is None or not hasattr(store, "chat_json"):
        return None
    return store.chat_json(system=SYSTEM, user=user)
