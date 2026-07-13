"""
Band coordination adapter (Phase 4).

When `agent_config.yaml` has real Band credentials, Scout recruiting and
finding posts can ride Band room messages/@mentions. When Band is absent or
any call fails, the orchestrator keeps the direct mesh (PRD §10 degradation).

This module is intentionally thin: it does not rewrite agent logic. It
exposes helpers the orchestrator can call around the existing spine.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger("playbook.band")

PLATFORM_AGENT_KEYS = {
    "linkedin": "linkedin_agent",
    "x": "x_agent",
    "instagram": "instagram_agent",
    "tiktok": "tiktok_agent",
    "youtube": "youtube_agent",
}


class BandAdapter:
    def __init__(self, config_path: str | None = None):
        path = config_path or os.environ.get("BAND_CONFIG", "agent_config.yaml")
        self.config_path = Path(path)
        self.config: dict[str, Any] = {}
        self.enabled = False
        self._load()

    def _load(self) -> None:
        if not self.config_path.exists():
            logger.info("Band config missing (%s) — direct orchestration", self.config_path)
            return
        try:
            raw = yaml.safe_load(self.config_path.read_text()) or {}
        except Exception as e:
            logger.warning("Band config unreadable: %s", e)
            return
        if not isinstance(raw, dict):
            return
        # Treat placeholder uuids as "not wired yet".
        usable = {
            k: v
            for k, v in raw.items()
            if isinstance(v, dict)
            and v.get("agent_id")
            and not str(v["agent_id"]).startswith("uuid-")
            and v.get("api_key")
            and "band-key" not in str(v.get("api_key"))
        }
        self.config = usable
        self.enabled = bool(usable)
        if self.enabled:
            logger.info("Band adapter ready (%s agents)", len(usable))
        else:
            logger.info("Band config placeholders only — direct orchestration")

    def agent_block(self, name: str) -> dict[str, str] | None:
        return self.config.get(name)

    def platform_agent_name(self, platform_key: str) -> str:
        return PLATFORM_AGENT_KEYS.get(platform_key, platform_key)

    def recruit_note(self, platform_keys: list[str]) -> str:
        """
        Human/judge-facing note of what Band WOULD do. Real
        thenvoi_add_participant wiring lands when SDK + UUIDs are present.
        """
        if not self.enabled:
            return "Band not configured; Scout recruited specialists via direct mesh."
        names = [self.platform_agent_name(k) for k in platform_keys]
        present = [n for n in names if n in self.config]
        return (
            f"Band: would thenvoi_add_participant for {present} "
            f"(config has {list(self.config.keys())})"
        )

    async def run_agent_loop(self, agent_name: str) -> None:
        """
        Optional Band WebSocket loop for a registered external agent.
        Safe no-op when Band SDK / creds are missing.
        """
        block = self.agent_block(agent_name)
        if not block:
            logger.info("Band skip run_agent_loop(%s): no creds", agent_name)
            return
        try:
            from thenvoi import Agent  # type: ignore
            from thenvoi.adapters import AnthropicAdapter  # type: ignore
        except ImportError:
            logger.warning("band-sdk/thenvoi not installed — skip agent loop")
            return
        try:
            adapter = AnthropicAdapter(
                model=os.environ.get("BAND_MODEL", "claude-sonnet-4-6"),
                custom_section=f"You are {agent_name} in the Playbook AI GTM mesh.",
                enable_execution_reporting=True,
            )
            agent = Agent.create(
                adapter=adapter,
                agent_id=block["agent_id"],
                api_key=block["api_key"],
            )
            await agent.run()
        except Exception as e:
            logger.warning("Band agent loop failed for %s: %s", agent_name, e)
