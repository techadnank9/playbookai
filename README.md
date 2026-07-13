# Playbook AI

An AI GTM employee for the GrowthMasters / Kylon + Nimble track.
Give it one company URL → per-platform action pack (posts, gaps, drafted outreach).

## Setup (from the challenge brief)

See [`kylon/SETUP.md`](kylon/SETUP.md). Short version:

1. Claim Kylon credits (invite link in SETUP)
2. Store `NIMBLE_API_KEY` as a Kylon secret
3. Connect Gmail on the agent
4. Paste [`kylon/PERSONA.md`](kylon/PERSONA.md) into the agent Persona

Local `.env` already holds Nimble for the Python engine.

## Run

```bash
pip install -r requirements.txt
python3 run_kylon.py https://company.com/
```

Or use the landing page: start the dashboard and paste a URL.

```bash
cd dashboard && npm run dev
# http://localhost:3000
```

## Architecture

Nimble (live web) → Playbook AI agents + LLM seams → InsForge (runs/findings) →
Kylon channel action pack / Gmail send.
