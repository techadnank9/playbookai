"""
InsForge persistence + model gateway client.

Persistence: one `runs` row per Playbook AI run, one `findings` row per
`ctx.add(...)`. Uses the InsForge PostgREST-shaped records API:

  POST {base}/api/database/records/{table}

LLM: all five seams route through the project model gateway:

  POST {base}/api/ai/chat/completion

Graceful degradation: if URL/key are missing or any call fails, methods
log and return None / empty so the in-memory spine keeps running.
"""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from typing import Any

import requests

logger = logging.getLogger("playbook.insforge")

DEFAULT_MODEL = os.environ.get("INSFORGE_MODEL", "openai/gpt-4o-mini")


class InsForgeClient:
    def __init__(
        self,
        project_url: str | None = None,
        api_key: str | None = None,
        gateway_url: str | None = None,
        gateway_key: str | None = None,
    ):
        self.project_url = (
            project_url or os.environ.get("INSFORGE_PROJECT_URL") or ""
        ).rstrip("/")
        self.api_key = api_key or os.environ.get("INSFORGE_API_KEY") or ""
        # Gateway can share the project URL + key, or use dedicated overrides.
        self.gateway_url = (
            gateway_url
            or os.environ.get("INSFORGE_GATEWAY_URL")
            or self.project_url
        ).rstrip("/")
        self.gateway_key = (
            gateway_key or os.environ.get("INSFORGE_GATEWAY_KEY") or self.api_key
        )
        self.enabled = bool(self.project_url and self.api_key)
        self._session = requests.Session()
        if self.api_key:
            self._session.headers.update(
                {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "Prefer": "return=representation",
                }
            )

    # ------------------------------------------------------------------ persistence

    def create_run(self, target_url: str) -> str | None:
        """Insert a running row; return run id (or a local uuid if offline)."""
        run_id = str(uuid.uuid4())
        if not self.enabled:
            return run_id
        row = {
            "id": run_id,
            "target_url": target_url,
            "status": "running",
        }
        try:
            data = self._insert("runs", row)
            if data and isinstance(data, list) and data[0].get("id"):
                return data[0]["id"]
            return run_id
        except Exception as e:
            logger.warning("InsForge create_run failed (memory-only): %s", e)
            return run_id

    def update_run(
        self,
        run_id: str,
        *,
        company_name: str | None = None,
        niche: str | None = None,
        status: str | None = None,
    ) -> None:
        if not self.enabled or not run_id:
            return
        patch: dict[str, Any] = {}
        if company_name is not None:
            patch["company_name"] = company_name
        if niche is not None:
            patch["niche"] = niche
        if status is not None:
            patch["status"] = status
        if not patch:
            return
        try:
            url = f"{self.project_url}/api/database/records/runs?id=eq.{run_id}"
            resp = self._session.patch(url, json=patch, timeout=30)
            if resp.status_code >= 400:
                logger.warning(
                    "InsForge update_run %s: %s %s",
                    run_id,
                    resp.status_code,
                    resp.text[:200],
                )
        except Exception as e:
            logger.warning("InsForge update_run failed: %s", e)

    def insert_finding(
        self,
        run_id: str,
        *,
        agent: str,
        platform: str | None,
        kind: str,
        data: dict[str, Any],
    ) -> str | None:
        if not self.enabled or not run_id:
            return None
        row = {
            "id": str(uuid.uuid4()),
            "run_id": run_id,
            "agent": agent,
            "platform": platform,
            "kind": kind,
            "data": data,
        }
        try:
            inserted = self._insert("findings", row)
            if inserted and isinstance(inserted, list):
                return inserted[0].get("id")
            return row["id"]
        except Exception as e:
            logger.warning("InsForge insert_finding failed: %s", e)
            return None

    def list_findings(self, run_id: str) -> list[dict[str, Any]]:
        if not self.enabled:
            return []
        try:
            url = (
                f"{self.project_url}/api/database/records/findings"
                f"?run_id=eq.{run_id}&order=created_at.asc"
            )
            resp = self._session.get(url, timeout=30)
            if resp.status_code >= 400:
                logger.warning(
                    "InsForge list_findings: %s %s",
                    resp.status_code,
                    resp.text[:200],
                )
                return []
            data = resp.json()
            return data if isinstance(data, list) else []
        except Exception as e:
            logger.warning("InsForge list_findings failed: %s", e)
            return []

    def _insert(self, table: str, row: dict[str, Any]) -> Any:
        url = f"{self.project_url}/api/database/records/{table}"
        resp = self._session.post(url, json=[row], timeout=30)
        if resp.status_code >= 400:
            raise RuntimeError(f"{resp.status_code} {resp.text[:300]}")
        if not resp.text:
            return None
        return resp.json()

    # ------------------------------------------------------------------ LLM gateway

    def chat_json(
        self,
        *,
        system: str,
        user: str,
        model: str | None = None,
        temperature: float = 0.2,
    ) -> Any | None:
        """
        Call the InsForge model gateway and parse a JSON-only response.
        Returns None on any failure so seams can apply their fallbacks.
        """
        base = self.gateway_url
        key = self.gateway_key
        if not base or not key:
            return None
        try:
            resp = requests.post(
                f"{base}/api/ai/chat/completion",
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model or DEFAULT_MODEL,
                    "temperature": temperature,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                },
                timeout=90,
            )
            if resp.status_code >= 400:
                logger.warning(
                    "InsForge chat_json: %s %s",
                    resp.status_code,
                    resp.text[:300],
                )
                return None
            body = resp.json()
            text = _completion_text(body)
            return _parse_json_loose(text)
        except Exception as e:
            logger.warning("InsForge chat_json failed: %s", e)
            return None


def _completion_text(body: dict[str, Any]) -> str:
    """Normalize InsForge / OpenAI-shaped completion payloads to plain text."""
    if isinstance(body.get("text"), str):
        return body["text"]
    choices = body.get("choices") or []
    if choices:
        msg = choices[0].get("message") or {}
        content = msg.get("content")
        if isinstance(content, str):
            return content
    return ""


def _parse_json_loose(text: str) -> Any | None:
    if not text:
        return None
    cleaned = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned)
    if fence:
        cleaned = fence.group(1).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Last resort: first {...} or [...] blob.
        m = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", cleaned)
        if not m:
            return None
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            return None
