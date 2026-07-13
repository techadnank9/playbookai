"""
Kylon-facing Playbook AI runner (GTM AI Employee challenge port).

Runs the spine, writes a channel-ready action pack, and optionally sends
one outreach draft through Kylon Gmail.

Usage:
  python run_kylon.py https://www.notion.com/
  python run_kylon.py https://www.notion.com/ --send   # needs KYLON_API_KEY + Gmail
  python run_kylon.py https://www.notion.com/ --out out/action_pack.md
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

from core.kylon_client import KylonClient
from core.report import action_pack_json, action_pack_markdown
from run import run

logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
logger = logging.getLogger("playbook.kylon_port")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Playbook AI for Kylon GTM demo")
    parser.add_argument("url", nargs="?", default="https://www.notion.com/")
    parser.add_argument("--out", help="Write markdown action pack to this path")
    parser.add_argument(
        "--send",
        action="store_true",
        help="Send one emailable outreach draft via Kylon Gmail (confirm)",
    )
    parser.add_argument("--json", action="store_true", help="Also print JSON summary")
    args = parser.parse_args()

    ctx = run(args.url)
    md = action_pack_markdown(ctx)

    out_path = Path(args.out) if args.out else ROOT / "out" / f"action_pack_{ctx.run_id or 'local'}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md)
    logger.info("Wrote action pack → %s", out_path)

    # Always print markdown so a Kylon agent can paste it into a channel.
    print(md)

    if args.json:
        print("\n--- JSON ---")
        print(json.dumps(action_pack_json(ctx), indent=2, default=str)[:8000])

    if args.send:
        kylon = KylonClient()
        if not kylon.enabled:
            logger.error("KYLON_API_KEY missing — cannot send")
            return 1
        outreach = [f for f in ctx.findings if f.kind == "outreach"]
        emailable = [
            f
            for f in outreach
            if isinstance((f.data or {}).get("public_contact"), str)
            and "@" in (f.data or {}).get("public_contact", "")
        ]
        pick = (emailable or [None])[0]
        if not pick:
            logger.error("No emailable outreach draft found")
            return 1
        result = kylon.send_outreach_finding(
            pick.data, company=ctx.company_name, confirm=True
        )
        print("\n--- Kylon send ---")
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("ok") else 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
