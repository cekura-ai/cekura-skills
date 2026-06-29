# Optimization · Apply — Land the Combined Edit Set

Fourth sub-phase of optimization. Applies the approved combined edit set (early-end-call edits from EARLY.3 + diagnose edits from DIAGNOSE.4) to the appropriate live surface, then runs `redeploy_command` (or fires the manual restart gate) so the live agent picks up the changes.

This sub-phase performs writes — every step is a real PATCH / `Edit` against live state. The Sync sub-phase ([`sync.md`](sync.md)) immediately follows to verify the writes landed.

## Pre-flight check

Before any Step APPLY.x work, verify diagnose handed off cleanly:

- Combined approved edit set is non-empty (if empty, the diagnose hand-off should have already stopped the loop — do not reach Apply).
- In `auto_mode: false`, the user explicitly confirmed the Step DIAGNOSE.5 proposal.
- All edits are de-conflicted — no two edits target the same prompt section / source-file lines without being merged into a single combined edit.
- `redeploy_command` is recorded on run state (set during Setup Step 1.4) — either a real shell command, `"manual"`, `"noop"`, render-only, or VAPI / ElevenLabs (managed providers, which don't need one).

If any of the above is missing, return control to the orchestrator.

## Step APPLY.1 — Apply the edits (branch by mode)

Apply-order details, gate wording, and edge cases live in each mode's doc:

- **VAPI** — [`../../providers/vapi/phase-4-apply.md`](../../providers/vapi/phase-4-apply.md): tool PATCH → new-tool POST → assistant PATCH (prompt + `toolIds` bundled). No redeploy step (edits land live; skip Step APPLY.2).
- **ElevenLabs** — [`../../providers/elevenlabs/phase-4-apply.md`](../../providers/elevenlabs/phase-4-apply.md): tool PATCH (`/v1/convai/tools/{id}`) → new-tool POST (`/v1/convai/tools`) → agent PATCH (`conversation_config.agent.prompt.prompt` + `prompt.tool_ids` bundled). No redeploy step (edits land live; skip Step APPLY.2).
- **Self-hosted** — [`../../providers/self-hosted/overview.md`](../../providers/self-hosted/overview.md) § "Apply order, Sync, and exit framing" + "Edit mechanisms". Apply via the mechanism the run-setup points to: tool/mock-tool edits → new tools → system-prompt edit → (source-file edits) orchestration-code edits, then the redeploy step (Step APPLY.2). For a database row, run the user's UPDATE through the right CLI client (psql / mysql / sqlite3 / sqlcmd / mongosh), passing the new prompt via env var or stdin (never a positional arg). When there's no reachable live target (render-only), print the rewritten prompt — auto-mode asks once for new pasted failures concisely, non-auto fires the full manual-apply gate — and skip Step APPLY.2 (no live agent).

Apply early-end-call edits and diagnose edits as a single batch in the order above. They were already de-conflicted in Step DIAGNOSE.4, so order between the two diagnose sub-phases' edits doesn't matter — only the apply order (tools before prompt, or per-doc instructions) matters.

## Step APPLY.2 — Redeploy step (self-hosted with live target only)

Skip entirely for VAPI, for ElevenLabs, and for render-only runs (no live target). For every self-hosted run with a live target, branch on `redeploy_command`:

- **Command provided** → run it via the Bash tool. Capture exit code and stderr. On non-zero exit, surface the failure to the user, do NOT proceed to [`sync.md`](sync.md), and ask whether to retry the redeploy or abort. On success (or success-with-warnings), proceed to Sync.
- **`redeploy_command == "manual"` (or unset and `auto_mode: false`)** → fire the manual restart gate (see [`../../providers/self-hosted/overview.md`](../../providers/self-hosted/overview.md) § "Redeploy command flow"). Wait for explicit user confirmation (`done` / `restarted` / `redeployed` / `yes`).
- **`redeploy_command == "noop"` (the live agent re-reads the new state on every request)** → skip the pause and proceed straight to Sync. The edit is already live.
- **Unset and `auto_mode: true`** → proceed straight to Sync without pausing. The Eval phase's no-change detector surfaces stale-state hypotheses after the fact.

Treat the redeploy step as a critical path: a failed redeploy means validation will reflect the pre-edit live state. Never silently swallow a non-zero exit code and proceed to Sync — that produces results indistinguishable from "the prompt edit didn't help" and burns iteration cap.

## Hand-off to sync

After Step APPLY.2 (or after Step APPLY.1 for VAPI / ElevenLabs / render-only), hand off to [`sync.md`](sync.md) with:

- The list of artifacts that were edited (assistant IDs, tool IDs, file paths) — Sync re-fetches these to verify.
- The combined edit set (used by Sync to confirm the specific changed fields landed correctly).
- The redeploy outcome (succeeded / skipped / manual-confirmed) so Sync can correctly attribute any drift it detects.
