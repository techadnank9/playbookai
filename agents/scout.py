"""
Scout: the entry agent.

Takes the URL, profiles the company via Nimble (extract the site, search their
social footprint), infers the niche, and decides which platform specialists to
recruit. In the Band build this recruiting is a real thenvoi_lookup_peers +
add_participant call, which is the dynamic-recruiting pattern that anchors the
Best Use of Band story. Here the logic is framework-agnostic so it runs and
tests standalone before we bolt on the Band adapter.
"""

import logging
from core.config import RunContext, Finding, PLATFORMS
from core.nimble_client import NimbleClient, find_social_profiles, text_of
from core.llm import call_json

logger = logging.getLogger("playbook.scout")


class Scout:
    def __init__(self, nimble: NimbleClient):
        self.nimble = nimble

    def profile_company(self, ctx: RunContext) -> None:
        """Extract the target site to learn who they are and what they sell."""
        try:
            result = self.nimble.extract(ctx.target_url)
            content = text_of(result)
        except Exception as e:
            logger.warning("Scout extract failed, continuing with URL only: %s", e)
            content = ""

        # LLM seam 1: company + niche naming (docs/LLM_SEAMS.md).
        named = _name_company(content, ctx.target_url, store=ctx.store)
        ctx.company_name = ctx.company_name or named["company_name"]
        ctx.niche = ctx.niche or named["niche"]

        ctx.add(Finding(
            agent="Scout",
            platform=None,
            kind="profile",
            data={
                "company": ctx.company_name,
                "niche": ctx.niche,
                "source_url": ctx.target_url,
                "content_chars": len(content),
            },
        ))
        logger.info("Scout profiled %s (niche: %s)", ctx.company_name, ctx.niche)

    def detect_and_recruit(self, ctx: RunContext) -> list[str]:
        """
        Search the company's social footprint, decide which platforms are worth
        a specialist, and return the recruit list. In Band this is where
        add_participant fires per chosen platform.
        """
        try:
            result = find_social_profiles(self.nimble, ctx.company_name or ctx.target_url)
            footprint = text_of(result).lower()
        except Exception as e:
            logger.warning("Scout footprint search failed: %s", e)
            footprint = ""

        recruited = []
        for key, meta in PLATFORMS.items():
            # Recruit a platform if the company (or the search) shows presence.
            # Default-recruit all five for the full-mesh demo; the footprint
            # signal is what makes the recruiting look intelligent on stage.
            present = key in footprint or meta["display"].lower() in footprint
            if present or True:  # full-mesh demo: recruit all, flag presence
                recruited.append(key)
                ctx.add(Finding(
                    agent="Scout",
                    platform=key,
                    kind="profile",
                    data={"recruited": True, "has_existing_presence": present},
                ))

        ctx.detected_platforms = recruited
        logger.info("Scout recruited: %s", recruited)
        return recruited


def _guess_company(url: str) -> str:
    host = url.split("//")[-1].split("/")[0].replace("www.", "")
    return host.split(".")[0].capitalize()


def _name_company(content: str, url: str, store=None) -> dict:
    """LLM seam 1. Fallback: hostname + empty niche."""
    fallback = {"company_name": _guess_company(url), "niche": ""}
    if not content.strip():
        return fallback
    result = call_json(
        store,
        user=(
            "Schema: {\"company_name\": string, \"niche\": string}\n"
            f"Source URL: {url}\n"
            f"Extracted site content (truncated):\n{content[:6000]}"
        ),
    )
    if not isinstance(result, dict):
        return fallback
    name = result.get("company_name")
    niche = result.get("niche")
    if not isinstance(name, str) or not name.strip():
        return fallback
    return {
        "company_name": name.strip(),
        "niche": niche.strip() if isinstance(niche, str) else "",
    }
