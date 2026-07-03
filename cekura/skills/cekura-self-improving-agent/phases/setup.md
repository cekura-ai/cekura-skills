# Setup Phase — Resolve the Target

Runs **once per invocation**, before Reproduce / Optimization / Eval. Setup resolves the run's **target** — the three axes that let one loop serve every provider and fix surface:

- **Editable surface** — where the fix lands: system prompt / tool config / (self-hosted) owned source code the run-setup points to (source file / DB row / Cekura mock tools / pasted text).
- **Apply path** — how an edit goes live: provider API PATCH (VAPI / ElevenLabs, live immediately) · `Edit` + `redeploy_command` · live-on-save (`"noop"`) · **offline / PR** (code-fix) · **render-only** (print the rewrite).
- **Validation** — how a fix is proven later: Cekura scenarios (simulation) or a code test suite. Setup only records which; it does not run either.

Setup also records the **signal shape** (`input_is_prod_call`), collects the `redeploy_command` (hard gate, Step 1.4) where a live target exists, and persists newly-collected run-setup to `.claude/MEMORY.md` (Step 1.4a).

**Prod-call inputs route through Collect → Debug → Reproduce** (the `3→4→5` loop in SKILL.md). When the input is `call_ids`, or a `result_id` / `run_ids` pointing at **production call logs**, set `input_is_prod_call = true`. After Setup, the orchestrator enters [`collect.md`](collect.md) — which anchors the kept-failure set on the FAIL'd verdict(s) — then [`debug.md`](debug.md) to root-cause them, then [`reproduce.md`](reproduce.md). Setup only records the input shape; Collect fetches and Debug diagnoses.

**Setup's fetch surface is the agent only — prompt + tool config.** Do NOT fetch failure data (`results_retrieve` / `runs_bulk_retrieve` / `call_logs_retrieve` / `scenarios_retrieve`) here, even if the user supplied IDs. Failure data is Collect's job. The Pre-flight check at the top of [`collect.md`](collect.md) enforces that Collect cannot start until every step below is complete.

## Step 1.0 — Check project memory FIRST

Before resolving mode (1.1) or fetching the agent (1.2–1.3): walk from the current directory upward to the filesystem root, checking each directory for `.claude/CLAUDE.md` and `.claude/MEMORY.md`, and **use the first one found that contains the run-setup** (stop searching once you have it). They hold the run-setup — how the agent is run, redeployed, and connected to a Cekura simulation — recorded in any form (session notes, step list). Read the contents; don't match a heading.

**User-documented setup is authoritative over the Cekura agent record.** The live prompt/code location, redeploy command, launch + connect steps, and which local bot serves a given Cekura agent can all differ from the record's stored fields. Resolve mode, source location, redeploy command, and simulation-launch/connect path from memory; fall back to the record only for what memory omits.

Do **NOT** treat the record's configured connection URL (`telephony.websocket_url`, `chat_agent_details.config.url`) as the reproduction/redeploy target — it reflects whatever instance was last connected. The target is governed by the memory run-setup (Step 1.4), typically a bot you stand up **locally** and point a fresh Cekura run at. Do not manufacture a "the live agent is on someone else's machine, I can't redeploy" blocker from a stored URL.

If no run-setup is found, proceed through 1.1–1.4 and persist what you collect (1.4a).

## Step 1.1 — Resolve the apply path from the input shape

Branch on the user's input:

- `prompt` (text or file) **and** no `agent_id`, OR `prompt` + `mode: self_hosted` with no reachable live target → **render-only** (apply path = print the rewrite; no live agent to edit/validate). Skip to Step 1.3.
- **Diagnosed code bug** (source file + supplied root cause, ± the originating call) → **code-fix**: editable surface = that owned source file, apply path = **offline / PR** (no live redeploy — the Step 1.4 hard gate is satisfied by `redeploy_command = "noop"`/offline), validation = a **test suite**. The supplied root cause is consumed as-is, not re-derived. Resolve `mode: self_hosted` and continue at Step 1.3 (self-hosted branch) to locate/record the source file.
- `agent_id` only → Step 1.2.
- `agent_id` **and** `prompt` without a mode → ask once: operate against the live agent (PATCH / edit per run-setup) or render-only. Default to live agent.
- Neither → ask. If they don't know an agent ID, list their agents.

## Step 1.2 — Fetch agent details and gate on provider (skipped when render-only)

