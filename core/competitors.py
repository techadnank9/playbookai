"""
Cross-platform competitor ranking.

Dedupes by company name and returns a single top-N list for the run desk
(not one list per platform).
"""

from __future__ import annotations

from typing import Any

from core.config import Finding, RunContext
from agents.platform_agent import _is_self


def rank_top_competitors(
    ctx: RunContext,
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """
    Merge competitor signals across platforms → unique names → top `limit`.

    Score = platforms mentioned × 10 + note richness. Higher is better.
    """
    buckets: dict[str, dict[str, Any]] = {}

    for f in ctx.findings:
        if f.kind != "competitor":
            continue
        raw = f.data or {}
        name = str(raw.get("name") or "").strip()
        if not name:
            continue
        if _is_self(
            raw,
            company_name=ctx.company_name,
            target_url=ctx.target_url,
        ):
            continue

        key = _norm_name(name)
        if not key:
            continue

        platforms = set()
        if f.platform:
            platforms.add(f.platform)
        existing = buckets.get(key)
        if existing:
            platforms |= set(existing.get("platforms") or [])
            # Keep the richer note / better url.
            note = str(raw.get("note") or "")
            if len(note) > len(str(existing.get("note") or "")):
                existing["note"] = note
            if raw.get("url") and not existing.get("url"):
                existing["url"] = raw.get("url")
            if raw.get("handle") and not existing.get("handle"):
                existing["handle"] = raw.get("handle")
            existing["platforms"] = sorted(platforms)
            existing["score"] = len(platforms) * 10 + min(len(str(existing.get("note") or "")), 80) // 8
            continue

        note = str(raw.get("note") or "")
        buckets[key] = {
            "name": name,
            "handle": str(raw.get("handle") or ""),
            "url": str(raw.get("url") or ""),
            "note": note,
            "platforms": sorted(platforms),
            "score": len(platforms) * 10 + min(len(note), 80) // 8,
        }

    ranked = sorted(buckets.values(), key=lambda r: (-r["score"], r["name"].lower()))
    top = ranked[:limit]
    for i, row in enumerate(top, start=1):
        row["rank"] = i
        # Drop internal score from persisted payload? keep for debug — fine to keep.
    return top


def publish_top_competitors(ctx: RunContext, *, limit: int = 5) -> list[dict[str, Any]]:
    top = rank_top_competitors(ctx, limit=limit)
    ctx.add(
        Finding(
            agent="Strategist",
            platform=None,
            kind="top_competitors",
            data={"competitors": top, "limit": limit},
        )
    )
    return top


def _norm_name(name: str) -> str:
    n = name.strip().lower()
    # Strip corporate noise so "Nebius Group N.V." == "Nebius Group" == "Nebius".
    suffixes = (
        " n.v.",
        " n.v",
        " nv",
        " inc",
        " inc.",
        " llc",
        " ltd",
        " ltd.",
        " plc",
        " corp",
        " corporation",
        " holdings",
        " group",
        " company",
        " co",
        " ai",
        " labs",
    )
    changed = True
    while changed:
        changed = False
        for suffix in suffixes:
            if n.endswith(suffix) and len(n) > len(suffix) + 1:
                n = n[: -len(suffix)].strip()
                changed = True
                break
    return " ".join(n.split())
