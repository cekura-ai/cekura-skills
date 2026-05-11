# VAPI Mode — Overview

VAPI is the only mode this skill can PATCH end-to-end against the live agent. The system prompt and every tool definition (function declarations, spoken `messages`, handoff `destinations`) are editable via the VAPI API using `VAPI_KEY`. Edits land immediately; the live agent picks them up on the next call.

This mode is the "fast path" — full closed-loop iteration without redeploy gates, file edits, or paste round-trips.

Use this reference together with the main SKILL.md.

## VAPI-mode gate (Phase 1.2)

When `assistant_provider == vapi`, no extra confirmation needed — proceed straight into Phase 1.3a. Compare lowercased.

`retell` is the related supported-but-disabled tag — do NOT route Retell agents into the VAPI branch even though the gate shape is similar. See `phase-1-fetch.md` for the canonical unsupported-provider error wording.

## What's editable

| Surface | Editable via | Notes |
|---------|--------------|-------|
| System prompt (per assistant; per squad member for squads) | `PATCH /assistant/{id}` with `model.messages` | Replace the system message wholesale; preserve `role: "system"`. |
| Tool function declaration (`name`, `description`, `parameters`) | `PATCH /tool/{id}` with `function.*` | Tool PATCH replaces nested objects wholesale — always re-fetch after PATCH (Step 4.2a). |
| Tool spoken messages (`request-start.content`, `request-complete.content`, `request-failed.content`) | `PATCH /tool/{id}` with `messages` | Edit when the spoken utterance is itself wrong — don't use this to mask a prompt-driven utterance issue. |
| Handoff `destinations` (transferCall / handoff tools) | `PATCH /tool/{id}` with `destinations` | Wrong destination is a tool-config root cause, not a prompt root cause. |
| Tool references per assistant (`model.toolIds`) | `PATCH /assistant/{id}` with `model.toolIds` | Add or remove references. For squads, only the targeted member is affected. |
| New tool creation | `POST /tool` then `PATCH /assistant/{id}` to reference it | Capture the new id and bundle the `toolIds` update with the assistant PATCH. |
| Tool deletion | `DELETE /tool/{id}` | Rare — only after cross-referencing every squad member's `toolIds` and confirming no references remain. Prefer reference removal. |

The Cekura `description` field is **not** read or written by this skill in VAPI mode. VAPI is the single source of truth.

## Files in this directory

- `phase-1-fetch.md` — Provider-gate error message shapes, VAPI assistant + squad + tool fetch curl bodies, member summary template, and Phase 1 edge cases (401 / 404, empty squads, inline-only members, response-shape changes).
- `phase-4-apply.md` — VAPI PATCH / POST / DELETE curl bodies, tool-backup pattern, validation-set construction details, loop guardrails (oscillation, stability, cumulative diff), and iteration-cap exit messaging.

## Phase 4 in one sentence

PATCH tools first → POST new tools → PATCH assistant (system prompt + `toolIds` bundled into one body, one per member for squads) → re-fetch everything edited to confirm the body landed → run validation → re-collect failures → loop or exit. Full apply-order rationale and curl bodies are in `phase-4-apply.md`.

## Anti-patterns specific to VAPI mode

- **Skipping the Phase 4.2a re-fetch.** VAPI's PATCH semantics replace nested objects wholesale; a malformed body can silently wipe `messages` or `destinations` while returning 200. Always re-fetch `/assistant/{id}` and every edited `/tool/{id}` and verify the changed fields landed.
- **Editing dynamic-variable placeholders (`{{...}}`) without an explicit user ask.** They're owned by the calling system. Same rule as the other modes.
- **Patching a tool's spoken `messages` to mask a prompt issue.** If the agent says the wrong thing in conversation, fix the prompt; only patch `request-start` / `request-complete` / `request-failed` when the tool's *own* utterance is the offending one.
- **Mass-deleting "unused"-looking tools.** A tool with no references in this agent's squad members may still be referenced elsewhere. Prefer reference removal over delete; deletion is irreversible from this skill.
- **Bundling a prompt edit and a `toolIds` change into separate PATCHes.** They must land in the same body — splitting them creates a brief window where the agent's instructions reference a tool it doesn't have (or vice versa).
- **Re-using a stale local copy of the prompt / tools across iterations.** VAPI dashboard edits don't notify Cekura. Re-fetch at the start of every Phase 3 if more than a few minutes have passed since the last Phase 1.3 / Phase 4.2 read.
