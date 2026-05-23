---
name: cekura-create-agent
description: >
  Use when the user asks to "create a main agent", "set up a main agent", "add my main agent to Cekura",
  "configure my main agent", "connect my main agent", "set up mock tools", "add tools to my agent",
  "upload knowledge base", "configure integration", "connect VAPI", "connect Retell",
  "connect LiveKit", "connect ElevenLabs", "add dynamic variables", or needs to onboard
  a voice AI agent onto the Cekura platform. Covers the full agent setup flow: project
  selection, provider selection, basics and connection type, description, main agent creation,
  mock tools, knowledge base, dynamic variables, and advanced configuration.
license: MIT
compatibility: Requires a Cekura account (https://dashboard.cekura.ai) — sign in via OAuth or use an API key.
metadata:
  author: cekura
  version: "1.0.0"
---

# Cekura Create Agent

Full main agent setup flow — **pick provider early, it shapes everything that follows**.

```
Phase 1    Phase 2       Phase 3              Phase 4       Phase 5
Project →  Provider   →  Basics &          →  Description → Create main
Pick the   Which         Connection Type      Full system   POST main agent,
project    provider?     Name, phone/WebRTC/  prompt or     save ID
ID         Credentials   chat, auto-fetch     exported
           collected     from provider        config

Phase 6        Phase 7     Phase 8     Phase 9     Phase 10
Mock Tools  →  KB      →   Dyn Vars →  Advanced →  Verify
Auto-fetch     Upload      {{var}}     Outbound    Checklist
or manual      KB docs     patterns,   config      + summary
               files       multi-node              + next steps
                           pattern
```

## The 10 Phases

| Phase | File | What happens |
|-------|------|--------------|
| 1 | [phase1-project.md](phase1-project.md) | List projects, pick `project_id` |
| 2 | [phase2-provider.md](phase2-provider.md) | Choose provider; collect all credentials upfront |
| 3 | [phase3-basics.md](phase3-basics.md) | Main agent name, language, connection type (phone/WebRTC/chat/SIP), auto-fetch from provider |
| 4 | [phase4-description.md](phase4-description.md) | Collect main agent description — the full system prompt that defines its behaviour |
| 5 | [phase5-create.md](phase5-create.md) | Create the main agent — POST v2, full provider examples |
| 6 | [phase6-mock-tools.md](phase6-mock-tools.md) | Main agent mock tools — auto-fetch or manual |
| 7 | [phase7-knowledge-base.md](phase7-knowledge-base.md) | Main agent knowledge base — upload KB files |
| 8 | [phase8-dynamic-variables.md](phase8-dynamic-variables.md) | Main agent dynamic variables — register via API (identified during Phase 4) |
| 9 | [phase9-advanced.md](phase9-advanced.md) | Outbound config (auto_dial_outbound, outbound_numbers) |
| 10 | [phase10-verify.md](phase10-verify.md) | Verify main agent setup — checklist + summary + next-skill handoff |

---

## What This Skill Does

This skill configures the user's **main agent** — their existing voice/chat AI — on Cekura so it can be tested. The "agent" throughout this skill always refers to the user's production voice/chat AI (the thing being tested), never a new agent being invented. By Phase 4, the main agent's identity, description, and purpose must be fully established. Do not ask "what should this agent do?" after Phase 4 — that was determined from the user's existing code, provider config, or system prompt.

---

## Execution Model — Read This First

This skill executes **one phase at a time, in order**. Do not plan ahead, do not batch phases, do not jump.

**How to execute each phase:**
1. Announce the phase you are starting: "Starting Phase N — [name]"
2. **Read the phase file** — open and follow the instructions in phaseN-*.md. Do not rely on memory of what the phase contains.
3. Complete every task in that phase's file
4. Satisfy the gate condition
5. Announce completion: "Phase N complete."
6. Move immediately to Phase N+1 — do not wait for the user to prompt you

**Never do this:**
- Start Phase 4 before Phase 3 is fully complete
- Skip a mandatory phase because it "seems done"
- Stop after Phase 5 because the main agent was created
- Bundle multiple phases into one response without completing each
- Dismiss multiple phases together (e.g. "phases 6–9 not needed") — each phase must be read and executed individually
- Make decisions about a phase without first reading its phase file
- Ask the user "shall we continue?" between phases — just continue
- Give the user a list of steps to do manually — execute them yourself using Bash and API calls
- Offer a placeholder URL or "connect the real server later" as an option — if a WebSocket URL is needed, get a real working one now by running the server and ngrok yourself

**Do it yourself. Do not instruct.** When something needs to be done — making an API call, updating a field, running a scenario — do it directly using available tools. Do not write out steps for the user to follow. Only ask the user when you genuinely cannot proceed without their input (e.g. a file they need to upload, a decision only they can make).

**Use MCP tools, not raw API calls.** The Cekura MCP server is configured and authenticated. Use it directly for all Cekura platform operations — listing projects, creating agents, registering variables, running scenarios, fetching results. Do not generate curl commands for operations that the MCP server can perform. Raw curl is only a fallback when a specific operation is not available via MCP.

**All 10 phases are mandatory — execute every phase, every time, no exceptions.**

**The skill does not end until Phase 10's verification run succeeds.** If the run reveals issues (missing dynamic variables, broken mock tools, wrong connection settings, silent agent), go back to the relevant phase, fix the issue, and retry the run. Never exit before a real conversation is confirmed in the transcript.

**If the user has partially completed setup:** ask at the start which phases are done, mark them complete, then begin from the first incomplete phase — but always end at Phase 10.

**Collect conversationally — ask one thing at a time.** Do not dump all questions at once.

**Never silently accept a field's default.** When a field has a default value, ask: "does this default make sense for this specific agent's purpose?" before moving on. For example — `language` defaults to `en` but the agent may serve non-English callers; `inbound` defaults to `false` but most agents receive calls; `agent_speaks_first` defaults to null but the agent may always open with a greeting. A default is a fallback, not a recommendation.

**After every inferred decision, explain and confirm.** When you determine a value from code, config, or context — state what you decided, give one line explaining why, and ask the user to confirm before using it. Example: "I'll set language to `multi` — the system prompt contains Hindi-specific instructions alongside English. Does that sound right?" Do not silently commit inferred values.

---

## API Access

**Prerequisites:** Cekura account + API key or OAuth.

For Claude Code plugin users, platform tools are auto-configured. If platform operations aren't working, run `/setup-mcp` to configure the connection.

For other clients, use the Cekura dashboard or call the API directly. **All Cekura API calls use `X-CEKURA-API-KEY: <key>` as the auth header** — never `Authorization: Api-Key` or `Authorization: Bearer`.

---

## Reference Files

- **`references/integrations.md`** — Full per-provider field lists, WebSocket message format, custom webhook payload, provider comparison table
- **`references/websocket-server-scaffold.md`** — WebSocket server code scaffolds (Python, Node.js/TS, FastAPI) implementing Cekura's protocol; use when user needs a server generated
- **`references/mock-tool-design.md`** — Per-input branching examples, chain dependency design, append-not-replace pattern
- **`references/api-reference.md`** — Complete main agent API endpoints, all field schemas, mock tool and KB endpoints
- **`scripts/upload-agent.sh`** — Curl wrapper for creating/updating agents with large system prompts

**Docs:** https://docs.cekura.ai/documentation/integrations/ | https://docs.cekura.ai/mcp/overview
