# LLM Seam Contracts

Five places need an LLM call. Each has a strict JSON contract. Prompt the model
to return ONLY JSON (no prose, no markdown fences), parse defensively, and fall
back to the empty structure on any parse failure so one bad call never crashes a
run. All calls route through the InsForge model gateway.

---

## Seam 1 — Scout: company + niche naming
File: `agents/scout.py` (replaces `_guess_company` / `_guess_niche`)

Input: extracted site content (string, from Nimble extract).
Output:
```json
{ "company_name": "Acme Analytics", "niche": "B2B product analytics SaaS" }
```
Fallback: `{ "company_name": <hostname>, "niche": "" }`

---

## Seam 2 — PlatformAgent: competitor parse
File: `agents/platform_agent.py` (replaces `_parse_competitors`)

Input: Nimble deep-search text for "<company> competitors <platform>".
Output:
```json
[
  { "name": "CompetitorCo", "handle": "@competitorco",
    "url": "https://...", "note": "posts 5x/week, thought-leadership" }
]
```
Fallback: `[]`

---

## Seam 3 — PlatformAgent: playbook synthesis
File: `agents/platform_agent.py` (fills the `playbook` dict in `analyze`)

Input: parsed competitors + the platform's `angle` (from `PLATFORMS` config).
Output:
```json
{
  "winning_content": ["angle 1", "angle 2", "angle 3"],
  "cadence": "4-5 posts/week",
  "creator_archetypes": ["micro-B2B-founder", "technical-educator"],
  "gap": "target posts 0x/week video; competitors lean video hard"
}
```
Fallback: leave the dict fields as their empty defaults.

---

## Seam 4 — Strategist: convergence
File: `agents/strategist.py` (replaces `_biggest_gap`, enriches `synthesize`)

Input: all per-platform playbooks.
Output:
```json
{
  "ranked_recommendations": [
    { "platform": "tiktok", "priority": 1, "why": "biggest gap + high ROI" }
  ],
  "biggest_opportunity": "You have zero TikTok presence; 3 of 4 competitors win there via creators."
}
```
Fallback: `{ "ranked_recommendations": [], "biggest_opportunity": "" }`

---

## Seam 5 — Outreach: people parse + message draft
File: `agents/strategist.py` (replaces `_parse_people` / `_draft_message`)

Input: Nimble people search results + run context (company, niche, platform).
Output (per person):
```json
{
  "name": "Jamie Rivera",
  "handle": "@jamiecreates",
  "url": "https://...",
  "public_contact": "jamie@creates.co",   // or null if none public
  "draft": "Hi Jamie — loved your recent series on ... we're building ... would you be open to ...?"
}
```
Rules: only public professional contacts; prefer business channels; never
fabricate an email (use null → best channel becomes a platform DM). Draft must
reference the specific person and be appropriate to the platform.
Fallback: `[]`

---

## Prompt pattern (apply to all seams)

System: "You are a component in an automated pipeline. Return ONLY valid JSON
matching the schema. No explanation, no markdown."

User: schema + the input data.

Parse: strip any accidental ```json fences, `json.loads`, validate keys, on
failure log + return the fallback.
