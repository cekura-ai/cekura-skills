# Optimization · Sync — Verify the Edits Landed

Final sub-phase of optimization. Re-reads the just-edited artifacts and verifies the intended changes are present. This is the last gate before handing off to the Overfitting Gate phase, and it catches three classes of silent failures:

- **VAPI PATCH nested-object replacement**: a malformed `messages` or `destinations` body can wipe the entire nested object while returning 200 OK.
- **ElevenLabs wrong-path prompt no-op**: a PATCH that nests the prompt at the wrong path (e.g. top-level `prompt` instead of `conversation_config.agent.prompt.prompt`) returns 200 OK and changes nothing; an array (`tool_ids` / `prompt.tools`) sent partially replaces the whole array.
- **Ambiguous `Edit` anchors** (self-hosted source-file edits): an `old_string` that matched a near-identical block elsewhere in the file landed the change in the wrong region. Apply may have succeeded against a "lookalike" line set.
- **Stale-cache reads in Cekura platform tools** (self-hosted mock-tool edits): the post-PATCH re-fetch may serve a cached pre-PATCH view; re-read after the platform tool's response, not from any local cache.

If Sync detects drift, do NOT proceed to the Overfitting Gate. Roll back to Apply, fix the offending edit, and re-run Apply + Sync.

## Pre-flight check

Before any Step SYNC.x work, verify Apply completed:

- Apply Step APPLY.1 emitted no errors (per-provider apply machinery returned success).
- Apply Step APPLY.2 redeploy succeeded (for self-hosted live targets) — or was skipped because mode is VAPI / ElevenLabs / render-only, or because `redeploy_command` is unset in `auto_mode: true`.
- The list of edited artifacts and the combined edit set are available from Apply's hand-off.

If Apply errored, return control to the orchestrator — Sync has nothing to verify.

## Step SYNC.1 — Re-fetch and verify (branch by mode)

- **VAPI** — re-fetch `/assistant/{id}` and every edited / created `/tool/{id}` and verify the changed fields landed. Don't skip the tool re-fetch — VAPI's tool PATCH semantics replace nested objects wholesale; a malformed body can silently wipe `messages` or `destinations` while returning 200.
- **ElevenLabs** — re-fetch `GET /v1/convai/agents/{id}` and every edited / created `GET /v1/convai/tools/{id}` and verify the changed fields landed. Critically: confirm `conversation_config.agent.prompt.prompt` actually equals the new prompt string (a 200 on the PATCH proves nothing if the body nested the prompt at the wrong path — it no-ops silently), and that `prompt.tool_ids` matches the intended array (arrays replace wholesale). For edited tools, confirm `tool_config` fields match.
- **Self-hosted** — re-read whatever was edited and verify the changed fields landed:
  - **Source file** — re-read it (Read tool, not cached) and verify the changed regions match the intended `Edit` output. If a tool-definition edit was supposed to extend the tools list but the post-edit file shows the old length, the edit landed in the wrong place or matched a partial-but-ambiguous `old_string` — roll back to Apply and retry with more surrounding context in the anchor.
  - **Database row** — re-run the fetch query and confirm the returned prompt equals the intended new prompt (whitespace-only diffs are fine; content drift means the write targeted the wrong row or a trigger rewrote it).
  - **Cekura mock tools** — re-fetch via `mcp__cekura__aiagents_retrieve` with `ql={mock_tools}` and verify the updated `mock_tools` list matches what was patched.
  - There is no "live agent" sync to verify on Cekura's side; the redeploy gate (non-auto) or the no-change detector (auto) covers the live state.
  - **Render-only (no live target)** — skip; nothing to sync server-side. The user's reply to the apply gate is the only confirmation.

For each artifact, verify each individual changed field — not just "the artifact was re-fetched successfully". A 200 OK on the PATCH plus a 200 OK on the re-fetch is necessary but not sufficient evidence; the new field values must match the intended `new_string` / new prompt section / new tool description.

## Drift handling

If any field doesn't match its intended value:

- **VAPI: nested object wiped** → the most likely cause is a PATCH body that replaced (rather than merged) a nested `messages` or `destinations` object. Rebuild the PATCH body with the full nested structure preserved (per the VAPI apply doc) and re-issue via Apply.
- **ElevenLabs: prompt unchanged after 200 OK** → the PATCH body almost certainly nested the prompt at the wrong path. Rebuild with `{"conversation_config":{"agent":{"prompt":{"prompt":"..."}}}}` (per the ElevenLabs apply doc) and re-issue via Apply. If `tool_ids` came back missing entries, the array was sent partially — re-send the full intended array.
- **Self-hosted source file: edit landed in wrong region** → the `old_string` matched a lookalike elsewhere in the file. Roll back by inverting the `Edit` (swap `old_string` and `new_string`) at the wrong location, then re-issue Apply with a more uniquely-anchored `old_string` (5–10 lines of surrounding context).
- **Self-hosted database row: re-fetch shows the pre-edit prompt** → the write targeted the wrong row (stale WHERE/bind values), a trigger/view rewrote it, or fetch and write point at different environments. Re-issue the UPDATE against the correct row (per the self-hosted overview's DB notes), or — in render-only — re-render and wait.
- **Self-hosted mock tools: re-fetch shows old description** → wait 2-3 seconds and re-fetch once more (eventual-consistency window). If still stale, re-issue the PATCH; the original may not have committed.

In every drift case, the Overfitting Gate must NOT run on the failed state — return to Apply, fix the edit, re-run Sync, and only hand off when Sync confirms.

## Hand-off to the Overfitting Gate phase

After Step SYNC.1 confirms every changed field landed correctly, the Optimization phase is complete for this iteration. Hand off to [`../overfitting-gate.md`](../overfitting-gate.md) with:

- The edits that were applied this iteration, with `old_string` + `new_string` per edit (the gate needs this to score whether any new text quotes the failing transcripts verbatim or otherwise overfits).
- The failing transcripts from Collect Step COLLECT.4 (also gate input — the gate compares added text against these).
- The early-end-call diagnose summary (the gate's signature scorer excludes orchestration-code edits and pure deletions, and may also want to know which edits came from the early-end sub-phase so it can apply tighter heuristics on those — they're prone to quoting farewell phrasing).
- The kept failure set, the full set (recorded on iteration 1, never changes mid-loop), and the iteration number for cap tracking and oscillation/no-change detection.

If the iteration produced zero edits and reached Sync only via the "early-end pass-through" + "diagnose all-Upstream" path, the diagnose hand-off should have already short-circuited the loop. Reaching Sync with an empty edit set is a contract violation upstream — surface to the user and stop.
