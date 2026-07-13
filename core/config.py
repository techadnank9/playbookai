"""
Shared config and run state for Playbook AI.

Holds the platform registry (which specialists exist) and a lightweight run
context that agents write findings into. In the full Band build these findings
are posted as room events / Kylon channel messages; this context is the local
mirror that the judge dashboard reads from, so the demo has a single source of
truth even if a platform call hiccups.
"""

import os
from dataclasses import dataclass, field
from typing import Any

# The five platform specialists Scout can recruit. Each has the Nimble query
# angle that makes sense for how GTM actually works on that platform.
PLATFORMS = {
    "linkedin": {
        "display": "LinkedIn",
        "angle": "thought leadership, cadence, employee advocacy, long-form posts",
    },
    "x": {
        "display": "X",
        "angle": "hot takes, reply engagement, threads, real-time relevance",
    },
    "instagram": {
        "display": "Instagram",
        "angle": "visual formats, reels, creator partnerships, aesthetics",
    },
    "tiktok": {
        "display": "TikTok",
        "angle": "short-form trends, creator-led, native/unpolished content",
    },
    "youtube": {
        "display": "YouTube",
        "angle": "long-form value, tutorials, SEO-driven discovery, creators",
    },
}


@dataclass
class Finding:
    """One agent's structured output, posted to the room and the dashboard."""
    agent: str
    platform: str | None
    kind: str  # "profile" | "competitor" | "playbook" | "creator" | "outreach" | "activity"
    data: dict[str, Any]


@dataclass
class RunContext:
    """Everything about one Playbook AI run. The dashboard reads this live."""
    target_url: str
    company_name: str | None = None
    niche: str | None = None
    detected_platforms: list[str] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    run_id: str | None = None
    # Optional InsForgeClient; kept untyped to avoid a hard import cycle.
    store: Any | None = None

    def add(self, finding: Finding) -> None:
        self.findings.append(finding)
        if self.store is not None and self.run_id:
            try:
                self.store.insert_finding(
                    self.run_id,
                    agent=finding.agent,
                    platform=finding.platform,
                    kind=finding.kind,
                    data=finding.data,
                )
            except Exception:
                # Persistence must never crash a run (PRD §10).
                pass

    def activity(
        self,
        agent: str,
        status: str,
        detail: str,
        *,
        platform: str | None = None,
        step: str | None = None,
    ) -> None:
        """Realtime progress event for the run desk (kind=activity)."""
        self.add(
            Finding(
                agent=agent,
                platform=platform,
                kind="activity",
                data={
                    "status": status,  # queued | running | done | failed
                    "detail": detail,
                    "step": step or status,
                },
            )
        )

    def by_kind(self, kind: str) -> list[Finding]:
        return [f for f in self.findings if f.kind == kind]

    def by_platform(self, platform: str) -> list[Finding]:
        return [f for f in self.findings if f.platform == platform]


def load_env() -> dict:
    """Pull sponsor credentials. Missing InsForge keys → memory-only mode."""
    cfg = {
        "nimble_api_key": os.environ.get("NIMBLE_API_KEY"),
        "band_config_path": os.environ.get("BAND_CONFIG", "agent_config.yaml"),
        "llm_provider_key": os.environ.get("ANTHROPIC_API_KEY")
        or os.environ.get("OPENAI_API_KEY"),
        "insforge_project_url": os.environ.get("INSFORGE_PROJECT_URL"),
        "insforge_api_key": os.environ.get("INSFORGE_API_KEY"),
        "insforge_gateway_url": os.environ.get("INSFORGE_GATEWAY_URL"),
        "insforge_gateway_key": os.environ.get("INSFORGE_GATEWAY_KEY"),
        "kylon_api_key": os.environ.get("KYLON_API_KEY"),
    }
    return cfg
