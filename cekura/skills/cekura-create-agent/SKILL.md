---
name: cekura-create-agent
description: >
  Use when the user asks to "create an agent", "set up an agent", "add my agent to Cekura",
  "configure my voice agent", "connect my agent", "set up mock tools", "add tools to my agent",
  "upload knowledge base", "configure integration", "connect VAPI", "connect Retell",
  "connect LiveKit", "connect ElevenLabs", "add dynamic variables", or needs to onboard
  a voice AI agent onto the Cekura platform. Covers the full agent setup flow: project
  selection, provider selection, basics, description, agent creation, connection type,
  mock tools, knowledge base, dynamic variables, and advanced configuration.
license: MIT
compatibility: Requires a Cekura account (https://dashboard.cekura.ai) — sign in via OAuth or use an API key.
metadata:
  author: cekura
  version: "0.8.0"
---

# Cekura Create Agent

Full agent setup flow — **pick provider early, it shapes everything that follows**.

```
Phase 1    Phase 2       Phase 3    Phase 4       Phase 5         Phase 6
Project →  Provider   →  Basics  →  Description →  Create (v2)  →  Connection
Pick the   Which         Name,      Full system    POST nested     Phone /
project    provider?     language,  prompt or      provider        WebRTC /
ID         Credentials   in/out,    exported       block,          chat
           collected     phone      config         save ID

Phase 7        Phase 8     Phase 9     Phase 10    Phase 11
Mock Tools  →  KB      →   Dyn Vars →  Advanced →  Verify
Auto-fetch     Upload      {{var}}     Outbound    Checklist
or manual      KB docs     patterns,   config      + summary
curl                       multi-node              + next steps
                           pattern
```

## The 11 Phases

| Phase | File | What happens |
|-------|------|--------------|
| 1 | [phase1-project.md](phase1-project.md) | List projects, pick `project_id` |
| 2 | [phase2-provider.md](phase2-provider.md) | Choose provider; collect all credentials upfront |
| 3 | [phase3-basics.md](phase3-basics.md) | Required fields (name, project) + auto-fetch from provider API |
| 4 | [phase4-description.md](phase4-description.md) | Collect full system prompt — detailed, covers all flows and edge cases |
| 5 | [phase5-create.md](phase5-create.md) | POST v2 agent; full examples for all providers |
| 6 | [phase6-connection.md](phase6-connection.md) | Pick phone / WebRTC / chat / WebSocket |
| 7 | [phase7-mock-tools.md](phase7-mock-tools.md) | Auto-fetch or manual curl; mock data design rules |
| 8 | [phase8-knowledge-base.md](phase8-knowledge-base.md) | Upload KB files |
| 9 | [phase9-dynamic-variables.md](phase9-dynamic-variables.md) | `{{var}}` patterns, multi-node agent guidance |
| 10 | [phase10-advanced.md](phase10-advanced.md) | Outbound config (auto_dial_outbound, outbound_numbers) |
| 11 | [phase11-verify.md](phase11-verify.md) | Verification checklist + summary + next-skill handoff |

---

## Ground Rules

**Phases are sequential — do not skip.** Each phase has a gate; a gate is satisfied by evidence, not assumption.

**Phase 2 (provider) comes before basics** — knowing the provider determines what credentials to collect, which connection modes are available, and which auto-fetch capabilities exist.

**The user may have partially completed setup.** Ask what's already done and skip completed phases.

**Collect conversationally — never dump a form.** Ask for one thing at a time.

**Phases 7–10 are optional** — skip any that don't apply to this agent.

---

## API Access

**Prerequisites:** Cekura account + API key or OAuth.

For Claude Code plugin users, platform tools are auto-configured. If platform operations aren't working, run `/setup-mcp` to configure the connection.

For other clients, use the Cekura dashboard or call the API directly with your API key (`X-CEKURA-API-KEY` header).

---

## Reference Files

- **`references/integrations.md`** — Full per-provider field lists, WebSocket message format, custom webhook payload, provider comparison table
- **`references/mock-tool-design.md`** — Per-input branching examples, chain dependency design, append-not-replace pattern
- **`references/api-reference.md`** — Complete agent API endpoints, all field schemas, mock tool and KB endpoints
- **`scripts/upload-agent.sh`** — Curl wrapper for creating/updating agents with large system prompts

**Docs:** https://docs.cekura.ai/documentation/integrations/ | https://docs.cekura.ai/mcp/overview
