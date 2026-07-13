"""
Playbook AI orchestrator.

Runs the full loop locally (framework-agnostic) so you can prove the pipeline
before wiring the Band adapters on top:

  Scout.profile -> Scout.recruit -> [PlatformAgent.analyze x5] -> Strategist
  -> Outreach

Usage:
  NIMBLE_API_KEY=... python run.py https://example.com
"""

import sys
import json
import logging
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).resolve().parent / ".env")

from core.config import RunContext, load_env, PLATFORMS
from core.nimble_client import NimbleClient
from core.insforge_client import InsForgeClient
from core.band_adapter import BandAdapter
from agents.scout import Scout
from agents.platform_agent import PlatformAgent
from agents.strategist import Strategist, Outreach

logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
logger = logging.getLogger("playbook")


def run(target_url: str) -> RunContext:
    cfg = load_env()
    nimble = NimbleClient(api_key=cfg["nimble_api_key"])
    store = InsForgeClient(
        project_url=cfg.get("insforge_project_url"),
        api_key=cfg.get("insforge_api_key"),
        gateway_url=cfg.get("insforge_gateway_url"),
        gateway_key=cfg.get("insforge_gateway_key"),
    )
    band = BandAdapter(cfg.get("band_config_path"))
    ctx = RunContext(target_url=target_url, store=store)
    ctx.run_id = store.create_run(target_url)
    # Machine-readable line for the dashboard API (flush before long agent work).
    print(f"PLAYBOOK_RUN_ID={ctx.run_id}", flush=True)
    if store.enabled:
        logger.info("InsForge persistence on (run_id=%s)", ctx.run_id)
    else:
        logger.info("InsForge not configured — memory-only run")
    logger.info("%s", band.recruit_note([]))

    # Seed the live roster so the UI shows agents immediately.
    ctx.activity("Scout", "queued", "Waiting to profile the company", step="queue")
    for key, meta in PLATFORMS.items():
        ctx.activity(
            f"{meta['display']}Agent",
            "queued",
            f"Waiting to be recruited for {meta['display']}",
            platform=key,
            step="queue",
        )
    ctx.activity("Strategist", "queued", "Waiting for platform playbooks", step="queue")
    ctx.activity("Outreach", "queued", "Waiting for Strategist convergence", step="queue")

    try:
        # 1. Scout
        ctx.activity("Scout", "running", "Extracting site + naming company/niche", step="profile")
        scout = Scout(nimble)
        scout.profile_company(ctx)
        store.update_run(
            ctx.run_id,
            company_name=ctx.company_name,
            niche=ctx.niche,
        )
        ctx.activity(
            "Scout",
            "running",
            f"Company identified as {ctx.company_name} — detecting platforms",
            step="recruit",
        )
        recruited = scout.detect_and_recruit(ctx)
        ctx.activity(
            "Scout",
            "done",
            f"Recruited {len(recruited)} platform specialists: {', '.join(recruited)}",
            step="done",
        )
        logger.info("%s", band.recruit_note(recruited))

        # Mark unrecruited platforms as skipped
        for key, meta in PLATFORMS.items():
            if key not in recruited:
                ctx.activity(
                    f"{meta['display']}Agent",
                    "done",
                    "Not recruited for this run",
                    platform=key,
                    step="skipped",
                )

        # 2. Platform specialists
        for key in recruited:
            agent = PlatformAgent(key, nimble)
            ctx.activity(
                agent.name,
                "running",
                f"Searching competitors + synthesizing {agent.meta['display']} playbook",
                platform=key,
                step="analyze",
            )
            agent.analyze(ctx)
            pb = next(
                (
                    f
                    for f in reversed(ctx.findings)
                    if f.kind == "playbook" and f.agent == agent.name
                ),
                None,
            )
            n_comp = (pb.data or {}).get("competitor_count", 0) if pb else 0
            ctx.activity(
                agent.name,
                "done",
                f"Playbook ready ({n_comp} competitors)",
                platform=key,
                step="done",
            )

        # Dedupe + rank a single global top-5 competitor list (not per-platform).
        from core.competitors import publish_top_competitors

        top = publish_top_competitors(ctx, limit=5)
        ctx.activity(
            "Strategist",
            "running",
            f"Ranked top {len(top)} cross-platform competitors",
            step="competitors",
        )

        # 3. Strategist
        ctx.activity(
            "Strategist",
            "running",
            "Converging platform playbooks into ranked recommendations",
            step="synthesize",
        )
        Strategist().synthesize(ctx)
        ctx.activity(
            "Strategist",
            "done",
            "Cross-platform opportunity locked",
            step="done",
        )

        # 4. Outreach
        outreach = Outreach(nimble)
        ctx.activity(
            "Outreach",
            "running",
            "Finding creators + drafting partnership messages",
            step="creators",
        )
        outreach.find_people(ctx, mode="creators")
        ctx.activity(
            "Outreach",
            "running",
            "Finding prospects + drafting outbound messages",
            step="prospects",
        )
        outreach.find_people(ctx, mode="prospects")
        n_out = len(ctx.by_kind("outreach"))
        ctx.activity(
            "Outreach",
            "done",
            f"Drafted {n_out} outreach messages",
            step="done",
        )

        store.update_run(ctx.run_id, status="complete")
    except Exception as e:
        ctx.activity("Orchestrator", "failed", f"Run failed: {e}", step="failed")
        store.update_run(ctx.run_id, status="failed")
        raise

    return ctx


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "https://example.com"
    ctx = run(url)
    print(json.dumps(
        {
            "run_id": ctx.run_id,
            "company": ctx.company_name,
            "niche": ctx.niche,
            "platforms": ctx.detected_platforms,
            "findings": [
                {"agent": f.agent, "platform": f.platform, "kind": f.kind}
                for f in ctx.findings
            ],
        },
        indent=2,
    ))
