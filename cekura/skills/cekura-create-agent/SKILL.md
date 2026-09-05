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
  version: "1.2.1"
---

# Cekura Create Agent

Full main agent setup flow — **pick provider early, it shapes everything that follows**.

> **LiveKit / Pipecat note:** keep `provider.type = livekit` or `pipecat` regardless of how Cekura connects (phone, WebRTC, chat). Never reroute a LiveKit/Pipecat agent into `self_hosted` just because it has a phone number — these providers support phone-based simulations and SDK integration natively under their own type.

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
- Offer a placeholder URL or "connect the real server later" as an option — if a WebSocket URL is needed, get a real working one now by running the server and ngrok yourself. **The one exception is the LiveKit/Pipecat dashboard handoff below**, where the three named dummies are required because `aiagents_create` rejects those providers without an api_key and url — and that path is gated: no run happens until `livekit_placeholder_fields` comes back empty.

**Do it yourself. Do not instruct.** When something needs to be done — making an API call, updating a field, running a scenario — do it directly using available tools. Do not write out steps for the user to follow. Only ask the user when you genuinely cannot proceed without their input (e.g. a file they need to upload, a decision only they can make).

**Use MCP tools, not raw API calls.** The Cekura MCP server is configured and authenticated. Use it directly for all Cekura platform operations — listing projects, creating agents, registering variables, running scenarios, fetching results. Do not generate curl commands for operations that the MCP server can perform. Raw curl is only a fallback when a specific operation is not available via MCP.

**All 11 phases are mandatory for non-auto-import providers — execute every phase, every time, no exceptions.** Phase 6 (SDK Integration) is a no-op for providers other than LiveKit/Pipecat — announce it and continue. For VAPI, Retell, ElevenLabs, Bland, and Synthflow using `configure_from_provider`, phases 3, 4, 6, 7, 8, and 9 are skipped (the backend imports all of that automatically). The phase files for those phases contain explicit skip instructions — follow them.

**The skill does not end until Phase 11's verification run succeeds.** If the run reveals issues (missing dynamic variables, broken mock tools, wrong connection settings, silent agent), go back to the relevant phase, fix the issue, and retry the run. Never exit before a real conversation is confirmed in the transcript.

**If the user has partially completed setup:** ask at the start which phases are done, mark them complete, then begin from the first incomplete phase — but always end at Phase 11.

**Collect conversationally — ask one thing at a time.** Do not dump all questions at once. Two carve-outs, so this does not fight the platform's batching rule: a **branch-determining** question (one whose answer decides which other questions exist) is asked ALONE and first; once the branch is known, the fields it requires are batched into ONE clarification rather than dribbled across turns.

### LiveKit / Pipecat: offer GitHub before you ask anything else

**This is the first thing you do after the provider answer — before the connection-mode question, before Phase 3.** It is branch-determining: reading the repo answers most of what the later phases would ask. Full detail (extraction table, credential-manifest rules, report-and-hold) is in [phase2-provider.md](phase2-provider.md) §2a′ — **read that file** — but the offer itself is here because it must not be skipped if you have not.

**Step 1 — `github_list_repos`** (no arguments).

**Not connected → offer to connect, in two beats. Both are `<clarification>` blocks, never prose** — prose does not pause the turn, so a prose offer is a remark the user cannot answer and the flow rolls past it. Never state "no GitHub connection, so I'll collect the details from you" and continue; that skips the offer entirely.

```
<clarification>
{"questions": ["LiveKit and Pipecat agents are code-based — most of what I need (your system prompt, language, and dispatch name) lives in your repo. Want to connect your org's GitHub so I can read it and fill these in for you? Connect it here: <frontend_url>/settings/org/integrations. Otherwise I'll just ask you for them."], "question_types": [null], "options": [["Yes, take me there", "Just ask me instead"]]}
</clarification>
```

On "Yes, take me there", stop again so they have a turn in which to do it:

```
<clarification>
{"questions": ["Open <frontend_url>/settings/org/integrations, install the GitHub App, and pick the repositories you want Cekura to see. Tell me when it's done and I'll pull your agent's setup from the code."], "question_types": [null], "options": [["I've connected it", "Never mind — just ask me"]]}
</clarification>
```

Then **re-run `github_list_repos`** and report what it returns, not what the user claimed.

**The link is `<frontend_url>/settings/org/integrations`**, where `frontend_url` comes from the run context — every environment sets its own dashboard URL, so that value is the correct one. Never substitute another host.

**Connected → offer the scan** (`options: [["Read my repo", "I'll paste it instead"]]`), then pick the repo per §2a′.

### Then create the agent — never ask for credentials in chat

**This handoff is UNCONDITIONAL — it applies whether or not the repo was scanned.** If the user declined GitHub, you still ask them for the name, system prompt and language in chat, then create the agent with the same three dummies and send them to the same page. **Never ask for a LiveKit/Pipecat api_key, api_secret or url in chat on any path.** The scan changes how much you had to ask for; it never changes where the credentials come from.


**Default to WebRTC Automated** unless the repo showed SIP/telephony handling. Say so rather than asking: *"Setting this up as WebRTC Automated — the most common LiveKit setup. Tell me if yours is reached by phone or SIP instead."*

`aiagents_create` with everything the scan found, plus exactly these placeholders (LiveKit/Pipecat reject a create without an api_key and url — the only reason placeholders are allowed here):
`api_key` = `DUMMY_API_KEY`, `url` = `DUMMY_WSS_URL`, and `api_secret` = `DUMMY_SECRET`. All three get a dummy — assume nothing is already set.

Then hand the agent over in the SAME reply, because a placeholder without a link strands the user:

```
<clarification>
{"questions": ["Created your agent: <frontend_url>/agents/<agent_id>. Open it and fill in your LiveKit API key, API secret and server URL there — that way none of your secrets go through this chat. Tell me when they're saved."], "question_types": [null], "options": [["I've saved them", "I'd rather paste them here"]]}
</clarification>
```

**On "I've saved them", `aiagents_retrieve` and read `livekit_placeholder_fields`** (or `pipecat_…`) — never take the word for it. `[]` means all three replaced, proceed. A non-empty list names what is still a dummy: say which ("your server URL is still unset") and re-link. `null` means undeterminable, which is also NOT done. **No evaluators and no run until it returns empty** — a run against a dummy fails in a way that looks like a broken agent.

**Declined at any beat → carry on with the normal asks and never re-offer.**

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
