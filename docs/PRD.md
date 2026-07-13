# Playbook AI — Product Requirements Document

Version 1.0 | Hackathon build ("Build Your Own AI Company", GTM AI Employee track)

---

## 1. What Playbook AI is, in one sentence

Playbook AI is an AI GTM employee: you give it one company URL, and a team of
platform-specialist agents learns that company, studies how its competitors win
on each social platform, and hands back a per-platform action pack — what to
post, which creators to work with, and personalized outreach drafted and ready
to send.

If you read nothing else, read this: the finished product takes a URL as input
and produces a **per-platform action pack** as output. Everything below serves
that one transformation.

---

## 2. Why it exists (the wedge)

Companies pay separately for social strategists, SEO managers, and influencer
agencies. Playbook AI replaces the social-strategy and influencer-outreach slice of
that with an agent team that reverse-engineers what is already winning in a
company's space and executes it. The differentiated insight is *learning the
competitor playbook from public social performance*, then acting on it — not
generic "AI writes posts."

This is deliberately scoped to social GTM (not SEO) for the hackathon: it is the
on-brand, highest-signal slice and it is fully buildable in the time available.

---

## 3. The output we must achieve (definition of done)

The single measure of success: given a real company URL, Playbook AI produces a
**per-platform action pack** containing, for each platform the company should be
active on:

1. **What to post** — 3-5 concrete content angles plus a recommended cadence,
   derived from what is measurably working for competitors on that platform.
2. **The gap to exploit** — one specific thing competitors are doing on that
   platform that the target company is not.
3. **Who to contact** — a shortlist of 3-5 real people (creators to partner with
   as the primary audience; prospects to sell to as the secondary audience),
   each with: name, platform handle, public profile URL, the best public
   channel to reach them, and a **drafted, ready-to-send message** personalized
   to them.

Plus one cross-platform headline: the single biggest opportunity across all
platforms.

The action pack must:
- persist to the InsForge backend (survives a page refresh / new session),
- be viewable in the judge dashboard as a live run,
- have at least the outreach step demonstrably *executable* through Kylon
  (a drafted email can be sent via Kylon's Gmail tool — the demo stops at
  "ready to send" but the send path is wired and provably works).

**Demo acceptance test:** Paste a URL. Within the run, the dashboard shows
platforms detected, competitors found, playbooks per platform, people with
drafted messages, and the cross-platform headline. One outreach draft can be
pushed through the Kylon send path on command.

---

## 4. The four sponsors and their exact roles

Playbook AI is built to win four separate "Best Use of" prizes. Each sponsor has
one clear, non-overlapping job. Do not blur these.

| Sponsor      | Role in Playbook AI                        | What it powers                                                        |
| ------------ | --------------------------------------- | -------------------------------------------------------------------- |
| **Band**     | Multi-agent coordination layer          | Agents register, join a room, route work via @mentions, Scout dynamically recruits the 5 platform specialists |
| **Nimble**   | Live web data spine                     | Every agent calls Nimble to search/extract social + competitor data  |
| **InsForge** | Backend + model gateway                 | Postgres persistence for all run state; model gateway for LLM calls; hosting for the dashboard |
| **Kylon**    | Execution layer                         | Sends the drafted outreach via connected Gmail tool (proxy/tools/execute) |

The narrative: **Nimble gathers → agents reason (Band coordinates, InsForge
gateway serves the models) → InsForge stores → Kylon ships.**

---

## 5. The agent mesh

Seven agents. Four always run; three are recruited on demand (which is the
Band dynamic-recruiting showcase). All agent business logic already exists in
the `agents/` and `core/` spine — this PRD's build job is to wire the four
sponsor integrations around that proven spine.

### Always-on

- **Scout** (`agents/scout.py`) — entry agent. Extracts the target URL via
  Nimble, profiles the company, infers the niche, detects the social footprint,
  and recruits the platform specialists into the Band room.
- **PlatformAgent** (`agents/platform_agent.py`) — one parameterized class
  serving five specialists (LinkedIn, X, Instagram, TikTok, YouTube). Each
  studies the company's presence on its platform, finds competitors there via
  Nimble deep search, and produces a per-platform playbook.
- **Strategist** (`agents/strategist.py`) — reads every platform playbook and
  converges them into the ranked recommendation plus the biggest cross-platform
  gap.
- **Outreach** (`agents/strategist.py`) — finds specific people (creators
  primary, prospects secondary) via Nimble, surfaces public contact paths, and
  drafts the messages.

### Recruited on demand (Band showcase; safe to cut under time pressure)

