# Self-Hosted — Pipecat Sub-Flavor

Pipecat-flavor agents are pipecat pipelines the user runs on Pipecat Cloud or their own infrastructure. The Cekura agent record's `description` (system prompt) and the attached mock-tool definitions are the editable surface — Cekura is a mirror of what the user's live pipecat code is *contracted* to follow. In auto mode (the default), re-validation runs immediately after each PATCH and does NOT pause to ask the user to redeploy. In `auto_mode: false`, re-validation gates on a user-confirmed redeploy.

Use this reference together with the main SKILL.md and `providers/self-hosted/overview.md`. VAPI-specific details live in `providers/vapi/phase-1-fetch.md` and `providers/vapi/phase-4-apply.md`. The websocket sub-flavor of self-hosted is documented in `providers/self-hosted/websocket.md`.

## Pipecat-flavor gate (Phase 1.2)

The user reaches this sub-flavor either by:

- `provider.type == "pipecat"` — proceed straight in.
- `provider.type` is `self_hosted` / `custom` (or a chat-only agent, e.g. `agentforce` under `chat_agent_details.type`) and the user picked `pipecat` at the self-hosted sub-flavor router (see `overview.md`).

If the user is unsure whether their setup is pipecat or websocket, the disambiguating question is "Is your live agent a pipecat pipeline?" If no, route to `websocket.md` instead. If they declined every self-hosted sub-flavor, the workflow halts — see the main SKILL.md "unsupported provider" error wording (mirrored in `providers/vapi/phase-1-fetch.md`).

## Required Cekura tools

