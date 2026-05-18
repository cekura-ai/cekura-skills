---
name: cekura-create-agent
description: >
  Use when the user asks to "create an agent", "set up an agent", "add my agent to Cekura",
  "configure my voice agent", "connect my agent", "set up mock tools", "add tools to my agent",
  "upload knowledge base", "configure integration", "connect VAPI", "connect Retell",
  "connect LiveKit", "connect ElevenLabs", "add dynamic variables", or needs to onboard
  a voice AI agent onto the Cekura platform. Covers the full agent setup flow: project
  selection, description collection, provider integration, connection type, mock tools,
  knowledge base, dynamic variables, and advanced configuration.
license: MIT
compatibility: Requires a Cekura account (https://dashboard.cekura.ai) — sign in via OAuth or use an API key.
metadata:
  author: cekura
  version: "0.5.0"
---

# Cekura Create Agent

Full agent setup flow — **collect context first, create second, configure incrementally, verify last**.

```
Phase 1    Phase 2    Phase 3       Phase 4    Phase 5     Phase 6
Project →  Basics  →  Description →  Create  →  Provider →  Connection
Pick the   Name,       Full system    POST the   API key +   Phone /
project    language,   prompt or      agent,     assistant   WebRTC /
ID         in/out,     exported       save ID    ID + sync   chat
           number      config                    options

Phase 7        Phase 8     Phase 9     Phase 10    Phase 11
Mock Tools  →  KB      →   Dyn Vars →  Advanced →  Verify
Auto-fetch     Upload      {{var}}     LLM model,  Checklist
or manual      docs +      patterns,   topic/      + summary
curl           halluc.     multi-node  dropoff,    + next steps
               link        pattern     outbound
```

## The 11 Phases

| Phase | File | What happens |
|-------|------|--------------|
| 1 | [phase1-project.md](phase1-project.md) | List projects, pick `project_id` |
| 2 | [phase2-basics.md](phase2-basics.md) | Name, language, inbound/outbound, contact number |
| 3 | [phase3-description.md](phase3-description.md) | Collect full system prompt or exported config |
| 4 | [phase4-create.md](phase4-create.md) | POST the agent; curl fallback for large descriptions |
| 5 | [phase5-provider.md](phase5-provider.md) | Set provider, credentials, auto-fetch/sync options |
| 6 | [phase6-connection.md](phase6-connection.md) | Pick phone / WebRTC / chat / WebSocket |
| 7 | [phase7-mock-tools.md](phase7-mock-tools.md) | Auto-fetch or manual curl; mock data design rules |
| 8 | [phase8-knowledge-base.md](phase8-knowledge-base.md) | Upload KB files; link to hallucination detection |
| 9 | [phase9-dynamic-variables.md](phase9-dynamic-variables.md) | `{{var}}` patterns, multi-node agent guidance |
| 10 | [phase10-advanced.md](phase10-advanced.md) | LLM sim model, topic/dropoff nodes, pronunciation, outbound |
| 11 | [phase11-verify.md](phase11-verify.md) | Checklist, summary, next-skill handoff |

---

## Ground Rules

**Phases are sequential — do not skip.** Each phase has a gate; a gate is satisfied by evidence, not assumption.

**The user may have partially completed setup.** Ask what's already done and skip completed phases.

**Collect conversationally — never dump a form.** Ask for one thing at a time.

**Phases 7–10 are optional** — skip any that don't apply to this agent.

---

## API Access — Cekura MCP Server

Configure MCP:
```bash
claude mcp add --transport http cekura --scope user https://api.cekura.ai/mcp
```

| Tool | Used in |
|------|---------|
| `mcp__cekura__projects_list` | Phase 1 |
| `mcp__cekura__aiagents_create` | Phase 4 (small descriptions) |
| `mcp__cekura__aiagents_partial_update` | Phases 5, 6, 8, 10 |
| `mcp__cekura__aiagents_retrieve` | Phase 11 |
| `mcp__cekura__aiagents_tools_list` | Phase 11 |
| `mcp__cekura__aiagents_upload_knowledge_base` | Phase 8 |
| `Bash` | Phases 4, 7 (curl — MCP limitations below) |

**Known MCP limitations:**
- `aiagents_create` — 414 URI Too Long on descriptions >4 KB. Use curl / `scripts/upload-agent.sh`.
- `aiagents_tools_create` — not exposed by MCP. Always use curl for mock tool creation.

---

## Reference Files

- **`references/integrations.md`** — Full per-provider field lists, `livekit_data` JSON, SIP auth, WebSocket message format, custom webhook payload, provider comparison table
- **`references/mock-tool-design.md`** — Per-input branching examples, chain dependency design, append-not-replace pattern
- **`references/api-reference.md`** — Complete agent API endpoints, all field schemas, mock tool and KB endpoints
- **`scripts/upload-agent.sh`** — Curl wrapper for creating/updating agents with large system prompts

**Docs:** https://docs.cekura.ai/documentation/integrations/ | https://docs.cekura.ai/mcp/overview