- **GapHunter** — deep-dives competitor feature/messaging gaps.
- **CreatorMatcher** — expands the creator shortlist with equivalent creators.
- **Reporter** — posts run summaries.

---

## 6. The five LLM seams

The spine fetches real data but does not yet reason over it. There are exactly
five places an LLM call must be wired. All five route through the InsForge model
gateway. Each is marked in code with a clear seam comment.

1. **Scout — company + niche naming.** Input: extracted site content. Output:
   `{company_name, niche}`. (`agents/scout.py`, `_guess_company`/`_guess_niche`)
2. **PlatformAgent — competitor parse.** Input: Nimble deep-search text. Output:
   `[{name, handle, url, note}]`. (`agents/platform_agent.py`, `_parse_competitors`)
3. **PlatformAgent — playbook synthesis.** Input: competitor data + platform
   angle. Output: the `playbook` dict (winning_content, cadence,
   creator_archetypes, gap). (`agents/platform_agent.py`, `analyze`)
4. **Strategist — convergence.** Input: all playbooks. Output: ranked
   recommendation + biggest_opportunity. (`agents/strategist.py`, `_biggest_gap`)
5. **Outreach — people parse + message draft.** Input: Nimble people search.
   Output: `[{name, handle, url, public_contact}]` + a drafted message per
   person. (`agents/strategist.py`, `_parse_people`/`_draft_message`)

Each seam has a strict JSON contract (see `docs/LLM_SEAMS.md`). Prompt the model
to return only JSON, parse defensively, and fall back to an empty structure on
parse failure so a single bad call never crashes a run.

---

## 7. Data model (InsForge Postgres)

One run produces one `run` row and many `finding` rows. The dashboard reads
these. Schema (create via InsForge CLI/MCP at build time):

```
runs
  id            uuid pk
  target_url    text
  company_name  text
  niche         text
  status        text        -- running | complete | failed
  created_at    timestamptz default now()

findings
  id            uuid pk
  run_id        uuid fk -> runs.id
  agent         text        -- Scout | LinkedInAgent | ... | Strategist | Outreach
  platform      text null   -- linkedin | x | instagram | tiktok | youtube | null
  kind          text        -- profile | competitor | playbook | creator | outreach
  data          jsonb       -- the finding payload
  created_at    timestamptz default now()
```

`core/config.py` already defines `RunContext` and `Finding` as the in-memory
mirror of exactly this shape. The persistence task is: after each `ctx.add(...)`,
also insert the finding row into InsForge. Keep the in-memory mirror so the
system degrades gracefully to memory-only if InsForge is unavailable.

---

## 8. Confirmed sponsor API details

These are verified from the live docs (see `docs/API_REFERENCE.md` for full
detail and example calls). Do not guess endpoints — use these.

**Nimble**
- Search: `POST https://nimble-retriever.webit.live/search`, Bearer token.
  Body: `{query, num_results, deep_search, include_answer, country, locale}`.
- Extract: `POST https://sdk.nimbleway.com/v1/extract`, Bearer token.
- Python SDK: `from nimble_python import Nimble`.
- Deep search costs more credits (1 + 1 per page); use it for competitor
  profiling, fast mode elsewhere. Participant grant: 5,000 credits.

**Band**
- SDK: `pip install "band-sdk[anthropic]"` (add extras per framework used).
- Register each agent in the Band UI (app.band.ai/agents), store
  `agent_id` + `api_key` per agent in `agent_config.yaml`.
- Adapter pattern: instantiate an adapter (AnthropicAdapter / CrewAIAdapter),
  pass to `Agent.create(...)`, call `await agent.run()`.
- Platform tools auto-exposed: `thenvoi_send_message`, `thenvoi_add_participant`,
  `thenvoi_lookup_peers`, etc. Free tier: up to 10 agents. Bring your own LLM key.

**InsForge**
- Agent-native BaaS: Postgres, auth, storage, edge functions, hosting, model
  gateway. Operated by coding agents via CLI + MCP.
- Build-time: use the InsForge CLI/MCP to provision the DB and create the two
  tables above. LLM seams route through the InsForge model gateway (unified
  endpoint for Claude/GPT/Gemini).

**Kylon**
- Tools API base: `https://api.kylon.io`, auth header `x-api-key: pak_...`.
- Execute a tool: `POST /proxy/tools/execute` with
  `{tool: "GMAIL_SEND_EMAIL", arguments: {to, subject, body}}`.
