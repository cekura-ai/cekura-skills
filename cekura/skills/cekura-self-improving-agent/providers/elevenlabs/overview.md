# ElevenLabs Mode — Overview

ElevenLabs Conversational AI is a managed provider this skill can PATCH end-to-end against the live agent, the same way it can for VAPI. The system prompt and tool definitions are editable via the ElevenLabs API using `ELEVENLABS_API_KEY`. Edits land immediately; the live agent picks them up on the next conversation — there is no redeploy gate.

This mode is a "fast path" alongside VAPI — full closed-loop iteration without redeploy gates, file edits, or paste round-trips.

Use this reference together with the main SKILL.md.

## ElevenLabs-mode gate (Phase 1.2)

When `assistant_provider == elevenlabs`, no extra confirmation needed — proceed straight into Phase 1.3 (the ElevenLabs branch). Compare lowercased.

ElevenLabs is a single-agent provider — there is no squad / multi-member concept like VAPI's. One agent, one system prompt, one set of referenced tools. Agent-to-agent transfer (if configured) is a `built_in_tools.transfer_to_agent` system tool, not a squad of editable members; this skill edits the agent it was pointed at, not the transfer targets.

## Where the prompt and tools live

The Cekura agent record's `assistant_id` holds the ElevenLabs `agent_id` (e.g., `agent_3201km3twxxpekrtehzx6nxagnr5`). The live config is fetched from ElevenLabs:

- **System prompt** — `conversation_config.agent.prompt.prompt` (a single string).
- **Referenced tools** — `conversation_config.agent.prompt.tool_ids` — an array of standalone tool IDs. Each is fetched and edited via the standalone tools API (`/v1/convai/tools/{tool_id}`). This is the current ElevenLabs convention and the analog of VAPI's `model.toolIds`.
- **Inline tools (legacy)** — `conversation_config.agent.prompt.tools` — older agents embed full tool objects here instead of referencing IDs. Editable in-place on the agent PATCH. Analogous to VAPI's inline `model.tools`.
- **Built-in / system tools** — `conversation_config.agent.prompt.built_in_tools` — `end_call`, `transfer_to_agent`, `transfer_to_number`, `language_detection`, `skip_turn`. These are toggled/configured, not free-form function definitions; treat them as config flags, not prompt-editable tool bodies.

The Cekura `description` field is **not** read or written by this skill in ElevenLabs mode. ElevenLabs is the single source of truth.

## What's editable

| Surface | Editable via | Notes |
|---------|--------------|-------|
| System prompt | `PATCH /v1/convai/agents/{id}` with `conversation_config.agent.prompt.prompt` | Replace the prompt string. Preserve the rest of the `prompt` object (llm, temperature, tool_ids, knowledge_base). |
| Referenced tool (`name`, `description`, `api_schema`/`parameters`) | `PATCH /v1/convai/tools/{tool_id}` with `tool_config.*` | Standalone tool entities. Re-fetch after PATCH to verify (Step 4.2). |
| Inline tool (legacy `prompt.tools[i]`) | `PATCH /v1/convai/agents/{id}` with the full `prompt.tools` array | Sent wholesale — preserve the other entries. Prefer migrating to referenced tools only if the user asks. |
| Tool references on the agent (`prompt.tool_ids`) | `PATCH /v1/convai/agents/{id}` with `conversation_config.agent.prompt.tool_ids` | Add or remove references. Send the full new array. |
| New tool creation | `POST /v1/convai/tools` then `PATCH` the agent to add its id to `tool_ids` | Capture the new id; bundle the `tool_ids` update with the agent PATCH. |
| Tool deletion | `DELETE /v1/convai/tools/{tool_id}` | Rare. A standalone tool may be referenced by other agents in the workspace — prefer dropping the reference (`tool_ids`) over deleting the definition. |

## What is NOT in scope for ElevenLabs mode

- **Spoken `request-start` / `request-complete` / `request-failed` messages and handoff `destinations`** — those are VAPI-only concepts. ElevenLabs webhook tools don't carry per-fire spoken utterances the way VAPI tools do; do not propose edits to those surfaces. If the agent says the wrong thing when a tool fires, fix the prompt.
- **Squad members / `model.toolIds` per member** — ElevenLabs has no squads. Diagnose filters these candidates out.
- **TTS / ASR / turn-detection / voice settings** — out of scope; this skill edits prompt + tool config only. Surface voice/latency issues to the voice-channel filter (Collect Step COLLECT.3), not as edits.
- **Built-in tool toggles** (`end_call`, `transfer_to_agent`, etc.) — config flags owned by the user. Touch only if the user explicitly asks; otherwise surface as a hand-off.
- **Dynamic-variable placeholders (`{{...}}`)** — owned by the calling system. Same rule as every other mode.

## Files in this directory

- `phase-1-fetch.md` — Required env var, resolving the ElevenLabs `agent_id`, agent + tool fetch curl bodies, the compact summary template, and Phase 1 edge cases (401 / 404, missing tools, inline-vs-referenced tools, response-shape changes).
- `phase-4-apply.md` — ElevenLabs PATCH / POST / DELETE curl bodies, tool-backup pattern, the re-fetch verification step, validation-set construction, loop guardrails, and iteration-cap exit messaging.

## Phase 4 in one sentence

PATCH tools first → POST new tools → PATCH the agent (system prompt + `tool_ids` bundled into one body) → re-fetch the agent and every edited tool to confirm the body landed → run validation → re-collect failures → loop or exit. No redeploy step (edits land live). Full apply-order rationale and curl bodies are in `phase-4-apply.md`.

## Anti-patterns specific to ElevenLabs mode

- **Skipping the Step 4.2 re-fetch.** ElevenLabs PATCH does a deep merge for `conversation_config`, but arrays (`tool_ids`, `prompt.tools`) are replaced wholesale when included in the body — a malformed body can silently drop references. Always re-fetch `/v1/convai/agents/{id}` and every edited `/v1/convai/tools/{id}` and verify the changed fields landed.
- **Sending only `{"prompt": "..."}` at the top level.** The prompt is nested at `conversation_config.agent.prompt.prompt` — a top-level `prompt` key is ignored and the edit silently no-ops. This is the single most common ElevenLabs apply mistake.
- **Editing dynamic-variable placeholders (`{{...}}`) without an explicit user ask.** They're owned by the calling system. Same rule as the other modes.
- **Treating ElevenLabs like a VAPI squad.** There are no members to attribute failures to and no per-member prompt. One agent, one prompt — attribute every prompt-following failure to the single system prompt.
- **Patching a tool's `api_schema` to mask a prompt issue.** If the agent calls a tool wrong or says the wrong thing, fix the prompt; only edit the tool's `name` / `description` / `api_schema` when the tool definition itself is the root cause.
- **Re-using a stale local copy of the prompt / tools across iterations.** ElevenLabs dashboard edits don't notify Cekura. Re-fetch at the start of every Diagnose if more than a few minutes have passed since the last fetch.
- **Editing built-in/system tools or voice settings as if they were prompt-editable.** They're config flags, not free-form definitions. Surface as hand-offs unless the user asks.
