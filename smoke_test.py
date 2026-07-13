"""
Smoke test: runs the entire Playbook AI pipeline with a fake Nimble client so you
can verify wiring end to end without an API key or spending any credits.

Run:  python smoke_test.py
Expect: a full findings trace across Scout, 5 platform agents, Strategist, Outreach.
"""

import logging
from core.config import RunContext, PLATFORMS
from agents.scout import Scout
from agents.platform_agent import PlatformAgent
from agents.strategist import Strategist, Outreach

logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")


class FakeNimble:
    """Returns plausible shapes so parsing/flow is exercised, no network."""
    def extract(self, url, **kw):
        return {"data": {"markdown": f"Fake site content for {url}. We sell widgets."}}

    def search(self, query, **kw):
        return {"answer": f"Fake results for: {query}",
                "results": [{"title": "CompetitorCo", "url": "https://competitorco.com"}]}


def _fake_people(nimble_result, **_kwargs):
    """Stand-in for the LLM parse seam so the Outreach flow is exercised."""
    return [{"name": "Jamie Rivera", "handle": "@jamiecreates",
             "url": "https://example.com/jamie", "platform": "instagram",
             "public_contact": "jamie@creates.co"}]


def main():
    nimble = FakeNimble()
    ctx = RunContext(target_url="https://acme.example", company_name="Acme", niche="widgets")

    scout = Scout(nimble)
    scout.profile_company(ctx)
    recruited = scout.detect_and_recruit(ctx)
    assert recruited == list(PLATFORMS.keys()), "full mesh should recruit all 5"

    for key in recruited:
        PlatformAgent(key, nimble).analyze(ctx)

    Strategist().synthesize(ctx)

    # Patch the LLM parse seam so Outreach's flow is exercised without a model.
    import agents.strategist as strat
    strat._parse_people = _fake_people

    out = Outreach(nimble)
    out.find_people(ctx, mode="creators")
    out.find_people(ctx, mode="prospects")

    print("\n=== FINDINGS TRACE ===")
    for f in ctx.findings:
        print(f"  [{f.agent:14}] {str(f.platform):10} {f.kind}")

    kinds = {f.kind for f in ctx.findings}
    agents = {f.agent for f in ctx.findings}
    print("\n=== CHECKS ===")
    print("agents seen:", sorted(agents))
    print("kinds seen :", sorted(kinds))
    assert "Strategist" in agents and "Outreach" in agents, "convergence layer must run"
    platform_agents = {a for a in agents if a.endswith("Agent")}
    assert len(platform_agents) == 5, f"expected 5 platform specialists, got {platform_agents}"
    outreach_findings = ctx.by_kind("outreach")
    assert outreach_findings, "Outreach should produce drafted messages"
    assert all("draft" in f.data and "best_channel" in f.data for f in outreach_findings)
    print(f"\nOK: full pipeline ran end to end. "
          f"{len(ctx.findings)} findings, {len(outreach_findings)} outreach drafts.")


if __name__ == "__main__":
    main()