All pipecat-mode work uses Cekura platform tools (not VAPI's API). Confirm the MCP server is configured (`/setup-mcp`) before starting.

| Operation | Tool |
|-----------|------|
| Fetch agent record (description + provider config) | `mcp__cekura__aiagents_retrieve` |
| List mock tools attached to the agent | `mcp__cekura__aiagents_tools_list` |
| Read a single mock tool | `mcp__cekura__aiagents_tool_retrieve` |
| Update agent description | `mcp__cekura__aiagents_partial_update` |
| Update a mock tool's description / parameters | `mcp__cekura__aiagents_tool_partial_update` |
| Create a new mock tool | `mcp__cekura__aiagents_tools_create` |

`aiagents_create` and `aiagents_tools_create` have known MCP URI-length limits for large payloads (>4 KB). For long descriptions, fall back to direct API calls — see `cekura-create-agent`'s `scripts/upload-agent.sh` and the "Known MCP Limitations" section in this repo's CLAUDE.md.

## Phase 1.3b — compact summary template

```
Pipecat agent: <agent_name> (id: <agent_id>)
  Provider tag: <provider.type>      # pipecat, or the custom tag confirmed pipecat-backed
  Description (system prompt): <length> chars
  Mock tools: <N>
    - <tool_name> — <description first 80 chars>
        params: <comma-separated required keys, or "none">
  Dynamic-variable placeholders detected in description: <list of {{...}} or "none">

Note: Cekura's stored description and mock tools are the editable surface. The live
pipecat agent runs your own code — in auto mode (the default), validation runs
immediately after each PATCH without pausing to ask you to redeploy. If you want
the new prompt to actually take effect before evals run, redeploy your pipecat
agent in parallel. If two iterations come back with identical failures, the skill
surfaces a "redeploy may not have happened" hypothesis after the fact.
```

## Phase 1.3b edge cases

- **Empty description.** The agent isn't fully configured. Stop and point the user at `cekura-create-agent` to populate it before iterating. The skill cannot diagnose a missing prompt.
- **No mock tools.** Continue — many pipecat agents are conversational only. Record `mock_tools: []` and skip tool-config considerations in Phase 3.
- **One-line / placeholder description.** If the description is clearly a stub ("My pipecat agent", a single sentence), stop and ask whether this is the production prompt. Don't iterate against a stub — every edit will look like a "gap."
- **Description out of sync with live agent.** The user may have evolved their pipecat code without updating Cekura. Surface this risk in the Phase 1.3b summary and ask once: "Does the description above match what your live pipecat agent is currently running?" If no, recommend they sync Cekura first (paste the current production prompt into the description) before iterating — otherwise Phase 3 will diagnose against a stale baseline.
- **Multi-pipeline agents.** If the user runs multiple pipecat pipelines under one Cekura agent record, treat the single description as the unified prompt for diagnosis. There is no per-pipeline scoping in Cekura today; surface this as a known limitation if the failure cluster suggests one pipeline is the culprit.

## Phase 4.1b — apply order

1. Mock-tool edits via `mcp__cekura__aiagents_tool_partial_update` (one call per edited tool).
2. New mock-tool creation via `mcp__cekura__aiagents_tools_create` (one call per new tool).
3. Description edit via `mcp__cekura__aiagents_partial_update` (one call). For descriptions over ~4 KB, fall back to direct API:

```
curl -X PATCH \
  -H "X-CEKURA-API-KEY: $CEKURA_API_KEY" \
  -H "Content-Type: application/json" \
  -d @/tmp/agent_patch.json \
  https://api.cekura.ai/test_framework/v2/aiagents/<agent_id>/
```

where `/tmp/agent_patch.json` contains `{"description": "<new prompt>"}`.

4. **Redeploy step** (see Phase 4.1b — redeploy below). This runs after the Cekura PATCH has landed and before Step 4.2 sync verification.

## Phase 4.1b — redeploy

Three paths depending on `redeploy_command` (collected in main SKILL.md Step 1.4) and `auto_mode`:

### Path 1: `redeploy_command` is a real shell command — preferred

Execute it via the Bash tool with a generous timeout (default 600s for pipecat; container builds + Pipecat Cloud rollouts are slow). Capture exit code, stdout, stderr.

- **Exit 0** → proceed to Step 4.2 sync.
- **Non-zero exit** → surface stderr + exit code; do NOT proceed to validation. Ask: retry / edit the command (update `redeploy_command` on the run) / abort.
- **Timeout** → surface explicitly; ask whether the command is expected to run longer (bump timeout) or whether something is hung.

Special pipecat caveat: `pcc deploy` (and similar managed-platform commands) often return success **before the new container is actually live** — the command just enqueues a deploy job. If validation immediately after returns identical failures, the Step 4.5 no-change detector surfaces "deploy may not have rolled out yet" as a candidate hypothesis. Consider adding `&& sleep 30` to give the rollout a moment, or `&& pcc status --wait` if the user's tooling supports it.

### Path 2: `redeploy_command == "manual"` (or unset and `auto_mode: false`)

Render the canonical redeploy gate:

```
Cekura agent record updated. Validation runs against your live pipecat agent —
which is still running the *previous* prompt until you redeploy.

Before continuing:
  1. Copy the updated description above into your pipecat agent's system prompt.
  2. If mock-tool definitions changed, mirror those signatures in your pipecat tool implementations.
  3. Redeploy your pipecat agent to Pipecat Cloud (or your own infrastructure).
  4. Confirm the redeploy is live ("done", "redeployed", "yes").

Reply "skip" to validate against the current live agent anyway (the result will reflect
the *old* prompt) or "abort" to halt the loop.
```

Treat any of `"done"`, `"redeployed"`, `"yes"`, `"y"`, `"deployed"` (case-insensitive) as confirmation. `"skip"` continues but flags the iteration as `redeploy_skipped: true`. Anything else, ask once for clarification before treating as abort.

### Path 3: `redeploy_command` unset and `auto_mode: true`

Proceed straight to Step 4.2 sync verification and Step 4.4 validation without pausing. The Step 4.5 no-change detector surfaces stale-state hypotheses after the fact. This is the legacy auto-mode behavior; encourage the user to provide `redeploy_command` next iteration so the loop converges faster.

## Phase 4.2b — sync re-fetch

Re-fetch and verify:

- `mcp__cekura__aiagents_retrieve` → confirm `description` matches the patched value (compare lengths and first/last 200 chars; full-text compare for short descriptions).
- For each edited / created tool: `mcp__cekura__aiagents_tool_retrieve` → confirm `description` and `parameters` match.

There is no "is the live agent running the new prompt?" check available from Cekura. In auto mode (the default), the skill simply runs validation and relies on the Step 4.5 no-change detector to flag stale-state hypotheses after the fact. In `auto_mode: false`, the redeploy gate is the only pre-validation mechanism; if the user replied `"skip"`, carry that flag through Step 4.6 framing.

## Phase 4.6 — pipecat-specific exit framing

When the iteration ran with `redeploy_skipped: true`, the new failure summary is **not** evidence the prompt edit didn't work — it reflects the live agent's *prior* prompt. Surface this clearly:

```
Iteration N validation completed without a redeploy.
The failures below describe your *current live* pipecat agent, which is still
running the prompt from before this iteration's edits.

Before treating these failures as Phase 3 input, redeploy your pipecat agent
with the iteration N description and re-run validation.
```

Do not feed `redeploy_skipped` failure sets into the next Phase 3 — they will produce phantom edits stacked on top of changes that haven't taken effect yet.

When two consecutive iterations show identical failures (same scenarios, same transcript shapes), surface the redeploy-omission hypothesis even if the user nominally confirmed redeploy:

```
The failures from iteration N look identical to iteration N-1. The most likely
cause is that the live pipecat agent didn't pick up the new prompt — possibly the
redeploy didn't actually go out, or pipecat's deployment is caching the old
container. Please verify your live agent is running the iteration N description
before continuing.
```

## Anti-patterns specific to pipecat mode

- **Rendering the redeploy gate in auto mode.** In `auto_mode: true` (the default), the gate is intentionally skipped — the skill runs validation immediately after PATCH. Rendering the multi-step "before continuing, redeploy your server" block breaks the autonomous loop. The Step 4.5 no-change detector handles stale-state cases after the fact. (In `auto_mode: false`, the gate fires on every iteration including the first — that's the trade-off the user explicitly opted into.)
- **Treating mock-tool edits as live-tool edits.** The agent's real tool implementations live in pipecat code. A mock-tool description change tells future test runs what the contract should be; it does not change the agent's behavior on its own. When a mock-tool change matters for Phase 3 reasoning, also surface a hand-off asking the user to update the pipecat tool implementation to match.
- **Proposing VAPI-shaped edits in pipecat mode.** Spoken `messages` (`request-start`, `request-complete`, `request-failed`), handoff `destinations`, squad `model.toolIds` — none of these exist in pipecat. Phase 3 must filter these edit candidates out before presenting to the user.
- **Diagnosing "literal `{{variable}}` survived" without confirming it.** Pipecat doesn't expose the rendered system message the way VAPI does. If a failure transcript shows the agent saying `{{customerName}}`, that's clear evidence; if you're inferring it from indirect signals, mark the diagnosis as "suspected upstream — runtime state not observable" rather than presenting it as confirmed.
