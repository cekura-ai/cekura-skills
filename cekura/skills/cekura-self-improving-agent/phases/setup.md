# Setup Phase — Verify Agent and Provider Support

This phase runs **once per invocation**, before any optimization sub-phase or the Eval phase. It resolves the run mode, loads the agent the loop will edit against (its provider config and where its prompt lives), and (for self-hosted live targets) collects the `redeploy_command` that lets auto-mode run end-to-end.

**Setup's fetch surface is the agent only — prompt + tool config.** Do NOT fetch failure data (`results_retrieve` / `runs_bulk_retrieve` / `call_logs_retrieve` / `scenarios_retrieve`) here, even if the user supplied `result_id` / `run_ids` / `call_ids` / `scenario_ids`. Failure data is Collect's job — fetching it in Setup produces work against premature assumptions and conflates phase responsibilities.

The optimization Collect sub-phase must not begin until every step in this file is complete. The Pre-flight check at the top of [`optimization/collect.md`](optimization/collect.md) enforces this; if you find yourself entering Collect without all of these resolved, return here and finish setup first.

## Step 1.1 — Resolve the run mode

Branch on the user's input shape:

- The user supplied a `prompt` (pasted text or file path) **and** no `agent_id`, OR they supplied a `prompt` plus an explicit `mode: self_hosted, self_hosted_flavor: websocket, websocket_variant: offline` → resolve to **self-hosted / websocket / offline** and skip to Step 1.3 (per the websocket sub-flavor doc).
- The user supplied an `agent_id` only → continue with Step 1.2.
- The user supplied both an `agent_id` and a `prompt` without specifying a mode → ask once which they want: provider mode (skill PATCHes the live agent / edits the source file) or offline variant (skill outputs a rewritten prompt only). Default to provider mode if they accept the default.
- The user supplied neither → ask for one. If they don't know an agent ID, list their agents so they can pick one.

## Step 1.2 — Fetch agent details and gate on provider (skipped in offline variant)

Retrieve the agent and read `assistant_provider`:

- **`vapi`** → continue down the VAPI branch (Step 1.3a; see [`../providers/vapi/overview.md`](../providers/vapi/overview.md)).
- **`elevenlabs`** → continue down the ElevenLabs branch (Step 1.3c; see [`../providers/elevenlabs/overview.md`](../providers/elevenlabs/overview.md)). Like VAPI, this is a managed-provider fast path — the system prompt and tools are PATCHable directly and edits land live.
- **`pipecat`** → continue down the self-hosted / pipecat branch (Step 1.3b; see [`../providers/self-hosted/pipecat.md`](../providers/self-hosted/pipecat.md)).
- **`self_hosted`, `custom`, `agentforce`, or any other unrecognized non-managed tag** → enter the self-hosted sub-flavor router (see [`../providers/self-hosted/overview.md`](../providers/self-hosted/overview.md)). Ask the user which of `pipecat`, `websocket`, or `database` matches their setup. If they say none and don't want to iterate offline, halt.
- **`retell`, `livekit`, `sip`, or missing/empty** → the provider is unclear. Ask the user where the live prompt lives before falling through to offline. Present the full sub-flavor menu (`vapi` / `elevenlabs` / `pipecat` / `websocket` / `database` / `offline`) — see [`../providers/self-hosted/database.md`](../providers/self-hosted/database.md) § "Database-flavor gate (Phase 1.2 — provider clarification)" for the canonical prompt wording. Route per the user's answer (database → continue at Step 1.3d). Fall back to offline only if the user explicitly picks it.

`retell` is in the unsupported list on purpose — Retell handling is temporarily disabled. Do not bypass the gate for direct PATCHing. If `assistant_provider` is empty, ask the provider-clarification question described above rather than guessing or defaulting silently. Compare lowercased — be defensive against mixed-case input (`ElevenLabs`, `VAPI`).

Track the resolved mode and sub-flavor on the run; every later phase branches on them.

