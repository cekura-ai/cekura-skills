# ElevenLabs Mode — Overview

ElevenLabs Conversational AI is a managed provider. Edits to the system prompt and tool definitions go directly to the ElevenLabs API via `ELEVENLABS_API_KEY` and land immediately — no redeploy gate.

## Provider gate

When `assistant_provider == elevenlabs` (compare lowercased), proceed straight to Phase 1.3. No extra confirmation.

ElevenLabs has no squad concept; agents link via `built_in_tools.transfer_to_agent` (targets in its `transfers[].agent_id`). Every agent reachable through these links is in scope — the skill fetches, clones, diagnoses, and edits the whole linked graph together, validating through the registered entry agent (transfers exercise the rest). See [`../../phases/clone.md`](../../phases/clone.md).

## Where the prompt and tools live

The Cekura agent record's `assistant_id` holds the ElevenLabs `agent_id` (shape `agent_<...>`).

- **System prompt** — `conversation_config.agent.prompt.prompt` (single string).
- **Referenced tools** — `conversation_config.agent.prompt.tool_ids` — array of standalone tool IDs; each fetched/edited via `/v1/convai/tools/{tool_id}`.
- **Inline tools (legacy)** — `conversation_config.agent.prompt.tools` — full tool objects embedded on the agent; editable in-place on the agent PATCH.
- **Built-in / system tools** — `conversation_config.agent.prompt.built_in_tools` — `end_call`, `transfer_to_agent`, `transfer_to_number`, `language_detection`, `skip_turn`. Config flags, not free-form definitions; touch only if the user explicitly asks — except `transfer_to_agent.transfers[].agent_id`, which is read to discover linked agents and repointed to the clones during Clone.

The Cekura `description` field is **not** read or written. ElevenLabs is the single source of truth.

## What's editable

| Surface | Editable via | Notes |
|---------|--------------|-------|
| System prompt | `PATCH /v1/convai/agents/{id}` with `conversation_config.agent.prompt.prompt` | Preserve the rest of the `prompt` object (llm, temperature, tool_ids, knowledge_base). |
| Referenced tool (`name`, `description`, `api_schema`/`parameters`) | `PATCH /v1/convai/tools/{tool_id}` with `tool_config.*` | Re-fetch after PATCH to verify. |
| Inline tool (legacy `prompt.tools[i]`) | `PATCH /v1/convai/agents/{id}` with the full `prompt.tools` array | Sent wholesale — preserve all other entries. |
| Tool references on the agent (`prompt.tool_ids`) | `PATCH /v1/convai/agents/{id}` with `conversation_config.agent.prompt.tool_ids` | Send the full new array. |
| New tool creation | `POST /v1/convai/tools` then `PATCH` the agent to add its id to `tool_ids` | Bundle the `tool_ids` update with the agent PATCH. |
| Tool deletion | `DELETE /v1/convai/tools/{tool_id}` | Standalone tools may be referenced by other agents — prefer dropping the reference over deleting. |

## Out of scope

- Spoken `request-start` / `request-complete` / `request-failed` messages and handoff `destinations` — VAPI-only. Fix agent speech issues in the prompt.
- Squad members / per-member prompts — ElevenLabs has no squads.
- TTS / ASR / turn-detection / voice settings — surface to voice-channel filter (Collect Step COLLECT.3).
- Built-in tool toggles — surface as hand-offs unless user asks.
- Dynamic-variable placeholders (`{{...}}`) — owned by the calling system.

## Apply in one sentence

PATCH tools first → POST new tools → PATCH the agent (system prompt + `tool_ids` in one body) → re-fetch every edited surface to confirm → run validation → re-collect → loop or exit. Full curl bodies in `phase-4-apply.md`.

## Anti-patterns

- **Skipping the Step 4.2 re-fetch.** Arrays (`tool_ids`, `prompt.tools`) replace wholesale when included — a malformed body can silently drop references. Always re-fetch and verify.
- **Sending `{"prompt": "..."}` at the top level.** The prompt is nested at `conversation_config.agent.prompt.prompt` — a top-level `prompt` key is ignored and the edit silently no-ops.
- **Editing `{{...}}` placeholders without an explicit user ask.** They're owned by the calling system.
- **Treating ElevenLabs like a VAPI squad.** One agent, one prompt — attribute every prompt-following failure to the single system prompt.
- **Patching a tool's `api_schema` to mask a prompt issue.** If the agent calls a tool wrong, fix the prompt; edit `name` / `description` / `api_schema` only when the tool definition itself is the root cause.
- **Reusing a stale local copy of the prompt / tools across iterations.** Re-fetch at the start of every Fix if more than a few minutes have passed.
- **Editing built-in/system tools as if they were prompt-editable.** They're config flags — surface as hand-offs.

## Files in this directory

- `phase-1-fetch.md` — Required env var, resolving the agent id, agent + tool fetch curl bodies, compact summary template, edge cases.
- `phase-4-apply.md` — PATCH/POST/DELETE curl bodies, tool-backup pattern, re-fetch verification, validation-set construction, loop guardrails.
- `workflow-internals.md` — Workflow (multi-node) agents: node types, edge types, the `transfer_to_agent` dead-end trap, failure-mode signatures, deterministic-bypass principles, PATCH gotchas, ZDR-safe run debugging.
