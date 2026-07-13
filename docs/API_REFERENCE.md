# API Reference — confirmed sponsor endpoints

All endpoints below were verified against live documentation. Use these exactly;
do not substitute remembered or guessed endpoints.

---

## Nimble (data spine)

Auth: `Authorization: Bearer <NIMBLE_API_KEY>` on every request.

### Search
```
POST https://nimble-retriever.webit.live/search
Content-Type: application/json

{
  "query": "acme competitors LinkedIn marketing strategy",
  "num_results": 10,
  "deep_search": false,        // true => auto-extracts each result page (costs more)
  "include_answer": false,
  "country": "US",
  "locale": "en"
}
```
Deep search cost: 1 credit per search + 1 per page extracted. Use deep_search
for competitor profiling; fast mode for footprint/creator lookups.

### Extract
```
POST https://sdk.nimbleway.com/v1/extract
Content-Type: application/json

{ "url": "https://acme.com", "render": true, "format": "markdown" }
```

### Python SDK
```python
from nimble_python import Nimble
nimble = Nimble(api_key="...")
result = nimble.extract(url="https://acme.com")
```

Note: response body shapes vary. `core/nimble_client.py::_text_of` handles
multiple shapes defensively; confirm against a real response and adjust once.

Participant grant: 5,000 API credits (sign up at online.nimbleway.com/signup,
create an API key).

---

## Band (coordination)

### Install
```
pip install "band-sdk[anthropic]"    # add extras: [crewai], [langgraph], etc.
```

### Register agents
1. app.band.ai/agents → New Agent → External Agent.
2. Name descriptively (never "Assistant"/"Bot" — LLMs read those as role tokens).
3. Copy the API key immediately (shown once) and the Agent UUID.
4. One block per agent in `agent_config.yaml`:
```yaml
scout:
  agent_id: "uuid-for-scout"
  api_key:  "band-key-for-scout"
linkedin_agent:
  agent_id: "..."
  api_key:  "..."
# ... one per agent
```

### Wire an agent
```python
from thenvoi import Agent
from thenvoi.adapters import AnthropicAdapter
from thenvoi.config import load_agent_config

adapter = AnthropicAdapter(
    model="claude-sonnet-4-6",
    custom_section="You are Scout. Profile the company and recruit specialists.",
    enable_execution_reporting=True,
)
agent_id, api_key = load_agent_config("scout")
agent = Agent.create(adapter=adapter, agent_id=agent_id, api_key=api_key)
await agent.run()   # opens WebSocket, listens
```

### Platform tools (auto-exposed to the LLM)
`thenvoi_send_message`, `thenvoi_send_event`, `thenvoi_add_participant`,
`thenvoi_remove_participant`, `thenvoi_get_participants`, `thenvoi_lookup_peers`,
`thenvoi_create_chatroom`.

Key behaviors: visibility is @mention-scoped (agents only see messages they are
mentioned in; humans see all). Use messages for chat, events for tool
calls/thoughts. Free tier: up to 10 agents, full Agent API + WebSocket.

Dynamic recruiting (the showcase): Scout calls `thenvoi_lookup_peers` then
`thenvoi_add_participant` to pull each platform specialist into the room.

---

## InsForge (backend + model gateway)

Agent-native BaaS. Operated by coding agents via CLI + MCP. Provides Postgres,
auth, storage, edge functions, hosting, and a unified model gateway.

### Build-time provisioning (via InsForge CLI / MCP)
- Provision a project (gets a Postgres DB).
- Create the `runs` and `findings` tables (schema in PRD section 7).
- Agents create/read/write tables directly — no manual dashboard step.

### Model gateway
Unified API gateway to 100+ LLMs (GPT, Claude, Gemini). Route all five LLM seams
through it: one base URL + key instead of per-provider wiring. Confirm the exact
gateway base URL and auth from the InsForge dashboard/CLI at build time (it is
account-specific).

### Notes
- Every primitive returns structured outputs + readable errors (agent-friendly).
- Branching + scoped permissions + reversible writes exist — safe for agent
  operation.
- Best Use of InsForge prize: substantive use = persistence + gateway + hosting.

---

## Kylon (execution)

Base: `https://api.kylon.io`. Auth: `x-api-key: pak_<your_key>`.

### List connections
```
GET /proxy/tools/connections
```

### Search toolkits
```
GET /proxy/tools/search?keywords=gmail&limit=10
```

### Authorize a toolkit
```
POST /proxy/tools/auth
{ "toolkit": "gmail", "redirect_url": "https://example.com/connected" }
```
Response includes a redirect URL; open in a browser to authorize.

### Execute a tool (the send path)
```
POST /proxy/tools/execute
{
  "tool": "GMAIL_SEND_EMAIL",
  "arguments": {
    "to": "person@example.com",
    "subject": "...",
    "body": "..."
  }
}
```

### Proxy a native toolkit request
```
POST /proxy/tools/proxy
{ "toolkit": "github", "method": "GET", "url": "https://api.github.com/user/repos" }
```

For the demo: Outreach produces drafts; `core/kylon_client.py` sends one on
command via `/proxy/tools/execute` with `GMAIL_SEND_EMAIL`. Do not mass-send.
