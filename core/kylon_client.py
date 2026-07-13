"""
Kylon client — tools proxy for the GTM AI Employee challenge.

Used for:
  - verifying Gmail / toolkit connections
  - starting OAuth for a toolkit
  - sending one drafted outreach via GMAIL_SEND_EMAIL (confirm required)

Auth: x-api-key: pak_...   OR   Authorization: Bearer pak_...
Env:  KYLON_API_KEY
"""

from __future__ import annotations

import logging
import os
from typing import Any

import requests

logger = logging.getLogger("playbook.kylon")

BASE_URL = "https://api.kylon.io"


class KylonClient:
    def __init__(self, api_key: str | None = None):
        self.api_key = (
            api_key
            or os.environ.get("KYLON_API_KEY")
            or os.environ.get("KYLON_WORKSPACE_API_KEY")
            or ""
        )
        self.enabled = bool(self.api_key)
        self._session = requests.Session()
        if self.api_key:
            self._session.headers.update(
                {
                    "x-api-key": self.api_key,
                    "Content-Type": "application/json",
                }
            )

    def list_connections(self) -> Any:
        return self._get("/proxy/tools/connections")

    def search_toolkits(self, keywords: str = "gmail", limit: int = 10) -> Any:
        return self._get(
            f"/proxy/tools/search?keywords={requests.utils.quote(keywords)}&limit={limit}"
        )

    def start_auth(
        self,
        toolkit: str = "gmail",
        redirect_url: str = "https://example.com/connected",
    ) -> Any:
        return self._post(
            "/proxy/tools/auth",
            {"toolkit": toolkit, "redirect_url": redirect_url},
        )

    def toolkit_details(self, toolkit: str = "gmail") -> Any:
        return self._get(f"/proxy/tools/toolkit/{toolkit}")

    def execute(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if not self.enabled:
            return {"ok": False, "error": "KYLON_API_KEY not configured"}
        try:
            resp = self._session.post(
                f"{BASE_URL}/proxy/tools/execute",
                json={"tool": tool, "arguments": arguments},
                timeout=60,
            )
            if resp.status_code >= 400:
                return {
                    "ok": False,
                    "status": resp.status_code,
                    "error": resp.text[:500],
                }
            return {"ok": True, "result": resp.json() if resp.text else {}}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def send_email(
        self,
        *,
        to: str,
        subject: str,
        body: str,
        confirm: bool = False,
    ) -> dict[str, Any]:
        if not confirm:
            return {
                "ok": False,
                "skipped": True,
                "reason": "confirm=False — drafted only",
            }
        if not to or "@" not in to:
            return {"ok": False, "error": "refusing send: no valid public email"}
        return self.execute(
            "GMAIL_SEND_EMAIL",
            {"to": to, "subject": subject, "body": body},
        )

    def send_outreach_finding(
        self,
        finding_data: dict[str, Any],
        *,
        company: str | None = None,
        confirm: bool = False,
    ) -> dict[str, Any]:
        to = finding_data.get("public_contact") or finding_data.get("best_channel")
        if not isinstance(to, str) or "@" not in to:
            return {
                "ok": False,
                "error": "no public email on finding — cannot send via Gmail",
            }
        name = finding_data.get("name") or "there"
        subject = f"Partnership idea — {company or 'us'} x {name}"
        body = finding_data.get("draft") or ""
        return self.send_email(to=to, subject=subject, body=body, confirm=confirm)

    def _get(self, path: str) -> Any:
        if not self.enabled:
            return None
        try:
            resp = self._session.get(f"{BASE_URL}{path}", timeout=30)
            if resp.status_code >= 400:
                logger.warning("Kylon GET %s: %s %s", path, resp.status_code, resp.text[:200])
                return None
            return resp.json() if resp.text else None
        except Exception as e:
            logger.warning("Kylon GET %s failed: %s", path, e)
            return None

    def _post(self, path: str, body: dict[str, Any]) -> Any:
        if not self.enabled:
            return None
        try:
            resp = self._session.post(f"{BASE_URL}{path}", json=body, timeout=30)
            if resp.status_code >= 400:
                logger.warning("Kylon POST %s: %s %s", path, resp.status_code, resp.text[:200])
                return {"ok": False, "status": resp.status_code, "error": resp.text[:500]}
            return resp.json() if resp.text else {"ok": True}
        except Exception as e:
            logger.warning("Kylon POST %s failed: %s", path, e)
            return {"ok": False, "error": str(e)}
