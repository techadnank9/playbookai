# Playbook AI

A multi-agent pipeline that turns a single company URL into a per-platform GTM (go-to-market) action pack — what to post, where the content gap is, and a drafted outreach message to a relevant creator or prospect.

## What it does

Given a target company URL, a chain of agents runs in sequence:

1. **Scout** extracts the company's site and social footprint (via Nimble), infers its niche, and decides which platform specialists to recruit.
2. **PlatformAgent** (one instance per platform — LinkedIn, X, Instagram, TikTok, YouTube) studies the company's presence on that channel, finds competitors active there, and extracts how those competitors win on that specific channel. Each agent is parameterized by a platform "angle" (e.g. LinkedIn = thought leadership/cadence, TikTok = short-form trends).
3. **Strategist** synthesizes every platform agent's findings into a per-platform action pack (what to post, cadence, the gap to exploit) plus the single biggest cross-platform opportunity.
4. **Outreach** turns the recommended creator/prospect archetypes into specific, reachable people via Nimble — surfacing a public contact channel and drafting a message. It deliberately stops at a draft; it never sends automatically and never fabricates an email address.

Findings from each step are written into a shared `RunContext` and persisted to InsForge, so a dashboard (or a Kylon agent channel) can read a consistent run state even if an individual platform call fails.

There's also a Kylon-facing entry point (`run_kylon.py`) that wraps the same pipeline for a GTM-agent-platform demo, writing a markdown action pack and optionally sending one outreach draft through a connected Gmail account.

## Tech stack

- **Python** — orchestration and agent logic (`core/`, `agents/`)
- **Nimble** — live web extraction and search (company profiling, competitor discovery, creator lookup)
- **InsForge** — run/findings storage, read by the dashboard
- **Kylon** (optional) — agent-channel integration and Gmail send for the outreach draft
- **Next.js / React / Tailwind CSS** — the dashboard (`dashboard/`), a frontend that can trigger and display a run

## Project structure

```
agents/         Scout, PlatformAgent, Strategist (+Outreach)
core/           config, RunContext, Nimble/InsForge/Kylon clients, LLM seam
dashboard/      Next.js frontend
kylon/          setup notes and persona for the Kylon-hosted agent
docs/           API reference, LLM seam notes, PRD, schema
run.py          local, framework-agnostic pipeline runner
run_kylon.py    Kylon-facing runner (writes action pack, optional Gmail send)
```

## Getting started

```bash
pip install -r requirements.txt
python3 run_kylon.py https://company.com/
```

Or run the underlying pipeline directly:

```bash
NIMBLE_API_KEY=... python run.py https://example.com
```

To use the dashboard instead of the CLI:

```bash
cd dashboard && npm install && npm run dev
# http://localhost:3000
```

Requires a `.env` with at least `NIMBLE_API_KEY`. See `kylon/SETUP.md` for wiring up the Kylon agent integration (Nimble secret, Gmail connection, persona).
