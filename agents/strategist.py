"""
Strategist + Outreach: the convergence layer.

Strategist reads every platform agent's playbook from the room and produces:
  - a per-platform action pack (what to post, cadence, gap to exploit)
  - the single biggest cross-platform opportunity

Outreach then turns the recommended creator archetypes (and, secondarily,
prospect targets) into specific reachable people via Nimble: find the public
profile, surface the best reachable channel, and draft the message. It stops at
a drafted message (no live send), which is the demo's deliberate stopping point.

Ethics note baked into the code path: Outreach only surfaces publicly available
professional contact paths, prefers business channels, and never fabricates an
email. If no public contact path exists, it returns the profile + best channel
(often a DM) rather than guessing an address.
"""

import logging
from core.config import RunContext, Finding
from core.nimble_client import NimbleClient, find_creators_for_niche
from core.llm import call_json

logger = logging.getLogger("playbook.strategist")


class Strategist:
    def synthesize(self, ctx: RunContext) -> dict:
        playbooks = ctx.by_kind("playbook")
        # Exclude Strategist's own prior convergence finding if re-run.
        per_platform = {
            pb.platform: pb.data
            for pb in playbooks
            if pb.platform and pb.agent != "Strategist"
        }

        # LLM seam 4: convergence (docs/LLM_SEAMS.md).
        converged = _converge(per_platform, store=ctx.store)
        summary = {
            "company": ctx.company_name,
            "niche": ctx.niche,
            "platforms_analyzed": list(per_platform.keys()),
            "per_platform": per_platform,
            "ranked_recommendations": converged.get("ranked_recommendations") or [],
            "biggest_opportunity": converged.get("biggest_opportunity")
            or _biggest_gap(per_platform),
        }
        ctx.add(Finding(
            agent="Strategist",
            platform=None,
            kind="playbook",
            data={"role": "convergence", **summary},
        ))
        logger.info("Strategist converged %s platforms", len(per_platform))
        return summary


class Outreach:
    def __init__(self, nimble: NimbleClient):
        self.nimble = nimble

    def find_people(self, ctx: RunContext, mode: str = "creators") -> None:
        """
        mode="creators": partnership targets (primary for the demo).
        mode="prospects": ICP employees to sell to (secondary).
        """
        niche = ctx.niche or ""
        for platform in ctx.detected_platforms:
            try:
                if mode == "creators":
                    result = find_creators_for_niche(self.nimble, niche, platform)
                else:
                    result = self.nimble.search(
                        f"{niche} companies decision makers {platform} profiles",
                        num_results=8,
                    )
                people = _parse_people(result, ctx=ctx, platform=platform, mode=mode)
            except Exception as e:
                logger.warning("Outreach search failed on %s: %s", platform, e)
                people = []

            for person in people:
                # Prefer draft embedded by seam 5; else draft separately.
                draft = person.pop("draft", None) or _draft_message(person, ctx, mode)
                # Never fabricate emails: coerce empty/guessed strings to None.
                contact = person.get("public_contact")
                if not contact or not isinstance(contact, str) or "@" not in contact:
                    # Keep non-email contacts (linkedin urls etc) only if clearly public.
                    if contact and isinstance(contact, str) and contact.startswith("http"):
                        pass
                    else:
                        person["public_contact"] = None
                        contact = None
                person_with_msg = {
                    **person,
                    "best_channel": _best_channel(person),
                    "draft": draft,
                    "contact_basis": "public professional profile",
                    "mode": mode,
                }
                ctx.add(Finding(
                    agent="Outreach",
                    platform=platform,
                    kind="outreach",
                    data=person_with_msg,
                ))
        logger.info("Outreach drafted messages for mode=%s", mode)


def _biggest_gap(per_platform: dict) -> str:
    return "LLM: the one platform where competitors win and the target is absent."


def _converge(per_platform: dict, store=None) -> dict:
    """LLM seam 4. Fallback: empty ranked list + stub opportunity."""
    fallback = {"ranked_recommendations": [], "biggest_opportunity": ""}
    if not per_platform:
        return fallback
    # Shrink payloads for the prompt.
    compact = {
        k: {
            "gap": (v or {}).get("gap"),
            "cadence": (v or {}).get("cadence"),
            "winning_content": (v or {}).get("winning_content"),
            "competitor_count": (v or {}).get("competitor_count"),
        }
        for k, v in per_platform.items()
    }
    result = call_json(
        store,
        user=(
            "Schema: {ranked_recommendations: [{platform, priority, why}], "
            "biggest_opportunity: string}\n"
            f"Per-platform playbooks:\n{compact}"
        ),
    )
    if not isinstance(result, dict):
        return fallback
    return {
        "ranked_recommendations": result.get("ranked_recommendations") or [],
        "biggest_opportunity": result.get("biggest_opportunity") or "",
    }


def _parse_people(nimble_result: dict, ctx: RunContext | None = None,
                  platform: str | None = None, mode: str = "creators") -> list[dict]:
    """
    LLM seam 5 (people + draft). Fallback: [].

    Signature keeps (nimble_result) as the first arg so smoke_test can patch it.
    """
    store = getattr(ctx, "store", None) if ctx is not None else None
    raw = ""
    if isinstance(nimble_result, dict):
        raw = str(
            nimble_result.get("answer")
            or nimble_result.get("results")
            or nimble_result.get("data")
            or nimble_result
        )
    else:
        raw = str(nimble_result)
    if not raw.strip():
        return []
    company = getattr(ctx, "company_name", None) if ctx else None
    niche = getattr(ctx, "niche", None) if ctx else None
    result = call_json(
        store,
        user=(
            "Schema: [{name, handle, url, public_contact, draft}]\n"
            "Rules: only publicly available professional contacts; never fabricate "
            "an email — use null for public_contact if unknown. Draft must reference "
            "the specific person and be appropriate to the platform.\n"
            f"Mode: {mode}\nPlatform: {platform}\nCompany: {company}\nNiche: {niche}\n"
            f"Search results:\n{raw[:8000]}"
        ),
    )
    if not isinstance(result, list):
        return []
    people = []
    for item in result:
        if not isinstance(item, dict) or not item.get("name"):
            continue
        people.append(
            {
                "name": str(item.get("name", "")),
                "handle": str(item.get("handle") or ""),
                "url": str(item.get("url") or ""),
                "platform": platform,
                "public_contact": item.get("public_contact"),
                "draft": item.get("draft"),
            }
        )
    return people


def _best_channel(person: dict) -> str:
    """Prefer a listed business email/link-in-bio; fall back to platform DM."""
    if person.get("public_contact"):
        return person["public_contact"]
    return f"{person.get('platform', 'platform')} DM"


def _draft_message(person: dict, ctx: RunContext, mode: str) -> str:
    """LLM seam 5 (draft-only fallback when people parse omitted draft)."""
    result = call_json(
        ctx.store,
        user=(
            "Schema: {\"draft\": string}\n"
            f"Mode: {mode}\nCompany: {ctx.company_name}\nNiche: {ctx.niche}\n"
            f"Person: {person}\n"
            "Write one short ready-to-send outreach message. Do not invent facts."
        ),
    )
    if isinstance(result, dict) and isinstance(result.get("draft"), str):
        return result["draft"]
    who = person.get("name", "there")
    if mode == "creators":
        return f"(draft) Hi {who} — partnership outreach referencing their work + {ctx.company_name}."
    return f"(draft) Hi {who} — outbound referencing {ctx.company_name}'s fit for their team."
