# Optimization · Apply — Land the Combined Edit Set

Fourth sub-phase of optimization. Applies the approved combined edit set (early-end-call edits from EARLY.3 + diagnose edits from DIAGNOSE.4) to the appropriate live surface, then runs `redeploy_command` (or fires the manual restart gate) so the live agent picks up the changes.

This sub-phase performs writes — every step is a real PATCH / `Edit` against live state. The Sync sub-phase ([`sync.md`](sync.md)) immediately follows to verify the writes landed.

## Pre-flight check

Before any Step APPLY.x work, verify diagnose handed off cleanly:

- Combined approved edit set is non-empty (if empty, the diagnose hand-off should have already stopped the loop — do not reach Apply).
- In `auto_mode: false`, the user explicitly confirmed the Step DIAGNOSE.5 proposal.
- All edits are de-conflicted — no two edits target the same prompt section / source-file lines without being merged into a single combined edit.
- `redeploy_command` is recorded on run state (set during Setup Step 1.4) — either a real shell command, the literal `"manual"`, or VAPI / ElevenLabs (managed providers, which don't need one).

If any of the above is missing, return control to the orchestrator.

## Step APPLY.1 — Apply the edits (branch by mode + sub-flavor)

Apply-order details, gate wording, and edge cases live in each provider's doc:

- **VAPI** — [`../../providers/vapi/phase-4-apply.md`](../../providers/vapi/phase-4-apply.md): tool PATCH → new-tool POST → assistant PATCH (prompt + `toolIds` bundled). No redeploy step (edits land live; skip Step APPLY.2).
- **ElevenLabs** — [`../../providers/elevenlabs/phase-4-apply.md`](../../providers/elevenlabs/phase-4-apply.md): tool PATCH (`/v1/convai/tools/{id}`) → new-tool POST (`/v1/convai/tools`) → agent PATCH (`conversation_config.agent.prompt.prompt` + `prompt.tool_ids` bundled). No redeploy step (edits land live; skip Step APPLY.2).
- **Self-hosted / pipecat** — [`../../providers/self-hosted/pipecat.md`](../../providers/self-hosted/pipecat.md) § "Phase 4.1b — apply order": mock-tool PATCH → new mock-tool POST → description PATCH → redeploy step (Step APPLY.2).
- **Self-hosted / websocket / `file`** — [`../../providers/self-hosted/websocket.md`](../../providers/self-hosted/websocket.md) § "Phase 4.1d — Apply" (variant `file`): tool-definition `Edit`s → new-tool `Edit` → system-prompt `Edit` → optional Cekura description sync → redeploy step (Step APPLY.2).
- **Self-hosted / websocket / `offline`** — [`../../providers/self-hosted/websocket.md`](../../providers/self-hosted/websocket.md) § "Phase 4.1d — Apply" (variant `offline`): render the rewritten prompt; auto-mode asks once for new pasted failures concisely; non-auto fires the full manual-apply gate. No redeploy step (no live agent; skip Step APPLY.2).
- **Self-hosted / database** — [`../../providers/self-hosted/database.md`](../../providers/self-hosted/database.md) § "Phase 4.1e — Apply (DB write)": write-query variant runs the user's UPDATE / `updateOne` via the appropriate CLI client (psql / mysql / sqlite3 / sqlcmd / mongosh), passing the new prompt via env var or stdin (never a positional arg), then runs `redeploy_command` (Step APPLY.2) — `"noop"` skips the pause when the live agent re-reads the row on every request. Render-only variant (no write query supplied) prints the new prompt and waits for the user to update the DB themselves; no redeploy step.

Apply early-end-call edits and diagnose edits as a single batch in the order above (per-mode). They were already de-conflicted in Step DIAGNOSE.4, so order between the two diagnose sub-phases' edits doesn't matter — only the per-mode apply order (tools before prompt, or per-doc instructions) matters.

## Step APPLY.2 — Redeploy step (self-hosted with live target only)

Skip entirely for VAPI, for ElevenLabs, and for the websocket `offline` variant. For pipecat, websocket / `file`, and database (write-query variant), branch on `redeploy_command`:

- **Command provided** → run it via the Bash tool. Capture exit code and stderr. On non-zero exit, surface the failure to the user, do NOT proceed to [`sync.md`](sync.md), and ask whether to retry the redeploy or abort. On success (or success-with-warnings), proceed to Sync.
- **`redeploy_command == "manual"` (or unset and `auto_mode: false`)** → fire the per-sub-flavor manual restart gate (pipecat redeploy gate, websocket restart gate, database restart-or-reload gate). Wait for explicit user confirmation (`done` / `restarted` / `redeployed` / `yes`).
- **`redeploy_command == "noop"` (database sub-flavor, live agent re-reads the row on every request)** → skip the pause and proceed straight to Sync. The UPDATE has already made the new prompt live.
- **Unset and `auto_mode: true`** → proceed straight to Sync without pausing. The Eval phase's no-change detector surfaces stale-state hypotheses after the fact.

Treat the redeploy step as a critical path: a failed redeploy means validation will reflect the pre-edit live state. Never silently swallow a non-zero exit code and proceed to Sync — that produces results indistinguishable from "the prompt edit didn't help" and burns iteration cap.

## Hand-off to sync

After Step APPLY.2 (or after Step APPLY.1 for VAPI / ElevenLabs / offline), hand off to [`sync.md`](sync.md) with:

- The list of artifacts that were edited (assistant IDs, tool IDs, file paths) — Sync re-fetches these to verify.
- The combined edit set (used by Sync to confirm the specific changed fields landed correctly).
- The redeploy outcome (succeeded / skipped / manual-confirmed) so Sync can correctly attribute any drift it detects.