Retrieve the agent, read `assistant_provider` (compare lowercased — defend against `ElevenLabs`, `VAPI`):

- **`vapi`** → VAPI branch (Step 1.3a; [`../providers/vapi/overview.md`](../providers/vapi/overview.md)). Managed: prompt + tools PATCHable, edits live.
- **`elevenlabs`** → ElevenLabs branch (Step 1.3c; [`../providers/elevenlabs/overview.md`](../providers/elevenlabs/overview.md)). Managed: same fast path.
- **Anything else** (`self_hosted`, `custom`, `agentforce`, other non-managed / unrecognized) → resolve **`mode: self_hosted`** and read the run-setup (Step 1.3; [`../providers/self-hosted/overview.md`](../providers/self-hosted/overview.md)). No further routing question — the run-setup defines explore/edit/redeploy/validate. No run-setup and no live target → render-only; if neither is workable, halt.
- **`retell`, `livekit`, `sip`, or missing/empty** → live target unclear. Ask how the agent is run (menu: `vapi` / `elevenlabs` / `self_hosted`; self_hosted details live in memory). Fall back to render-only only if the user explicitly picks it.

`retell` is unsupported on purpose (temporarily disabled) — do not bypass the gate for direct PATCHing. Never default silently on empty `assistant_provider`; ask.

Track the resolved mode; every later phase branches on it. VAPI error-shape / Retell note / 404 handling: [`../providers/vapi/phase-1-fetch.md`](../providers/vapi/phase-1-fetch.md).

## Step 1.3 — Fetch the agent (branch by mode)

Fetch the agent's provider config + tool surface only — **no failure data**. Each branch's full procedure is in its provider doc; the provider config is authoritative, the Cekura `description` is informational only.

- **VAPI** — [`../providers/vapi/overview.md`](../providers/vapi/overview.md) (+ [`phase-1-fetch.md`](../providers/vapi/phase-1-fetch.md) for curl bodies/edge cases). Pulls live `/assistant/{id}` (or squad) + every referenced `/tool/{id}` via `VAPI_KEY`.
- **ElevenLabs** (Step 1.3c) — [`../providers/elevenlabs/overview.md`](../providers/elevenlabs/overview.md) (+ [`phase-1-fetch.md`](../providers/elevenlabs/phase-1-fetch.md)). Pulls live `/v1/convai/agents/{id}` + referenced `/v1/convai/tools/{id}` via `xi-api-key`. Cekura `assistant_id` = ElevenLabs `agent_id`.
- **Self-hosted** — [`../providers/self-hosted/overview.md`](../providers/self-hosted/overview.md). The **run-setup** is authoritative: it names the editable surface (source file / DB row / Cekura mock tools / pasted text) and how to read it. Explore and record it; content stays otherwise unread until Fix. For a **code-fix**, the surface is the supplied source file. For a **DB row**, collect connection details (type, credentials, fetch/write queries) before any read — credentials stay in-memory for the run only, never echoed, persisted, or logged. If the run-setup is silent on where to look, ask.

Each branch ends by surfacing a compact summary, then → Step 1.4 (self-hosted) or the **Clone phase** ([`clone.md`](clone.md)) (VAPI / ElevenLabs skip 1.4 and clone before Collect, so edits land on a disposable copy).

## Step 1.4 — Resolve the redeploy command — HARD GATE

**Applies to self-hosted.** Do NOT enter Optimization until `redeploy_command` is one of:

- a **shell command** (self-hosted live target),
- `"manual"` — user-driven restart gate every iteration,
- `"noop"` — the edit is live the moment it lands (DB re-read per request; **also** the code-fix / offline / render-only case, where the harness is a failing test and there is no live restart to run),
- an explicit user-confirmed "no live target to restart" (rare; usually means render-only instead).

Skipped only for VAPI / ElevenLabs (managed — nothing to redeploy). For **code-fix / offline / render-only** the gate is satisfied without a live restart command (`"noop"`/offline) — record it and move on.

Skipping this gate for a live target is the top cause of phantom "prompt edits didn't help" iterations: edits never reach the running process, and the Eval no-change detector only catches it after an iteration of cap is burned.

**Neither auto mode nor a "no clarifying questions" directive exempts this step.** `auto_mode: true` skips per-iteration *diff approval* and *restart pauses*, not the one-time question that defines HOW the restart happens — asking once here is exactly what makes auto-mode autonomous. Session-level "work without stopping" directives cover *routine* clarifications, not this foundational one. Ask it anyway; silently defaulting to `"manual"` produces the strictly-worst outcome (no per-iteration restart, no end-to-end automation). If the directive's source truly meant to suppress it, the user will redirect.

