# CLAUDE.md — build instructions for Claude Code

You are building **Playbook AI**, an AI GTM employee. Read `docs/PRD.md` in full
before starting. This file tells you how to proceed autonomously without asking
the user questions.

## Prime directive

Build the product defined in `docs/PRD.md` to its "definition of done" (PRD
section 3): given a company URL, produce a **per-platform action pack** that
persists to InsForge, renders in a dashboard, and whose outreach step is
executable through Kylon.

## How to proceed without asking

- Follow the build phases in PRD section 9 **in order**. Do not skip. Complete
  and verify each phase before the next.
- The spine (Scout → 5 platform agents → Strategist → Outreach, plus the Nimble
  client and RunContext) already exists and passes `smoke_test.py`. Do NOT
  rewrite spine logic. Wire the four sponsor integrations *around* it.
- The five LLM seams are specified in `docs/LLM_SEAMS.md` with exact JSON
  contracts. Implement them to contract.
- Confirmed API endpoints are in `docs/API_REFERENCE.md`. Use them verbatim.
  Never substitute a remembered endpoint.
- When a credential or account-specific value is needed (InsForge gateway URL,
  Band agent UUIDs, Kylon pak key, Nimble key), read it from environment
  variables per `.env.example`. If absent, implement the code path anyway and
  leave the value to be filled at runtime — do not block.
- Make every integration degrade gracefully (PRD section 10). No single
  integration failure may crash a run. This is what lets you build without
  stopping: if Band is not wired yet, the orchestrator runs the mesh directly,
  exactly as the spine does today.

## Decisions already made (do not re-litigate)

- Product name: **Playbook AI**.
- Full mesh: all 5 platform agents.
- Both audiences: creators primary, prospects secondary.
- Outreach stops at drafted messages; Kylon send path wired but not mass-sent.
- Track: GTM AI Employee. Four sponsors, four roles (PRD section 4).
- SEO is explicitly out of scope for this build.

## Verification gates

- Phase 0: `python smoke_test.py` passes (already true on delivery).
- Phase 2: a run on a real URL produces non-stub reasoning in all findings.
- Phase 5: one drafted outreach sends via Kylon on command.
- Phase 6: dashboard shows a live run end to end.

## Order of value if time is short

Protect, in priority order: Nimble + spine, Kylon send, dashboard. Cut, in
order: 3 recruited-on-demand agents → Band (fall back to direct orchestration)
→ InsForge (fall back to in-memory). Each cut loses one prize, not the demo.

## Style

- Keep the spine's clear "LLM seam" comments; replace stubs, keep the seams
  documented.
- Small, testable commits per phase.
- Prefer editing existing files over creating parallel ones.
