"""
PlatformAgent: one class, five specialists.

Each recruited specialist runs the same job scoped to its platform:
  1. study the target company's presence on this platform
  2. find competitors active here (Nimble deep search)
  3. extract how those competitors win on this specific channel

Parameterizing keeps five agents in sync while the per-platform `angle` from the
config steers the Nimble queries and the eventual LLM analysis toward what
actually matters on that channel (LinkedIn cadence vs TikTok trends, etc).

In the Band build, each instance is a separate registered agent so it shows up
as its own participant in the room and its own Kylon channel. The analyze()
output is posted as a room event and mirrored into RunContext for the dashboard.
"""

import logging
from core.config import RunContext, Finding, PLATFORMS
from core.nimble_client import NimbleClient, find_competitors_on_platform, text_of
from core.llm import call_json

logger = logging.getLogger("playbook.platform")


class PlatformAgent:
    def __init__(self, platform_key: str, nimble: NimbleClient):
        if platform_key not in PLATFORMS:
            raise ValueError(f"Unknown platform {platform_key}")
        self.key = platform_key
        self.meta = PLATFORMS[platform_key]
        self.nimble = nimble

    @property
    def name(self) -> str:
        return f"{self.meta['display']}Agent"

    def analyze(self, ctx: RunContext) -> None:
        company = ctx.company_name or ctx.target_url
        niche = ctx.niche or ""

        # Find competitors and how they operate on this platform.
        try:
            result = find_competitors_on_platform(self.nimble, company, self.meta["display"])
            raw = text_of(result)
            competitors = _parse_competitors(
                raw,
                store=ctx.store,
                company_name=ctx.company_name,
                target_url=ctx.target_url,
            )
        except Exception as e:
            logger.warning("%s competitor search failed: %s", self.name, e)
            if ctx is not None:
                ctx.activity(
                    self.name,
                    "running",
                    f"Competitor search timed out — continuing with empty set ({e.__class__.__name__})",
                    platform=self.key,
                    step="analyze",
                )
            competitors = []

        # Record each competitor as a finding (dashboard renders these).
        for comp in competitors:
            ctx.add(Finding(
                agent=self.name,
                platform=self.key,
                kind="competitor",
                data=comp,
            ))

        # LLM seam 3: playbook synthesis (docs/LLM_SEAMS.md).
        playbook = {
            "platform": self.meta["display"],
            "angle": self.meta["angle"],
            "winning_content": [],
            "cadence": None,
            "creator_archetypes": [],
            "gap": None,
            "competitor_count": len(competitors),
        }
        synthesized = _synthesize_playbook(
            competitors, self.meta["angle"], company, niche, store=ctx.store
        )
        if synthesized:
            for key in ("winning_content", "cadence", "creator_archetypes", "gap"):
                if key in synthesized and synthesized[key] is not None:
                    playbook[key] = synthesized[key]

        ctx.add(Finding(
            agent=self.name,
            platform=self.key,
            kind="playbook",
            data=playbook,
        ))
        logger.info("%s produced playbook (%s competitors)", self.name, len(competitors))


def _parse_competitors(
    raw: str,
    store=None,
    company_name: str | None = None,
    target_url: str | None = None,
) -> list[dict]:
    """LLM seam 2. Fallback: []. Never includes the target company itself."""
    if not raw or not str(raw).strip():
        return []
    exclude = company_name or _hostname(target_url) or "the target company"
    result = call_json(
        store,
        user=(
            "Schema: [{name, handle, url, note}]\n"
            "Extract COMPETITORS (rival companies) active on this social platform "
            "from the research text. Only real rival companies — not partners, "
            "customers, investors, or news outlets.\n"
            f"CRITICAL: Do NOT include the target company itself ({exclude}). "
            "Skip any entry that is the target, a subsidiary, or the same brand.\n"
            f"Research text:\n{str(raw)[:8000]}"
        ),
    )
    if not isinstance(result, list):
        return []
    cleaned = []
    for item in result:
        if not isinstance(item, dict) or not item.get("name"):
            continue
        row = {
            "name": str(item.get("name", "")),
            "handle": str(item.get("handle") or ""),
            "url": str(item.get("url") or ""),
            "note": str(item.get("note") or ""),
        }
        if _is_self(row, company_name=company_name, target_url=target_url):
            continue
        cleaned.append(row)
    return cleaned


