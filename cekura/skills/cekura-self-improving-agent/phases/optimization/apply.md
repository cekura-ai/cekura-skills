# Optimization · Apply — Land the Combined Edit Set

Third sub-phase of optimization. Lands the approved combined edit set (early-end edits from FIX.1 + the rest from FIX.5) via the target's **apply path**, then — for a live self-hosted target — runs `redeploy_command` (or fires the manual restart gate) so the live agent picks up the change. Every step is a real write against live state (or a staged diff for the offline-PR path). Sync ([`sync.md`](sync.md)) immediately follows to verify.

## Pre-flight check

Before any APPLY.x work, verify fix handed off cleanly:

- Combined approved edit set is non-empty (empty → fix should have already stopped the loop; do not reach Apply).
- In `auto_mode: false`, the user confirmed the FIX.6 proposal.
- Edits are de-conflicted — no two target the same prompt section / source-file lines without being merged.
- The apply path is recorded on run state (Setup Step 1.4): provider API PATCH (VAPI / ElevenLabs), `Edit` + `redeploy_command` (self-hosted live), live-on-save (`"noop"`), **offline-PR** (code-fix), or render-only.

If any is missing, return control to the orchestrator.

## Step APPLY.1 — Apply the edits (branch by apply path)

Apply the whole edit set as a single batch; it was de-conflicted in FIX.5, so only apply *order* (tools before prompt) matters, not which stream an edit came from. Per-path machinery:

- **VAPI** — [`../../providers/vapi/phase-4-apply.md`](../../providers/vapi/phase-4-apply.md): tool PATCH → new-tool POST → assistant PATCH (prompt + `toolIds` bundled). Edits land live; skip APPLY.2.
- **ElevenLabs** — [`../../providers/elevenlabs/phase-4-apply.md`](../../providers/elevenlabs/phase-4-apply.md): tool PATCH (`/v1/convai/tools/{id}`) → new-tool POST (`/v1/convai/tools`) → agent PATCH (`conversation_config.agent.prompt.prompt` + `prompt.tool_ids` bundled). Edits land live; skip APPLY.2.
- **Self-hosted** — [`../../providers/self-hosted/overview.md`](../../providers/self-hosted/overview.md) § "Apply order, Sync, and exit framing" + "Edit mechanisms". Apply via the mechanism the run-setup names, in order: tool/mock-tool edits → new tools → system-prompt edit → owned source-code edits (orchestration or vendored/forked SDK in the tree), then APPLY.2. DB row: run the UPDATE through the right CLI client (psql / mysql / sqlite3 / sqlcmd / mongosh), passing the new prompt via env var or stdin (never a positional arg). Then branch on the apply path:
  - **`Edit` + `redeploy_command`** (live target) → apply the edits, then APPLY.2.
  - **live-on-save (`"noop"`)** → the running agent re-reads state per request; apply the edits and go straight to Sync (APPLY.2 is a skip — see below).
  - **offline-PR** (code-fix — the failure doesn't reproduce in simulation and is validated by a test suite) → apply the source edits to the working tree. **No live redeploy**: the diff is staged and carried to the PR phase; do NOT run `redeploy_command`. Skip APPLY.2. (Owned code, incl. a forked SDK in the tree, is a CodeBug and in-scope — not Upstream.)
  - **render-only** (no reachable live target) → print the rewritten prompt/diff. Auto-mode asks once, concisely, for new pasted failures; non-auto fires the full manual-apply gate. Skip APPLY.2.

## Step APPLY.2 — Redeploy step (self-hosted with live target only)

Skip entirely for VAPI, ElevenLabs, render-only, and offline-PR (no live target to refresh). For a self-hosted live target, branch on `redeploy_command`:

- **Command provided** → run via Bash. Capture exit code + stderr. Non-zero → surface the failure, do NOT proceed to Sync, ask whether to retry or abort. Success (or success-with-warnings) → Sync.
- **`"manual"`** (or unset and `auto_mode: false`) → fire the manual restart gate ([self-hosted overview](../../providers/self-hosted/overview.md) § "Redeploy command flow"); wait for explicit confirmation (`done` / `restarted` / `redeployed` / `yes`).
- **`"noop"`** (live agent re-reads state per request) → no pause, proceed to Sync; the edit is already live.
- **Unset and `auto_mode: true`** → proceed to Sync without pausing; Eval's no-change detector surfaces stale-state hypotheses after the fact.

The redeploy step is critical path: a failed redeploy means validation reflects pre-edit live state. Never swallow a non-zero exit and proceed — that's indistinguishable from "the edit didn't help" and burns iteration cap.

## Hand-off to sync

After APPLY.2 (or after APPLY.1 for VAPI / ElevenLabs / render-only / offline-PR / noop), hand off to [`sync.md`](sync.md) with:

- The list of edited artifacts (assistant IDs, tool IDs, file paths) — Sync re-fetches these.
- The combined edit set (Sync confirms each changed field landed).
- The redeploy outcome (succeeded / skipped / manual-confirmed / offline-staged) so Sync attributes drift correctly.
