---
name: cekura-create-agent
description: >
  Use when the user asks to "create a new agent", "create a main agent", "set up a new agent",
  "set up a main agent", "add my main agent to Cekura", "configure my main agent",
  "connect my main agent", "set up mock tools", "add tools to my agent",
  "upload knowledge base", "configure integration", "connect VAPI", "connect Retell",
  "connect LiveKit", "connect ElevenLabs", "add dynamic variables", or needs to onboard
  a voice AI agent onto the Cekura platform. Covers the full agent setup flow: project
  selection, provider selection, basics and connection type, description, main agent creation,
  mock tools, knowledge base, dynamic variables, and advanced configuration.
license: MIT
compatibility: Requires a Cekura account (https://dashboard.cekura.ai) — sign in via OAuth or use an API key.
metadata:
  author: cekura
  version: "1.3.0"
---

# Cekura Create Agent

Full main agent setup flow — **pick provider early, it shapes everything that follows**.

> **LiveKit / Pipecat note:** keep `provider.type = livekit` or `pipecat` regardless of how Cekura connects (phone, WebRTC, chat). Never reroute a LiveKit/Pipecat agent into `custom` just because it has a phone number — these providers support phone-based simulations and SDK integration natively under their own type. They are also the two **code-based** providers: nothing auto-imports, so Phase 2 checks GitHub, reads the configuration out of the agent's own repo, and creates the agent with placeholder credentials rather than asking for a secret in chat.
>
> `self_hosted` is NOT a valid `provider.type` — the v2 endpoint rejects it. Use `custom`; `self_hosted` survives only as a `chat_agent_details.type`.

```
Standard path (KoreAI, Genesys, Cisco, self-hosted):
Phase 1  → Phase 2  → Phase 3  → Phase 4  → Phase 5  → Phase 6  → Phase 7  → Phase 8  → Phase 9  → Phase 10 → Phase 11
Project    Provider   Basics &   Description  Create     SDK        Mock       KB         Dyn Vars   Advanced   Verify
                      Conn Type               agent     (no-op)     Tools

LiveKit / Pipecat path (Phase 6 wires the Cekura SDK in the user's repo):
Phase 1  → Phase 2  → Phase 3  → Phase 4  → Phase 5  → Phase 6  → Phase 7  → Phase 8  → Phase 9  → Phase 10 → Phase 11
                                                       SDK
                                                       integration

Auto-import path (VAPI / Retell / ElevenLabs / Bland / Synthflow — configure_from_provider: true):
Phase 1  → Phase 2  → Phase 5  → Phase 10 → Phase 11
Project    Provider   Create     Advanced   Verify
           (api_key   (import,   config
           + agent_id) poll
                      progress)
```

## The 11 Phases

| Phase | File | What happens | Standard providers | LiveKit / Pipecat | Auto-import (VAPI/Retell/ElevenLabs/Bland/Synthflow) |
|-------|------|--------------|-------------------|-------------------|------------------------------------------------|
| 1 | [phase1-project.md](phase1-project.md) | List projects, pick `project_id` | **✓ required** | **✓ required** | **✓ required** |
| 2 | [phase2-provider.md](phase2-provider.md) | Choose provider; collect all credentials upfront | **✓ required** | **✓ required** | **✓ required** (api_key + agent_id only) |
| 3 | [phase3-basics.md](phase3-basics.md) | Main agent name, language, connection mode(s) (multi-select for LiveKit/Pipecat) | **✓ required** | **✓ required** | skipped — auto-imported |
| 4 | [phase4-description.md](phase4-description.md) | Collect main agent description — the full system prompt | **✓ required** | **✓ required** | skipped — auto-imported |
| 5 | [phase5-create.md](phase5-create.md) | Create the main agent — POST v2, full provider examples | **✓ required** | **✓ required** | **✓ required** (auto-import path) |
| 6 | [phase6-sdk-integration.md](phase6-sdk-integration.md) | SDK integration in the user's repo (LiveKit / Pipecat only) | no-op | **✓ required** (unless explicitly refused) | no-op |
| 7 | [phase7-mock-tools.md](phase7-mock-tools.md) | Main agent mock tools — auto-fetch (managed provider or self-hosted MCP) or manual | **✓ required** | **✓ required** | skipped — auto-imported |
| 8 | [phase8-knowledge-base.md](phase8-knowledge-base.md) | Main agent knowledge base — upload KB files | **✓ required** | **✓ required** | skipped — auto-imported |
| 9 | [phase9-dynamic-variables.md](phase9-dynamic-variables.md) | Main agent dynamic variables — register via API | **✓ required** | **✓ required** | skipped — auto-imported |
| 10 | [phase10-advanced.md](phase10-advanced.md) | Auto-sync, auto-import calls, outbound config | **✓ required** | **✓ required** | **✓ required** |
| 11 | [phase11-verify.md](phase11-verify.md) | Verify main agent setup — checklist + summary + next-skill handoff | **✓ required** | **✓ required** | **✓ required** |

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
- Skip a phase for a non-auto-import provider because it "seems done"
- Stop after Phase 5 because the main agent was created
- Bundle multiple phases into one response without completing each
- Skip phases for non-auto-import providers (e.g. "phases 7–10 not needed" for LiveKit) — for these providers every phase is mandatory
- Make decisions about a phase without first reading its phase file
- Ask the user "shall we continue?" between phases — just continue
- Give the user a list of steps to do manually — execute them yourself using Bash and API calls
- Offer a placeholder URL or "connect the real server later" as an option — if a WebSocket URL is needed, get a real working one now by running the server and ngrok yourself. **One carve-out, and only one:** LiveKit and Pipecat provider *credentials* are created as marked placeholders on purpose, so that no provider secret is ever typed into a chat — see Phase 2's code-based flow. That is a deliberate mechanism with a verification step attached, not permission to defer a WebSocket URL.

**Do it yourself. Do not instruct.** When something needs to be done — making an API call, updating a field, running a scenario — do it directly using available tools. Do not write out steps for the user to follow. Only ask the user when you genuinely cannot proceed without their input (e.g. a file they need to upload, a decision only they can make).

**Use MCP tools, not raw API calls.** The Cekura MCP server is configured and authenticated. Use it directly for all Cekura platform operations — listing projects, creating agents, registering variables, running scenarios, fetching results. Do not generate curl commands for operations that the MCP server can perform. Raw curl is only a fallback when a specific operation is not available via MCP.

**All 11 phases are mandatory for non-auto-import providers — execute every phase, every time, no exceptions.** Phase 6 (SDK Integration) is a no-op for providers other than LiveKit/Pipecat — announce it and continue. For VAPI, Retell, ElevenLabs, Bland, and Synthflow using `configure_from_provider`, phases 3, 4, 6, 7, 8, and 9 are skipped (the backend imports all of that automatically). The phase files for those phases contain explicit skip instructions — follow them.

**The skill does not end until Phase 11's verification run succeeds.** If the run reveals issues (missing dynamic variables, broken mock tools, wrong connection settings, silent agent), go back to the relevant phase, fix the issue, and retry the run. Never exit before a real conversation is confirmed in the transcript.

**If the user has partially completed setup:** ask at the start which phases are done, mark them complete, then begin from the first incomplete phase — but always end at Phase 11.

**Collect conversationally — ask one thing at a time.** Do not dump all questions at once.

**Never use a field's default value without determining the correct value first.** For every field with a default, actively figure out the right value from code, config, provider API, or context — then confirm it with the user. Only fall back to asking the user directly if it genuinely cannot be determined. Never leave a field at its default because it was easier. A default is a last resort, not a starting point.

**After every inferred decision, explain and confirm.** When you determine a value from code, config, or context — state what you decided, give one line explaining why, and ask the user to confirm before using it. Example: "I'll set language to `multi` — the system prompt contains Hindi-specific instructions alongside English. Does that sound right?" Do not silently commit inferred values.

---

## API Access

**Prerequisites:** Cekura account + API key or OAuth.

For Claude Code plugin users, platform tools are auto-configured. If platform operations aren't working, run `/setup-mcp` to configure the connection.

For other clients, use the Cekura dashboard or call the API directly. **All Cekura API calls use `X-CEKURA-API-KEY: <key>` as the auth header** — never `Authorization: Api-Key` or `Authorization: Bearer`.

---

## Reference Files

- **`references/integrations.md`** — Full per-provider field lists, WebSocket message format, custom webhook payload, provider comparison table
- **`references/livekit-tracing.md`** — LiveKit SDK integration patterns (Python and JS/TS), install versions, `track_session` vs `observe_session`, env vars, common pitfalls
- **`references/pipecat-tracing.md`** — Pipecat SDK integration patterns, single-step vs multi-step API, required aggregators, OTel tracing, deferred upload
- **`references/websocket-server-scaffold.md`** — WebSocket server code scaffolds (Python, Node.js/TS, FastAPI) implementing Cekura's protocol; use when user needs a server generated
- **`references/mock-tool-design.md`** — Per-input branching examples, chain dependency design, append-not-replace pattern
- **`references/api-reference.md`** — Complete main agent API endpoints, all field schemas, mock tool and KB endpoints
- **`scripts/upload-agent.sh`** — Curl wrapper for creating/updating agents with large system prompts

**Docs:** https://docs.cekura.ai/documentation/integrations/ | https://docs.cekura.ai/mcp/overview
