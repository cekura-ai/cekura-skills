# Setup Phase — Verify Agent and Provider Support

This phase runs **once per invocation**, before the Reproduce phase, any optimization sub-phase, or the Eval phase. It resolves the run mode, loads the agent the loop will edit against (its provider config; for `self_hosted`, the run-setup in `memory.md` / `CLAUDE.md` defines how the agent is explored, edited, redeployed, and simulated), records whether the input is a **production call** (which routes through the Reproduce phase), and (for self-hosted live targets) collects the `redeploy_command` that lets auto-mode run end-to-end.

**Prod-call inputs route through Reproduce.** When the input is `call_ids`, or a `result_id` / `run_ids` that point at **production call logs** rather than Cekura simulation runs, record `input_is_prod_call = true` on the run. After Setup (and Clone, for VAPI / ElevenLabs), the orchestrator enters the [`reproduce.md`](reproduce.md) phase, which auto-builds the reproduction harness and gates on a definitive FAIL before the Optimization loop begins. Scenario / simulation-run inputs and the render-only (no-live-target) case skip the harness-building parts of Reproduce (see that file's "when this phase does real work vs. passes through"). Setup does NOT itself fetch the call log — that's Reproduce's job; Setup only records the input shape.

**Setup's fetch surface is the agent only — prompt + tool config.** Do NOT fetch failure data (`results_retrieve` / `runs_bulk_retrieve` / `call_logs_retrieve` / `scenarios_retrieve`) here, even if the user supplied `result_id` / `run_ids` / `call_ids` / `scenario_ids`. Failure data is Collect's job — fetching it in Setup produces work against premature assumptions and conflates phase responsibilities.

The optimization Collect sub-phase must not begin until every step in this file is complete. The Pre-flight check at the top of [`optimization/collect.md`](optimization/collect.md) enforces this; if you find yourself entering Collect without all of these resolved, return here and finish setup first.

## Step 1.0 — Check project memory FIRST (before resolving mode or fetching the agent)

Before anything else — before resolving the run mode (Step 1.1) and before fetching the Cekura agent (Steps 1.2–1.3) — **search the project for `memory.md` and `CLAUDE.md`** (at the project root, and the current sub-directory if different) and **read them**. These files contain the run-setup instructions — how the agent is run, redeployed, and connected to a Cekura simulation. They may be recorded in any form (free-form session notes, a list of steps, etc.), so read the file contents to find them rather than matching a specific heading or block name.

**User-documented setup takes priority over the Cekura-configured agent.** A real agent setup is frequently more complicated than what is configured on Cekura — the live prompt/code location, the redeploy command, the launch + connect steps, and even which local bot serves a given Cekura agent can all differ from the agent record's stored fields. When the memory files describe the setup, treat **that** as authoritative and resolve mode, source location, redeploy command, and the simulation-launch/connect path from it; fall back to the Cekura agent record only for what the memory files do not specify.

In particular, do **NOT** treat the agent record's configured connection URL (e.g. `telephony.websocket_url`, `chat_agent_details.config.url`) as the reproduction or redeploy target. That field reflects whatever instance was last connected; the reproduction/redeploy target is governed by the memory run-setup (Step 1.4) — typically a bot you stand up **locally** and point a fresh Cekura run at. Manufacturing a "the live agent is on someone else's machine, I can't redeploy" blocker from a stored URL is a misread: the URL is informational, the memory block is authoritative.

If no run-setup instructions are found, proceed normally through Steps 1.1–1.4 and persist whatever setup you collect (Step 1.4a) so the next invocation finds it here.

## Step 1.1 — Resolve the run mode

Branch on the user's input shape:

- The user supplied a `prompt` (pasted text or file path) **and** no `agent_id`, OR they supplied a `prompt` plus an explicit `mode: self_hosted` with no reachable live target → resolve to **self_hosted, render-only** (no live agent to edit/validate against) and skip to Step 1.3.
- The user supplied an `agent_id` only → continue with Step 1.2.
- The user supplied both an `agent_id` and a `prompt` without specifying a mode → ask once which they want: operate against the live agent (skill PATCHes the managed agent / edits per the run-setup) or render-only (skill outputs a rewritten prompt only). Default to operating against the live agent if they accept the default.
- The user supplied neither → ask for one. If they don't know an agent ID, list their agents so they can pick one.

## Step 1.2 — Fetch agent details and gate on provider (skipped when render-only)

Retrieve the agent and read `assistant_provider`:

- **`vapi`** → continue down the VAPI branch (Step 1.3a; see [`../providers/vapi/overview.md`](../providers/vapi/overview.md)).
- **`elevenlabs`** → continue down the ElevenLabs branch (Step 1.3c; see [`../providers/elevenlabs/overview.md`](../providers/elevenlabs/overview.md)). Like VAPI, this is a managed-provider fast path — the system prompt and tools are PATCHable directly and edits land live.
- **Anything else** — `self_hosted`, `custom`, `agentforce`, or any other non-managed / unrecognized tag → resolve **`mode: self_hosted`** and **read the run-setup** (Step 1.3; see [`../providers/self-hosted/overview.md`](../providers/self-hosted/overview.md)). There is **no further routing question** — the run-setup defines how the agent is explored, edited, redeployed, and simulated. If there is no run-setup and the user has no live target to edit/validate against, resolve render-only; if neither is workable, halt.
- **`retell`, `livekit`, `sip`, or missing/empty** → the live target is unclear. Ask the user how the agent is run before proceeding. Present the menu (`vapi` / `elevenlabs` / `self_hosted`); for `self_hosted`, the run-setup in `memory.md` / `CLAUDE.md` carries the operating details. Fall back to render-only only if the user explicitly picks it.

`retell` is in the unsupported list on purpose — Retell handling is temporarily disabled. Do not bypass the gate for direct PATCHing. If `assistant_provider` is empty, ask the clarification question described above rather than guessing or defaulting silently. Compare lowercased — be defensive against mixed-case input (`ElevenLabs`, `VAPI`).

Track the resolved mode on the run; every later phase branches on it (`vapi` / `elevenlabs` / `self_hosted`).

For the exact VAPI error-message shape, the Retell-specific note, and 404 handling, see [`../providers/vapi/phase-1-fetch.md`](../providers/vapi/phase-1-fetch.md). For the self-hosted operating model, see [`../providers/self-hosted/overview.md`](../providers/self-hosted/overview.md).

## Step 1.3 — Fetch the agent (branch by mode)

Each branch's full procedure lives in its provider doc. In each branch you fetch the agent's provider config + tool/tool-definitions surface — but you do NOT read failure data here.

- **VAPI** — [`../providers/vapi/overview.md`](../providers/vapi/overview.md) (with [`../providers/vapi/phase-1-fetch.md`](../providers/vapi/phase-1-fetch.md) for curl bodies + edge cases). VAPI is authoritative; the Cekura `description` is informational only. Pulls the live `/assistant/{id}` (or squad) plus every referenced `/tool/{id}` using `VAPI_KEY`.
- **ElevenLabs** (Step 1.3c) — [`../providers/elevenlabs/overview.md`](../providers/elevenlabs/overview.md) (with [`../providers/elevenlabs/phase-1-fetch.md`](../providers/elevenlabs/phase-1-fetch.md) for curl bodies + edge cases). ElevenLabs is authoritative; the Cekura `description` is informational only. Pulls the live `/v1/convai/agents/{id}` plus every referenced `/v1/convai/tools/{id}` using `ELEVENLABS_API_KEY` (`xi-api-key` header). The `assistant_id` on the Cekura record is the ElevenLabs `agent_id`.
- **Self-hosted** — [`../providers/self-hosted/overview.md`](../providers/self-hosted/overview.md). The **run-setup** in `memory.md` / `CLAUDE.md` is authoritative — it defines where the editable surface lives (a source file, a database row, the Cekura mock-tool record, or pasted text) and how to read it. Explore what the run-setup points to and record it; the Cekura `description` is informational only. If the editable surface is a database row, collect the DB connection details (type, credentials, fetch/write queries) before any read attempt; credentials are in-memory for the run only — never echoed back, persisted, or logged. If the run-setup is silent on where to look, ask the user.

Each branch ends by surfacing a compact summary to the user before moving on to Step 1.4 (self-hosted) or the **Clone phase** ([`clone.md`](clone.md)) (VAPI / ElevenLabs — both skip Step 1.4 and clone the agent before Collect, so all edits land on a disposable copy rather than the live agent).

## Step 1.4 — Collect the redeploy command (self-hosted modes only) — HARD GATE

Skipped for VAPI and ElevenLabs (both are managed providers — edits land live; nothing to redeploy) and when there is no reachable live target (render-only). For **every self-hosted run with a live target**, this step is a **hard gate**: do NOT proceed to the Optimization phase until the `redeploy_command` field is resolved to one of these explicit values — a shell command, the literal `"manual"`, `"noop"` (the live agent re-reads the new state on every request), or an explicit user-confirmed "no live target to restart" (rare; usually means the run should be render-only instead). Skipping Step 1.4 and hoping the user restarts their server between iterations is the single most common reason this skill produces phantom "prompt edits didn't help" iterations — the edits never reached the running process, but the no-change detector in the Eval phase only catches it after the fact, by which point an iteration of cap is already burned.

Auto mode does NOT exempt this step. `auto_mode: true` skips per-iteration *diff approval* and per-iteration *user-side restart pauses*; it does not skip the one-time setup question that defines HOW the restart happens. Asking once at Step 1.4 is precisely what enables auto-mode to be autonomous — without it, auto-mode is strictly worse than `auto_mode: false`, because non-auto would at least have paused at each iteration's apply step for a manual restart.

**Session-level "no clarifying questions" / "work without stopping" directives do NOT exempt this step either.** Some sessions arrive with a global instruction telling the assistant to make reasonable calls instead of pausing for clarifications mid-execution. That directive applies to *routine* clarifications and minor judgement calls; it does NOT override the one-time foundational setup question that defines HOW restarts happen. **Ask Step 1.4 anyway**, even when such a directive is in effect. Silently defaulting to `"manual"` (or to any other value) under a "no clarifying questions" instruction is a misread of the directive's scope — it produces the strictly-worst outcome documented above (no per-iteration restart, no end-to-end automation). The cost of one clarifying question at Setup is negligible; the cost of guessing wrong is the entire loop running phantom iterations. If the directive's source genuinely intends to suppress this question too, the user will redirect on seeing it; do not pre-empt that.

For self-hosted modes with a live target, the live agent does not pick up prompt or tool-config changes until the user redeploys / restarts. The skill can either run that step automatically each iteration (preferred, fully autonomous) or pause on a manual restart gate (the legacy behavior).

**Use the project memory already read in Step 1.0.** If `redeploy_command` is already provided in the run inputs, use it. Otherwise, use the run-setup instructions found when you read `memory.md` / `CLAUDE.md` in Step 1.0 (recording how to restart / redeploy the live agent and — for self-hosted live targets — how to launch the main-agent simulation and connect it to a Cekura run). If such instructions exist, use them instead of re-asking; confirm them back to the user in one line ("Using the run setup saved in `memory.md`: …") so a stale entry can be corrected. Only if no saved setup is found, ask the user exactly once:

```
For end-to-end automation, I can run your redeployment automatically after each
edit so the live agent is ready before re-validation. What shell command
(or commands) restarts your live agent?

Examples:
  Local Python server:    pkill -f main.py; nohup python main.py &
  Docker compose:         docker compose restart agent
  systemd:                sudo systemctl restart my-agent
  SSH'd remote host:      ssh user@host 'systemctl restart agent'
  Container platform:     <your deploy command>
  DB re-read every req:   noop   (the new state is live the moment the edit lands)

Reply with the shell command, "noop" if the new state is live the moment the
edit lands, or "manual" if you'd rather restart the agent yourself between
iterations (I'll pause and ask "done" before each re-validation).
```

Record the resolved `redeploy_command` on the run. Treat the literal `"manual"` (case-insensitive) as a sentinel meaning "user-driven restart gate every iteration", and `"noop"` as "the edit is live the moment it lands" — both branches are documented in [`../providers/self-hosted/overview.md`](../providers/self-hosted/overview.md) § "Redeploy command flow".

When the user provides a real command, treat it as a contract: the skill will execute it after every iteration's apply step (in the Optimization phase, before validation in the Eval phase). The user is responsible for the command being correct and idempotent; the skill is responsible for running it, capturing exit code + stderr, and failing loudly if it errors. Backgrounded servers (`nohup ... &`, `disown`) are fine — the Bash tool returns once the foreground portion completes.

For the full collection-prompt wording, sentinel handling, command-execution semantics, and how to handle "the command is multi-step or interactive" edge cases, see [`../providers/self-hosted/overview.md`](../providers/self-hosted/overview.md) § "Redeploy command flow".

### Step 1.4a — Persist the run setup to project memory (self-hosted modes) — do this BEFORE proceeding

Whenever the run setup was **collected from the user** this session (i.e., not already loaded from `memory.md` / `CLAUDE.md` above), **write it to `memory.md` at the project root before entering the next phase** so future invocations don't re-ask. Create `memory.md` if it doesn't exist; if the user prefers it in `CLAUDE.md`, write there instead (ask once if unclear which). Append (or update in place) a clearly-labeled run-setup section. The layout below is a suggested format — what matters is that the instructions are findable when the file is read, not the exact heading:

```markdown
## Agent run setup (launch, connect, redeploy)

- redeploy_command: <the exact shell command, or "manual" / "noop">
<!-- self-hosted live targets — how to run the main-agent simulation and wire it to a Cekura run: -->
- Launch the main agent: <start command(s) / which config file to edit / env vars>
- Connect to a Cekura simulation: <how the Cekura connection details are passed to the agent —
  e.g. the outbound number / SIP URI for telephony, or the WebRTC token, and where it goes>
- Notes: <ports, env vars, anything else needed to reproduce a run>
```

Capture the **simulation-launch** lines (how to start the live/main agent and pass it the per-run connection details Cekura returns) in addition to the redeploy command — the Reproduce and Eval phases both need them to run a simulation against a self-hosted agent. If the user only gave a redeploy command and the simulation-launch steps are still unknown when the first run is about to happen, that's a clarifying question to ask (and then persist) at that point, not a silent guess.

**Confirm the write succeeded** before continuing. Do NOT echo or persist secrets — when the editable surface is a database row, credentials stay in-memory for the run only (never written to `memory.md` / `CLAUDE.md`); persist only the non-secret launch/redeploy steps, referencing credentials by env-var name. This step is part of the Step 1.4 hard gate: a self-hosted run should not enter Optimization with run setup that was collected but not saved.

## Setup completion checklist

Before handing off to the Clone phase (VAPI / ElevenLabs) or the Optimization phase (all other modes), confirm:

- [ ] **Project memory checked FIRST** (Step 1.0): `memory.md` / `CLAUDE.md` read for run-setup instructions, and where they exist, used as authoritative over the Cekura agent record (mode, source location, redeploy command, simulation-launch/connect path) — and the agent record's configured URL was NOT treated as a redeploy/reproduction target
- [ ] Mode resolved (`vapi` / `elevenlabs` / `self_hosted`)
- [ ] Agent loaded (VAPI: `/assistant/{id}` + referenced tools; ElevenLabs: `/v1/convai/agents/{id}` + referenced `/v1/convai/tools/{id}`; self_hosted: explored per the run-setup — the editable surface the run-setup points to is recorded (source file / DB row / Cekura mock tools / pasted text); for a DB row, `db_type` + `db_connection` + `db_fetch_query` recorded and the fetch query executed; content otherwise stays unread until Diagnose; the Cekura `description` is informational only)
- [ ] **Self-hosted live target**: `redeploy_command` resolved to a shell command, `"manual"`, or `"noop"` when the live agent re-reads the new state on every request (N/A for VAPI / ElevenLabs)
- [ ] **Self-hosted live target**: run setup was either loaded from existing run-setup instructions in `memory.md` / `CLAUDE.md`, OR — if collected this session — **persisted to `memory.md` / `CLAUDE.md`** (Step 1.4a), with the write confirmed and no secrets written
- [ ] I have NOT fetched any failure data (`results_retrieve` / `runs_bulk_retrieve` / `call_logs_retrieve` / `scenarios_retrieve`) — that belongs to Collect

If any of the above is unresolved, ask the user the specific clarifying question and wait for an answer before entering the Clone phase (VAPI / ElevenLabs) or the Optimization phase (all other modes).