**Resolution order:** run inputs → run-setup already read in Step 1.0 (confirm back in one line: "Using the run setup saved in `.claude/MEMORY.md`: …" so a stale entry can be corrected) → only if none found, ask exactly once:

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

Record the resolved value (case-insensitive sentinels). A real command is a contract: the skill runs it after every apply step (before Eval validation), capturing exit code + stderr and failing loudly on error. Backgrounded servers (`nohup … &`, `disown`) are fine — Bash returns once the foreground portion completes. Full wording, sentinel handling, execution semantics, and multi-step/interactive edge cases: [`../providers/self-hosted/overview.md`](../providers/self-hosted/overview.md) § "Redeploy command flow".

### Step 1.4a — Persist the run setup to project memory — do this BEFORE proceeding

When the run setup was **collected from the user this session** (not loaded from memory above), **write it to `.claude/MEMORY.md` in the current directory before the next phase** so future invocations don't re-ask. Create the file (and its `.claude/` directory) if absent; write to `.claude/CLAUDE.md` instead if the user prefers (ask once if unclear). Append or update in place a clearly-labeled run-setup section — findability matters, not the exact heading:

```markdown
## Agent run setup (launch, connect, redeploy)

- redeploy_command: <the exact shell command, or "manual" / "noop">
<!-- self-hosted live targets — how to run the main-agent simulation and wire it to a Cekura run: -->
- Launch the main agent: <start command(s) / which config file to edit / env vars>
- Connect to a Cekura simulation: <how Cekura connection details reach the agent —
  outbound number / SIP URI for telephony, or the WebRTC token, and where it goes>
- Notes: <ports, env vars, anything else needed to reproduce a run>
```

Capture the **simulation-launch** lines (start the main agent + pass it the per-run connection details Cekura returns) alongside the redeploy command — Reproduce and Eval both need them to run a self-hosted simulation. If only a redeploy command was given and the launch steps are still unknown when the first run is about to happen, ask (and persist) then, not a silent guess. (Code-fix / render-only runs have no live-simulation launch to capture.)

**Confirm the write succeeded** before continuing. Do NOT echo or persist secrets — DB credentials stay in-memory for the run only; persist only non-secret launch/redeploy steps, referencing credentials by env-var name. This is part of the Step 1.4 hard gate: a self-hosted run must not enter Optimization with run setup collected but not saved.

## Setup completion checklist

Before Clone (VAPI / ElevenLabs) or Optimization (all other modes), confirm:

- [ ] **Project memory checked FIRST** (1.0): `.claude/CLAUDE.md` / `.claude/MEMORY.md` (current dir upward) read, used as authoritative where present (mode, source location, redeploy command, simulation-launch/connect path); the record's configured URL was NOT treated as a redeploy/reproduction target
- [ ] Mode resolved (`vapi` / `elevenlabs` / `self_hosted`)
- [ ] **Three axes resolved** — editable surface, apply path (PATCH / redeploy / `"noop"` / offline-PR / render-only), and validation mechanism (scenarios or test suite)
- [ ] Agent loaded (VAPI: `/assistant/{id}` + tools; ElevenLabs: `/v1/convai/agents/{id}` + `/v1/convai/tools/{id}`; self_hosted: editable surface explored per run-setup and recorded — source file / DB row / Cekura mock tools / pasted text; for a DB row, `db_type` + `db_connection` + `db_fetch_query` recorded and the fetch query executed; content otherwise unread until Fix; Cekura `description` informational only)
- [ ] **Self-hosted**: `redeploy_command` resolved to a shell command, `"manual"`, or `"noop"` (the latter also covers code-fix / offline / render-only, where no live restart runs; N/A for VAPI / ElevenLabs)
- [ ] **Self-hosted**: run setup either loaded from `.claude/CLAUDE.md` / `.claude/MEMORY.md`, OR — if collected this session — **persisted** (1.4a), write confirmed, no secrets written
- [ ] I have NOT fetched any failure data (`results_retrieve` / `runs_bulk_retrieve` / `call_logs_retrieve` / `scenarios_retrieve`) — that belongs to Collect

If any item is unresolved, ask the specific clarifying question and wait before entering Clone (VAPI / ElevenLabs) or Optimization (all other modes).
