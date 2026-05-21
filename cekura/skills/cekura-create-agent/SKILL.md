---
name: cekura-create-agent
description: >
  Use when the user asks to "create an agent", "set up an agent", "add my agent to Cekura",
  "configure my voice agent", "connect my agent", "set up mock tools", "add tools to my agent",
  "upload knowledge base", "configure integration", "connect VAPI", "connect Retell",
  "connect LiveKit", "connect ElevenLabs", "add dynamic variables", or needs to onboard
  a voice AI agent onto the Cekura platform. Covers the full agent setup flow: project
  selection, provider selection, basics and connection type, description, agent creation,
  mock tools, knowledge base, dynamic variables, and advanced configuration.
license: MIT
compatibility: Requires a Cekura account (https://dashboard.cekura.ai) — sign in via OAuth or use an API key.
metadata:
  author: cekura
  version: "1.0.0"
---

# Cekura Create Agent

Full agent setup flow — **pick provider early, it shapes everything that follows**.

```
Phase 1    Phase 2       Phase 3              Phase 4       Phase 5
Project →  Provider   →  Basics &          →  Description → Create (v2)
Pick the   Which         Connection Type      Full system   POST agent,
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
| 3 | [phase3-basics.md](phase3-basics.md) | Name, language, connection type (phone/WebRTC/chat/SIP), auto-fetch from provider |
| 4 | [phase4-description.md](phase4-description.md) | Collect full system prompt — detailed, covers all flows and edge cases |
| 5 | [phase5-create.md](phase5-create.md) | POST v2 agent; full examples for all providers |
| 6 | [phase6-mock-tools.md](phase6-mock-tools.md) | Auto-fetch or manual API; mock data design rules |
| 7 | [phase7-knowledge-base.md](phase7-knowledge-base.md) | Upload KB files |
| 8 | [phase8-dynamic-variables.md](phase8-dynamic-variables.md) | Register dynamic variables via API (identified during Phase 4) |
| 9 | [phase9-advanced.md](phase9-advanced.md) | Outbound config (auto_dial_outbound, outbound_numbers) |
| 10 | [phase10-verify.md](phase10-verify.md) | Verification checklist + summary + next-skill handoff |

---

## Execution Model — Read This First

This skill executes **one phase at a time, in order**. Do not plan ahead, do not batch phases, do not jump.

**How to execute each phase:**
1. Announce the phase you are starting: "Starting Phase N — [name]"
2. Complete every task in that phase's file
3. Satisfy the gate condition
4. Announce completion: "Phase N complete."
5. Move immediately to Phase N+1 — do not wait for the user to prompt you

**Never do this:**
- Start Phase 4 before Phase 3 is fully complete
- Skip a mandatory phase because it "seems done"
- Stop after Phase 5 because the agent was created
- Bundle multiple phases into one response without completing each
- Ask the user "shall we continue?" between phases — just continue

**Mandatory phases — execute every time, no exceptions:** 1, 2, 3, 4, 5, 10.

**Optional phases — ask before skipping, then move on:** 6 (mock tools), 7 (knowledge base), 8 (dynamic variables), 9 (advanced/outbound). For each optional phase: state its name, ask one question to determine if it applies, then either do it or explicitly mark it skipped and continue.

**If the user has partially completed setup:** ask at the start which phases are done, mark them complete, then begin from the first incomplete phase — but still end at Phase 10.

**Collect conversationally — ask one thing at a time.** Do not dump all questions at once.

---

## API Access

**Prerequisites:** Cekura account + API key or OAuth.

For Claude Code plugin users, platform tools are auto-configured. If platform operations aren't working, run `/setup-mcp` to configure the connection.

For other clients, use the Cekura dashboard or call the API directly with your API key (`X-CEKURA-API-KEY` header).

---

## Reference Files

- **`references/integrations.md`** — Full per-provider field lists, WebSocket message format, custom webhook payload, provider comparison table
- **`references/websocket-server-scaffold.md`** — WebSocket server code scaffolds (Python, Node.js/TS, FastAPI) implementing Cekura's protocol; use when user needs a server generated
- **`references/mock-tool-design.md`** — Per-input branching examples, chain dependency design, append-not-replace pattern
- **`references/api-reference.md`** — Complete agent API endpoints, all field schemas, mock tool and KB endpoints
- **`scripts/upload-agent.sh`** — Curl wrapper for creating/updating agents with large system prompts

**Docs:** https://docs.cekura.ai/documentation/integrations/ | https://docs.cekura.ai/mcp/overview
