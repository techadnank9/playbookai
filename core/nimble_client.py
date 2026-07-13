"""
Nimble client for Playbook AI — hackathon (GrowthMasters / Kylon) API shape.

Primary endpoints (from the challenge brief):
  - Search:  POST https://sdk.nimbleway.com/v1/search
  - Extract: POST https://sdk.nimbleway.com/v1/extract  formats=["markdown"]

Legacy retriever URL is kept as a soft fallback if the SDK search fails.
Auth: Authorization: Bearer <NIMBLE_API_KEY>
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import requests

logger = logging.getLogger("playbook.nimble")

SDK_SEARCH_URL = "https://sdk.nimbleway.com/v1/search"
SDK_EXTRACT_URL = "https://sdk.nimbleway.com/v1/extract"
LEGACY_SEARCH_URL = "https://nimble-retriever.webit.live/search"


class NimbleError(Exception):
    pass


class NimbleClient:
    def __init__(self, api_key: str | None = None, default_country: str = "US"):
        self.api_key = api_key or os.environ.get("NIMBLE_API_KEY")
        if not self.api_key:
            raise NimbleError(
                "No Nimble API key. Set NIMBLE_API_KEY or pass api_key=."
            )
        self.default_country = default_country
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
        )

    def _post(self, url: str, payload: dict, retries: int = 1) -> dict:
        last_err = None
        for attempt in range(retries + 1):
            try:
                resp = self._session.post(url, json=payload, timeout=45)
                if resp.status_code == 429:
                    wait = 2 ** attempt
                    logger.warning("Nimble rate limited, backing off %ss", wait)
                    time.sleep(wait)
                    continue
                if resp.status_code >= 400:
                    raise requests.HTTPError(
                        f"{resp.status_code} {resp.text[:300]}", response=resp
                    )
                return resp.json()
            except requests.RequestException as e:
                last_err = e
                logger.warning("Nimble call failed (attempt %s): %s", attempt + 1, e)
                time.sleep(0.5)
        raise NimbleError(f"Nimble request to {url} failed: {last_err}")

    def search(
        self,
        query: str,
        num_results: int = 10,
        deep_search: bool = False,
        include_answer: bool = False,
        country: str | None = None,
        locale: str = "en",
        focus: str = "general",
    ) -> dict:
        """
        Live web search via the Nimble SDK (challenge shape).
        deep_search maps to search_depth=deep; otherwise lite.
        include_answer is ignored on free trial (enterprise-only).
        """
        del include_answer  # not available on free trial
        depth = "deep" if deep_search else "lite"
        payload = {
            "query": query,
            "focus": focus,
            "search_depth": depth,
            "max_results": num_results,
            "country": country or self.default_country,
            "locale": locale,
        }
        logger.info("Nimble search: %r (depth=%s)", query, depth)
        try:
            return self._post(SDK_SEARCH_URL, payload)
        except NimbleError:
            # Soft fallback to legacy retriever body if SDK rejects a field.
            logger.warning("SDK search failed; trying legacy retriever")
            legacy = {
                "query": query,
                "num_results": num_results,
                "deep_search": deep_search,
                "include_answer": False,
                "country": country or self.default_country,
                "locale": locale,
            }
            return self._post(LEGACY_SEARCH_URL, legacy)

    def extract(
        self,
        url: str,
        render_js: bool = True,
        output: str = "markdown",
    ) -> dict:
        """
        Extract clean content from one URL.
        Challenge tip: use formats=["markdown"] (not format="markdown").
        """
        formats = ["markdown"] if output in ("markdown", "md", "json") else [output]
        payload: dict[str, Any] = {"url": url, "formats": formats}
        if render_js:
            payload["render"] = True
        logger.info("Nimble extract: %s formats=%s render=%s", url, formats, render_js)
        return self._post(SDK_EXTRACT_URL, payload)

    def map(self, url: str) -> dict:
        """Discover URLs on a site (challenge Map API)."""
        logger.info("Nimble map: %s", url)
        return self._post("https://sdk.nimbleway.com/v1/map", {"url": url})


def find_social_profiles(client: NimbleClient, company: str) -> dict:
    return client.search(
        f"{company} official social media LinkedIn Twitter Instagram TikTok YouTube",
        num_results=10,
    )


def find_competitors_on_platform(client: NimbleClient, company: str, platform: str) -> dict:
    """Lite search — deep_search timeouts were killing demo runs."""
    return client.search(
        f"{company} competitors {platform} marketing strategy content creators",
        num_results=8,
        deep_search=False,
    )


def find_creators_for_niche(client: NimbleClient, niche: str, platform: str) -> dict:
    return client.search(
        f"top {platform} creators influencers {niche} partnership collaboration",
        num_results=10,
    )


def text_of(nimble_result: dict | Any) -> str:
    """Best-effort readable text from Nimble SDK / legacy bodies."""
    if nimble_result is None:
        return ""
    if isinstance(nimble_result, str):
        return nimble_result
    if not isinstance(nimble_result, dict):
        return str(nimble_result)

    for key in ("answer", "markdown", "text", "html", "content"):
        val = nimble_result.get(key)
        if isinstance(val, str) and val.strip():
            return val

    data = nimble_result.get("data")
    if isinstance(data, str) and data.strip():
        return data
    if isinstance(data, dict):
        for key in ("markdown", "html", "text", "content", "answer", "extracted"):
            val = data.get(key)
            if isinstance(val, str) and val.strip():
                return val
        pages = data.get("pages") or data.get("results")
        if isinstance(pages, list) and pages:
            chunks = []
            for page in pages[:8]:
                if isinstance(page, dict):
                    chunks.append(
                        page.get("markdown")
                        or page.get("text")
                        or page.get("content")
                        or page.get("title")
                        or ""
                    )
                elif isinstance(page, str):
                    chunks.append(page)
            joined = "\n".join(c for c in chunks if c)
            if joined.strip():
                return joined

    results = nimble_result.get("results")
    if isinstance(results, list) and results:
        chunks = []
        for item in results[:12]:
            if isinstance(item, dict):
                title = item.get("title") or ""
                url = item.get("url") or ""
                snippet = (
                    item.get("snippet")
                    or item.get("description")
                    or item.get("content")
                    or item.get("text")
                    or ""
                )
                extract = item.get("extract") or item.get("markdown") or ""
                chunks.append(f"{title} {url}\n{snippet}\n{extract}".strip())
            elif isinstance(item, str):
                chunks.append(item)
        joined = "\n\n".join(c for c in chunks if c)
        if joined.strip():
            return joined

    links = nimble_result.get("links")
    if isinstance(links, list) and links:
        return "\n".join(
            str(x.get("url") if isinstance(x, dict) else x) for x in links[:50]
        )

    return str(nimble_result)[:4000]