For the exact VAPI error-message shape, the Retell-specific note, and 404 handling, see [`../providers/vapi/phase-1-fetch.md`](../providers/vapi/phase-1-fetch.md). For the self-hosted sub-flavor router, see [`../providers/self-hosted/overview.md`](../providers/self-hosted/overview.md).

## Step 1.3 — Fetch the agent (branch by mode)

Each branch's full procedure lives in its provider doc. In each branch you fetch the agent's provider config + tool/tool-definitions surface AND locate where its prompt lives — but you do NOT read failure data here.

- **VAPI** — [`../providers/vapi/overview.md`](../providers/vapi/overview.md) (with [`../providers/vapi/phase-1-fetch.md`](../providers/vapi/phase-1-fetch.md) for curl bodies + edge cases). VAPI is authoritative; the Cekura `description` is informational only. Pulls the live `/assistant/{id}` (or squad) plus every referenced `/tool/{id}` using `VAPI_KEY`.
- **ElevenLabs** (Step 1.3c) — [`../providers/elevenlabs/overview.md`](../providers/elevenlabs/overview.md) (with [`../providers/elevenlabs/phase-1-fetch.md`](../providers/elevenlabs/phase-1-fetch.md) for curl bodies + edge cases). ElevenLabs is authoritative; the Cekura `description` is informational only. Pulls the live `/v1/convai/agents/{id}` plus every referenced `/v1/convai/tools/{id}` using `ELEVENLABS_API_KEY` (`xi-api-key` header). The `assistant_id` on the Cekura record is the ElevenLabs `agent_id`.
- **Self-hosted / pipecat** — [`../providers/self-hosted/pipecat.md`](../providers/self-hosted/pipecat.md). The agent's Cekura record (`description` + mock-tool list) is authoritative. The live pipecat agent is not introspectable.
- **Self-hosted / websocket** — [`../providers/self-hosted/websocket.md`](../providers/self-hosted/websocket.md). `file` variant: **locate** the user's live source file (the system prompt is a string constant; tool definitions usually live in the same file) — record the path; the Diagnose phase reads its content. `offline` variant: pasted prompt text, read-only.
- **Self-hosted / database** (Step 1.3d) — [`../providers/self-hosted/database.md`](../providers/self-hosted/database.md). Collect DB type, credentials, fetch query (and optional write query) per the setup questions in that file, then run the fetch query and record the current prompt + tool definitions (if also in the DB). The user's DB row is authoritative; the Cekura record is informational only. Credentials are in-memory for the run only — never echoed back, persisted, or logged.

Each branch ends by surfacing a compact summary to the user before moving on to Step 1.4 (self-hosted) or the Optimization phase (VAPI / ElevenLabs — both skip Step 1.4).

## Step 1.4 — Collect the redeploy command (self-hosted modes only) — HARD GATE

Skipped for VAPI and ElevenLabs (both are managed providers — edits land live; nothing to redeploy) and for the websocket `offline` variant (no live agent at all). For **every other self-hosted run** (pipecat + websocket / `file` variant), this step is a **hard gate**: do NOT proceed to the Optimization phase until the `redeploy_command` field is resolved to one of three explicit values — a shell command, the literal `"manual"`, or an explicit user-confirmed "no live target to restart" (rare; usually means the run should have been routed to `offline` variant instead). Skipping Step 1.4 and hoping the user restarts their server between iterations is the single most common reason this skill produces phantom "prompt edits didn't help" iterations — the edits never reached the running process, but the no-change detector in the Eval phase only catches it after the fact, by which point an iteration of cap is already burned.

Auto mode does NOT exempt this step. `auto_mode: true` skips per-iteration *diff approval* and per-iteration *user-side restart pauses*; it does not skip the one-time setup question that defines HOW the restart happens. Asking once at Step 1.4 is precisely what enables auto-mode to be autonomous — without it, auto-mode is strictly worse than `auto_mode: false`, because non-auto would at least have paused at each iteration's apply step for a manual restart.

