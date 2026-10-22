# VAPI Mode — Overview

VAPI is the provider where prompts and tool definitions are editable directly via the VAPI API using `VAPI_KEY`. Edits land immediately; no redeploy gate needed.

## VAPI-mode gate (Setup)

When `assistant_provider == vapi` (compare lowercased), proceed to the fetch ([`phase-1-fetch.md`](phase-1-fetch.md)) without confirmation.

## What's editable

| Surface | Editable via | Notes |
|---------|--------------|-------|
| System prompt (per assistant; per squad member for squads) | `PATCH /assistant/{id}` with `model.messages` | Replace the system message wholesale; preserve `role: "system"`. |
| Tool function declaration (`name`, `description`, `parameters`) | `PATCH /tool/{id}` with `function.*` | Tool PATCH replaces nested objects wholesale — always re-fetch after PATCH (SYNC.1). |
| Tool spoken messages (`request-start.content`, `request-complete.content`, `request-failed.content`) | `PATCH /tool/{id}` with `messages` | Only when the tool's *own* utterance is wrong — not to mask a prompt issue. |
| Handoff `destinations` (transferCall / handoff tools) | `PATCH /tool/{id}` with `destinations` | Wrong destination is a tool-config root cause, not a prompt root cause. |
| Tool references per assistant (`model.toolIds`) | `PATCH /assistant/{id}` with `model.toolIds` | Add or remove references. For squads, only the targeted member is affected. |
| New tool creation | `POST /tool` then `PATCH /assistant/{id}` to reference it | Capture the new id and bundle the `toolIds` update with the assistant PATCH. |
| Tool deletion | `DELETE /tool/{id}` | Rare — only after confirming no squad member references it. Prefer reference removal. |

The Cekura `description` field is **not** read or written in VAPI mode.

## Apply in one sentence

PATCH tools first → POST new tools → PATCH assistant (system prompt + `toolIds` bundled, one per member for squads) → re-fetch everything edited → run validation → re-collect failures → loop or exit. Full curl bodies in [`phase-4-apply.md`](phase-4-apply.md).

## Anti-patterns

- **Skipping the SYNC.1 re-fetch.** VAPI PATCH replaces nested objects wholesale; a malformed body can silently wipe `messages` or `destinations` while returning 200.
- **Editing `{{...}}` placeholders without explicit user ask.** They're owned by the calling system.
- **Patching spoken `messages` to mask a prompt issue.** Only patch `request-start` / `request-complete` / `request-failed` when the tool's own utterance is the offending one.
- **Mass-deleting "unused"-looking tools.** A tool unreferenced in this agent may be referenced elsewhere. Prefer reference removal; deletion is irreversible from this skill.
- **Splitting prompt edit and `toolIds` change into separate PATCHes.** Bundle them into one body — split PATCHes create a window where instructions reference a tool the assistant doesn't have.
- **Reusing a stale local copy across iterations.** Re-fetch at the start of every Fix if more than a few minutes have passed since the last Setup / Sync read.
