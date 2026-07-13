"""
Send one drafted Outreach finding through Kylon (Phase 5).

Usage:
  python send_outreach.py <run_id>                 # dry-run (shows what would send)
  python send_outreach.py <run_id> --confirm       # actually send via Gmail tool
  python send_outreach.py <run_id> --finding <id>  # pick a specific finding uuid
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

from core.insforge_client import InsForgeClient
from core.kylon_client import KylonClient


def main() -> int:
    parser = argparse.ArgumentParser(description="Send one Playbook AI outreach draft via Kylon")
    parser.add_argument("run_id")
    parser.add_argument("--confirm", action="store_true", help="Actually send (default: dry-run)")
    parser.add_argument("--finding", dest="finding_id", help="Specific findings.id to send")
    args = parser.parse_args()

    store = InsForgeClient()
    if not store.enabled:
        print("InsForge not configured; cannot load drafts.", file=sys.stderr)
        return 1

    findings = store.list_findings(args.run_id)
    outreach = [f for f in findings if f.get("kind") == "outreach"]
    if args.finding_id:
        outreach = [f for f in outreach if f.get("id") == args.finding_id]
    # Prefer ones with a real email.
    emailable = [
        f for f in outreach
        if isinstance((f.get("data") or {}).get("public_contact"), str)
        and "@" in (f.get("data") or {}).get("public_contact", "")
    ]
    pick = (emailable or outreach or [None])[0]
    if not pick:
        print("No outreach findings on this run.", file=sys.stderr)
        return 1

    data = pick.get("data") or {}
    print(json.dumps({"finding_id": pick.get("id"), "preview": data}, indent=2, default=str))

    # Pull company from run for subject line if present.
    company = None
    try:
        url = f"{store.project_url}/api/database/records/runs?id=eq.{args.run_id}&select=company_name"
        resp = store._session.get(url, timeout=20)
        if resp.ok:
            rows = resp.json()
            if rows:
                company = rows[0].get("company_name")
    except Exception:
        pass

    kylon = KylonClient()
    result = kylon.send_outreach_finding(data, company=company, confirm=args.confirm)
    print(json.dumps(result, indent=2, default=str))
    return 0 if result.get("ok") or result.get("skipped") else 1


if __name__ == "__main__":
    raise SystemExit(main())