- Also: `/proxy/tools/connections` (list), `/proxy/tools/search?keywords=gmail`,
  `/proxy/tools/auth` (authorize toolkit), `/proxy/tools/proxy` (native calls).

---

## 9. Build phases (execute in order, do not skip)

The spine (Scout → 5 platform agents → Strategist → Outreach + Nimble client +
RunContext) already exists and passes `smoke_test.py`. Build on top of it.

**Phase 0 — verify spine.** Run `python smoke_test.py`. It must pass (full
pipeline, no keys needed). Do not modify spine logic; wire integrations around it.

**Phase 1 — InsForge persistence (lowest risk, do first).** Provision InsForge,
create `runs` + `findings` tables. Add a thin `core/insforge_client.py` that
inserts a finding row on every `ctx.add`. Keep in-memory mirror. Verify a run
persists and can be re-read.

**Phase 2 — LLM seams via InsForge gateway.** Wire the five seams (section 6) to
call models through the InsForge model gateway. Now a run on a real URL produces
real reasoning, not stubs. Verify end-to-end on one URL.

**Phase 3 — Nimble live.** Confirm the two Nimble endpoints work with the real
key; adjust `_text_of` parsing in `core/nimble_client.py` to match actual
response bodies. Verify Scout + one platform agent produce real data.

**Phase 4 — Band coordination.** Register the 7 agents, build the adapter layer
so the orchestrator's direct calls become Band room messages/@mentions, and
Scout recruits specialists via `thenvoi_add_participant`. Verify agents appear
and coordinate in a Band room.

**Phase 5 — Kylon execution.** Wire `core/kylon_client.py` to call
`proxy/tools/execute` with `GMAIL_SEND_EMAIL`. Verify one drafted outreach can be
sent on command.

**Phase 6 — dashboard.** Next.js app reading `runs`/`findings` from InsForge,
mirroring a live run: platforms detected, competitors, playbooks, people +
drafts, cross-platform headline. Host on InsForge.

**Phase 7 — demo polish.** One-take flow: paste URL → watch the run populate →
show one send. Seed a fallback company so a flaky network never kills the demo.

---

## 10. Non-negotiable constraints

- **Ethics / contact data:** only surface *publicly available* professional
  contact paths. Prefer business channels. Never fabricate an email; if no public
  contact exists, return the profile + best channel (often a platform DM). Frame
  everything as "learns from public social performance."
- **Outreach stops at drafted messages** by default. The Kylon send path is
  wired and provably works, but the demo does not blast real strangers.
- **Graceful degradation:** if InsForge is down, run in-memory; if a Nimble call
  fails, that agent yields an empty finding, the run continues; if Band is not
  wired yet, the orchestrator runs the mesh directly (as the spine does today).
  No single integration failure may crash a run.
- **Cut order under time pressure:** protect Nimble + the spine + Kylon send +
  the dashboard. Safe to cut, in order: the 3 recruited-on-demand agents → Band
  (fall back to direct orchestration) → InsForge (fall back to in-memory). Each
  cut loses one prize, not the demo.

---

## 11. Tech stack

- **Agents / orchestration:** Python 3.11+, the existing spine, Band SDK.
- **Data:** Nimble APIs.
- **Backend:** InsForge (Postgres, model gateway, hosting).
- **Execution:** Kylon Tools API.
- **Dashboard:** Next.js + TypeScript, reading InsForge.
- **LLM:** routed through InsForge model gateway (Claude/GPT/Gemini).

---

## 12. Repository layout

```
playbook-ai/   (repo folder may still be named ensemble/)
  README.md              -- quickstart
  CLAUDE.md              -- build instructions for Claude Code (read first)
  requirements.txt
  .env.example
  agent_config.yaml.example
  run.py                 -- orchestrator entrypoint
  smoke_test.py          -- zero-dependency pipeline test (Phase 0 gate)
  core/
    __init__.py
    config.py            -- RunContext, Finding, PLATFORMS, load_env
    nimble_client.py     -- Nimble search/extract (real endpoints)
    insforge_client.py   -- TO BUILD (Phase 1)
    kylon_client.py      -- TO BUILD (Phase 5)
    band_adapter.py      -- TO BUILD (Phase 4)
  agents/
    __init__.py
    scout.py
    platform_agent.py
    strategist.py        -- Strategist + Outreach
  dashboard/             -- TO BUILD (Phase 6), Next.js
  docs/
    PRD.md               -- this file
    API_REFERENCE.md
    LLM_SEAMS.md
    diagrams/
      functional_flow.svg
      technical_architecture.svg
```