def _hostname(url: str | None) -> str:
    if not url:
        return ""
    host = url.split("//")[-1].split("/")[0].lower()
    return host.replace("www.", "")


def _tokens(value: str | None) -> list[str]:
    import re

    if not value:
        return []
    return [t for t in re.sub(r"[^a-z0-9]+", " ", value.lower()).split() if t]


def _brand_roots(company_name: str | None, target_url: str | None) -> set[str]:
    """Canonical brand tokens used to recognize the target (and legal variants)."""
    roots: set[str] = set()
    host = _hostname(target_url)
    if host:
        roots.add(host.split(".")[0])
    tokens = _tokens(company_name)
    # Drop legal / corporate suffixes so "Nebius Group N.V." → nebius
    drop = {
        "group",
        "holding",
        "holdings",
        "inc",
        "llc",
        "ltd",
        "corp",
        "corporation",
        "company",
        "co",
        "nv",
        "n",
        "v",
        "ai",
        "labs",
        "the",
    }
    core = [t for t in tokens if t not in drop and len(t) >= 3]
    if core:
        roots.add(core[0])
        roots.add("".join(core))
    elif tokens:
        roots.add(tokens[0])
    return {r for r in roots if len(r) >= 3}


def _is_self(
    competitor: dict,
    *,
    company_name: str | None,
    target_url: str | None,
) -> bool:
    """True if this competitor row is actually the target company (incl. legal name variants)."""
    import re

    name = (competitor.get("name") or "").strip().lower()
    handle = (competitor.get("handle") or "").strip().lower().lstrip("@")
    handle_alnum = re.sub(r"[^a-z0-9]", "", handle)
    url_l = (competitor.get("url") or "").strip().lower()
    name_tokens = _tokens(name)
    name_alnum = "".join(name_tokens)
    roots = _brand_roots(company_name, target_url)
    target_host = _hostname(target_url)
    comp_host = _hostname(competitor.get("url"))

    brand = (company_name or "").strip().lower()
    if brand:
        if name == brand or name.startswith(brand + " ") or brand.startswith(name + " "):
            return True

    for root in roots:
        if not root:
            continue
        # "Nebius Group N.V.", "Nebius Group", "Nebius AI"
        if name_tokens and name_tokens[0] == root:
            return True
        if root in name_tokens:
            return True
        if name_alnum.startswith(root) and len(name_alnum) <= len(root) + 12:
            return True
        # @nebius, nebius-group, nebius.ai
        if handle_alnum == root or handle_alnum.startswith(root):
            return True
        if handle == root or handle.startswith(root + ".") or handle.startswith(root + "-"):
            return True
        # Only treat LinkedIn company pages for THIS brand as self.
        # Do NOT match article URLs that merely mention the brand
        # (e.g. reddit.com/.../nebius_vs_coreweave for a CoreWeave row).
        if "linkedin.com/company/" in url_l:
            slug = (
                url_l.split("linkedin.com/company/", 1)[-1]
                .split("?", 1)[0]
                .strip("/")
                .split("/")[0]
            )
            slug_alnum = re.sub(r"[^a-z0-9]", "", slug)
            if slug_alnum == root or slug_alnum.startswith(root):
                return True

    # Competitor URL is on the target's own domain.
    if target_host and comp_host:
        if comp_host == target_host or comp_host.endswith("." + target_host):
            return True
        root = target_host.split(".")[0]
        if root and (comp_host == root or comp_host.startswith(root + ".")):
            return True

    return False


def _synthesize_playbook(competitors, angle, company, niche, store=None) -> dict | None:
    """LLM seam 3. Fallback: None (caller keeps empty defaults)."""
    result = call_json(
        store,
        user=(
            "Schema: {winning_content: [string], cadence: string, "
            "creator_archetypes: [string], gap: string}\n"
            f"Target company (not a competitor): {company}\n"
            f"Niche: {niche}\nPlatform angle: {angle}\n"
            f"Competitors: {competitors}\n"
            "Infer what is winning on this platform and the gap for the target company. "
            "Do not treat the target company as a competitor."
        ),
    )
    if not isinstance(result, dict):
        return None
    return result