**Session-level "no clarifying questions" / "work without stopping" directives do NOT exempt this step either.** Some sessions arrive with a global instruction telling the assistant to make reasonable calls instead of pausing for clarifications mid-execution. That directive applies to *routine* clarifications and minor judgement calls; it does NOT override the one-time foundational setup question that defines HOW restarts happen. **Ask Step 1.4 anyway**, even when such a directive is in effect. Silently defaulting to `"manual"` (or to any other value) under a "no clarifying questions" instruction is a misread of the directive's scope — it produces the strictly-worst outcome documented above (no per-iteration restart, no end-to-end automation). The cost of one clarifying question at Setup is negligible; the cost of guessing wrong is the entire loop running phantom iterations. If the directive's source genuinely intends to suppress this question too, the user will redirect on seeing it; do not pre-empt that.

For self-hosted modes with a live target, the live agent does not pick up prompt or tool-config changes until the user redeploys / restarts. The skill can either run that step automatically each iteration (preferred, fully autonomous) or pause on a manual restart gate (the legacy behavior).

If `redeploy_command` is already provided in the run inputs, use it. Otherwise, ask the user exactly once:

```
For end-to-end automation, I can run your redeployment automatically after each
prompt edit so the live agent is ready before re-validation. What shell command
(or commands) restarts your live agent?

Examples:
  Local Python websocket server:    pkill -f main.py; nohup python main.py &
  Docker compose:                   docker compose restart agent
  systemd:                          sudo systemctl restart my-agent
  SSH'd remote host:                ssh user@host 'systemctl restart agent'
  Pipecat Cloud:                    pcc deploy
  Fly.io:                           fly deploy --strategy immediate

Reply with the shell command, OR reply "manual" if you'd rather restart the
agent yourself between iterations (I'll pause and ask "done" before each
re-validation).
```

Record the resolved `redeploy_command` on the run. Treat the literal `"manual"` (case-insensitive) as a sentinel meaning "user-driven restart gate every iteration" — that branch is the iter-pause behavior documented in each sub-flavor doc's Phase 4.1.

When the user provides a real command, treat it as a contract: the skill will execute it after every iteration's apply step (in the Optimization phase, before validation in the Eval phase). The user is responsible for the command being correct and idempotent; the skill is responsible for running it, capturing exit code + stderr, and failing loudly if it errors. Backgrounded servers (`nohup ... &`, `disown`) are fine — the Bash tool returns once the foreground portion completes.

For the full collection-prompt wording, sentinel handling, command-execution semantics, and how to handle "the command is multi-step or interactive" edge cases, see [`../providers/self-hosted/overview.md`](../providers/self-hosted/overview.md) § "Redeploy command flow".

## Setup completion checklist

Before handing off to the Optimization phase, confirm:

- [ ] Mode and sub-flavor resolved (`vapi` / `elevenlabs` / `pipecat` / `websocket-file` / `websocket-offline` / `database`)
- [ ] Agent loaded (VAPI: `/assistant/{id}` + referenced tools; ElevenLabs: `/v1/convai/agents/{id}` + referenced `/v1/convai/tools/{id}`; pipecat: Cekura agent record's `description` + mock-tool list; websocket-file: the correct live source file path located and confirmed via grep when ambiguous — content stays unread until Diagnose; database: `db_type` + `db_connection` (env var or inline) + `db_fetch_query` recorded, fetch query executed, current prompt captured)
- [ ] **Self-hosted live target**: `redeploy_command` resolved to a shell command, `"manual"`, or — database sub-flavor only — `"noop"` when the live agent re-reads on every request (N/A for VAPI / ElevenLabs)
- [ ] I have NOT fetched any failure data (`results_retrieve` / `runs_bulk_retrieve` / `call_logs_retrieve` / `scenarios_retrieve`) — that belongs to Collect

If any of the above is unresolved, ask the user the specific clarifying question and wait for an answer before entering the Optimization phase.
