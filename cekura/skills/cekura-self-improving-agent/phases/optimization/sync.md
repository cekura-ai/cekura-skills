# Optimization · Sync — Verify the Edits Landed

Final sub-phase of optimization. Re-reads the just-edited artifacts and verifies the intended changes are present — the last gate before the Overfitting Gate. Catches four classes of silent failure:

- **VAPI PATCH nested-object replacement** — a malformed `messages` / `destinations` body wipes the nested object while returning 200 OK.
- **ElevenLabs wrong-path prompt no-op** — a PATCH nesting the prompt at the wrong path (top-level `prompt` instead of `conversation_config.agent.prompt.prompt`) returns 200 OK and changes nothing; a partial array (`tool_ids` / `prompt.tools`) replaces the whole array.
- **Ambiguous `Edit` anchors** (self-hosted source-file / owned-code edits) — an `old_string` matching a near-identical block elsewhere landed the change in the wrong region.
- **Stale-cache reads** (self-hosted mock-tool edits) — the post-PATCH re-fetch may serve a cached pre-PATCH view; re-read from the platform tool's response, not any local cache.

On drift, do NOT proceed to the Overfitting Gate — roll back to Apply, fix the edit, re-run Apply + Sync.

## Pre-flight check

Before any SYNC.x work, verify Apply completed:

- APPLY.1 emitted no errors.
- APPLY.2 redeploy succeeded (self-hosted live target) — or was skipped (VAPI / ElevenLabs / render-only / offline-PR / `"noop"`, or `redeploy_command` unset in `auto_mode: true`).
- The edited-artifact list and combined edit set are available from Apply's hand-off.

If Apply errored, return control to the orchestrator — Sync has nothing to verify.

## Step SYNC.1 — Re-fetch and verify (branch by apply path)

For each artifact, verify **each individual changed field** — not just "the artifact was re-fetched." A 200 on the PATCH plus a 200 on the re-fetch is necessary but not sufficient; the new value must equal the intended `new_string` / prompt section / tool description.

- **VAPI** — re-fetch `/assistant/{id}` and every edited/created `/tool/{id}`; verify changed fields. Don't skip the tool re-fetch — VAPI tool PATCH replaces nested objects wholesale; a malformed body silently wipes `messages` / `destinations` at 200.
- **ElevenLabs** — re-fetch `GET /v1/convai/agents/{id}` and every edited/created `GET /v1/convai/tools/{id}`. Confirm `conversation_config.agent.prompt.prompt` equals the new prompt (a 200 proves nothing if the body nested it wrong — silent no-op), `prompt.tool_ids` matches the intended array (arrays replace wholesale), and edited tools' `tool_config` fields match.
- **Self-hosted** — re-read whatever was edited:
  - **Source file / owned code** (incl. vendored/forked SDK) — re-read (Read tool, not cached) and verify the changed regions match the `Edit` output. If a tool-list extension shows the old length, the edit matched an ambiguous/partial `old_string` — roll back and retry with more surrounding context.
  - **Database row** — re-run the fetch query; the returned prompt must equal the intended new prompt (whitespace-only diffs OK; content drift = wrong row or a trigger rewrote it).
  - **Cekura mock tools** — re-fetch via `mcp__cekura__aiagents_retrieve` with `ql={mock_tools}`; verify the updated `mock_tools` list matches. There is no "live agent" sync on Cekura's side; the redeploy gate (non-auto) / no-change detector (auto) covers live state.
  - **Offline-PR (code-fix)** — no live target and no redeploy; verify the working-tree diff instead: re-read the edited source and confirm each changed region matches the intended `Edit` output (same ambiguous-anchor check as above). The staged diff is what the PR phase carries — landing it in the wrong region would ship a broken PR. Validation is the test suite (run later), not a live re-fetch.
  - **Render-only (no live target)** — skip; nothing to sync server-side. The user's reply to the apply gate is the only confirmation.

## Drift handling

If any field doesn't match its intended value:

- **VAPI: nested object wiped** → PATCH body replaced rather than merged a nested `messages` / `destinations`. Rebuild with the full nested structure preserved (VAPI apply doc) and re-issue via Apply.
- **ElevenLabs: prompt unchanged after 200** → body nested the prompt at the wrong path. Rebuild with `{"conversation_config":{"agent":{"prompt":{"prompt":"..."}}}}` and re-issue. If `tool_ids` lost entries, the array was sent partially — re-send the full array.
- **Self-hosted source file / owned code: edit in wrong region** → `old_string` matched a lookalike. Invert the `Edit` (swap `old_string`/`new_string`) at the wrong location, then re-issue Apply with a uniquely-anchored `old_string` (5–10 lines of context). Same handling for an offline-PR working-tree diff that landed wrong.
- **Self-hosted DB row: re-fetch shows pre-edit prompt** → wrong row (stale WHERE/bind), a trigger/view rewrote it, or fetch and write point at different environments. Re-issue the UPDATE against the correct row (self-hosted overview DB notes), or in render-only re-render and wait.
- **Self-hosted mock tools: re-fetch shows old description** → wait 2–3s and re-fetch once (eventual-consistency window). Still stale → re-issue the PATCH; the original may not have committed.

In every drift case, the Overfitting Gate must NOT run on the failed state — return to Apply, fix the edit, re-run Sync, hand off only when Sync confirms.

## Hand-off to the Overfitting Gate

After SYNC.1 confirms every changed field landed, Optimization is complete for this iteration. Hand off to [`../overfitting-gate.md`](../overfitting-gate.md) with:

- The applied edits, `old_string` + `new_string` per edit (the gate scores whether new text quotes failing transcripts verbatim / overfits; code control-flow and pure deletions are not scored, embedded prompt string literals are).
- The failing transcripts from COLLECT.4 (gate compares added text against these).
- The FIX.1 early-end summary (the gate applies tighter heuristics to early-end edits — they're prone to quoting farewell phrasing).
- The kept failure set, the full set (recorded on iteration 1, never changes mid-loop), and the iteration number (cap tracking + oscillation/no-change detection).

If the iteration produced zero edits and reached Sync via "early-end pass-through" + "fix all-Upstream", the fix hand-off should have already short-circuited the loop. Reaching Sync with an empty edit set is an upstream contract violation — surface to the user and stop.
