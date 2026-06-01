# Self-Hosted — Websocket Sub-Flavor

Websocket-flavor agents are custom servers the user runs themselves. The Cekura agent record holds a `websocket_url` (e.g., `wss://...ngrok-free.app`, an internal host, or Pipecat Cloud websocket endpoint that isn't pipecat-native) and an informational `description` that is typically empty or a stub (`.`). The **real** system prompt, tool definitions, and conversation-orchestration code live in the user's source code — typically a Python/Node/Go file that wires up an LLM client, defines a `SYSTEM_PROMPT` string constant (and a `TOOLS` list), manages conversation history, forwards tool calls, and serves a websocket endpoint that Cekura connects to during runs.

This sub-flavor edits the source file directly using the `Edit` tool. Three editable surfaces in the same file: the **system prompt**, the **tool schemas**, and the **orchestration code** (history management, message wiring, state preservation, keepalive plumbing). Validation runs through Cekura — Cekura drives the test scenario, opens a websocket to the user's URL, and captures the transcript exactly the same way as VAPI / pipecat. The user must restart their websocket server before re-validation for edits to take effect.

When no live websocket is reachable (the user is iterating on a prompt offline, the server is down, they don't want the skill touching the file, etc.) this sub-flavor degrades to the pasted-prompt / pasted-failures variant — the skill renders the rewritten prompt and asks the user to re-run their tests externally and paste the new failures back. That degraded variant is documented at the bottom of this file.

Use this reference together with the main SKILL.md and `providers/self-hosted/overview.md`.

## Websocket-flavor gate (Phase 1.2)

After the user picks `websocket` at the self-hosted sub-flavor router (see `overview.md`), confirm one more thing before fetching anything:

```
Websocket sub-flavor confirmed. To edit the live prompt, the skill needs to
read your agent's source file. Two options:

  • "file <path>" → I'll read the file at <path>, locate the system-prompt
                    string + tool definitions, and edit them directly. After
                    each iteration you'll need to restart your websocket
                    server so the new prompt is live before re-validation.
  • "offline"    → I won't touch any file. I'll render the rewritten prompt
                    for you to copy into your system, and you'll re-run your
                    tests externally and paste the new failures back to me.

Pick the first option whenever possible — it's the only path that closes the
loop end-to-end. Pick "offline" only if there's no file I can reach (server
is on a different machine, you're iterating in a notebook, etc.).
```

Record the chosen variant on the run as `websocket_variant: file` or `websocket_variant: offline`. Every later phase branches on it.

## Phase 1.3 — Fetch the source-of-truth artifacts

### Variant: `file`

1. Read the source file with the Read tool. Don't fall back to treating the path as the prompt contents.
2. Locate the system prompt string. Common shapes:
   - Python: `SYSTEM_PROMPT = {"role": "system", "content": """..."""}` — the prompt content is the triple-quoted string.
   - Python: `SYSTEM_PROMPT = """..."""` — single multi-line string constant.
   - Python: `MESSAGES = [{"role": "system", "content": "..."}]` — first system message.
   - JS/TS: `const SYSTEM_PROMPT = \`...\`` — template literal.
   - Other: a `prompts/system.md` or similar that the code reads via `open(...)` — follow the read and edit the *file* the code reads, not the code itself.
3. Locate tool definitions if present in the same file. Common shapes:
   - Python: `TOOLS = [{"type": "function", "function": {...}}, ...]` — OpenAI-style function-call schema.
   - Python: `@tool` decorator on functions — note where each tool description lives (docstring or decorator arg).
   - JS/TS: equivalent arrays of tool descriptors.
4. Locate the **conversation-orchestration block** — this is the editable surface for CodeBug diagnoses in Phase 3. What to scan for:
   - The main message loop (e.g., `async def chat_response(...)` / `async def handle_websocket(...)`).
   - Conversation-history storage and any truncation / slicing logic (`chat_histories[session_id] = [...]`, `if len(history) > N: ...`, sliding-window code).
   - Tool-call orchestration: where the LLM's `tool_calls` are read, dispatched, and where the result is **appended back** to history before the next LLM turn.
   - Message forwarding to Cekura (e.g., `{"role": "Function Call", "data": {...}}` sends).
   - Keepalive / ping logic, retry / backoff blocks, error handlers around the LLM client.
   Capture line ranges for each — Phase 3 references these directly when classifying a failure as CodeBug.
5. Locate any greeting / first-message string if present (e.g., `GREETING = "..."`) — the agent's opening line. Editing this is rarely the right fix but flag it for Phase 3 context.
6. Capture line ranges for everything you'll edit later. Phase 4.1d's `Edit` calls need exact `old_string` matches — track surrounding context so you can produce unique anchors.

If the prompt or tools cannot be located safely (the file's structure isn't obvious, the prompt is constructed from several pieces at runtime, an `os.environ` indirection is in play), stop and ask the user to point at the exact variable / file rather than guessing. A wrong locate makes every iteration a silent no-op.

Treat as **out of scope** for edits (Phase 3 must hand these off, not edit them):
- Business logic / tool implementation bodies — what a tool computes, the math, external-service request shapes, response parsing.
- Security-sensitive code — API keys, OAuth flow, signing, secret management, header generation.
- Dependency / requirements changes, framework upgrades, new imports outside what's already in the file.
- LLM client *configuration* (model name, temperature, max_tokens) — touch only if the user explicitly asks; otherwise hand off.

Orchestration code (history management, message wiring, conversation state, keepalive plumbing) IS in scope — distinct from the "out of scope" list above.

#### Phase 1.3 summary template (variant: `file`)

```
Self-hosted (websocket / file) agent: <agent_name> (id: <agent_id>)
  Provider tag: <assistant_provider>
  Websocket URL: <wss://...>           # informational; live target for validation
  Source file: <abs path>
  System prompt: <N> chars at <file>:<start_line>-<end_line>
  Tool definitions: <M> tools at <file>:<start_line>-<end_line>
    - <tool_name> — <description first 80 chars>
        params: <required keys, or "none">
  Orchestration code located:
    - Message loop: <file>:<start_line>-<end_line>
    - History management / truncation: <file>:<start_line>-<end_line> (window=<N> or "none detected")
    - Tool-call dispatch + result-forwarding: <file>:<start_line>-<end_line>
    - Keepalive / ping logic: <file>:<start_line>-<end_line> or "none detected"
  Greeting / first message: <"line at file:lineno" | "none detected">
  Dynamic-variable placeholders detected in prompt: <list of {{...}} or "none">

Note: This skill will edit the source file directly — prompt, tool schemas,
and orchestration code (history, message wiring, state) are all in scope when
a failure's root cause is in one of those surfaces. Business logic, auth code,
and dependency changes remain out of scope. After each iteration you'll need
to restart your websocket server so the new code is live before re-validation.
In auto mode (the default) the skill triggers re-validation without pausing to
ask you to restart; if results look unchanged across iterations the skill
surfaces a "your server may not have been restarted" hypothesis after the fact.
```

### Variant: `offline`

Used when no live websocket is reachable.

1. Ask the user to paste the system prompt text (or point at a local file path — the skill reads it but does NOT edit it; this variant is read-only for the source).
2. Failure source must be **pasted failures** — `{transcript, expected_outcome, verdict, verdict_explanation}` blocks per failure. If the user instead provides Cekura run IDs / result IDs, ask whether they want to switch to the `file` variant (the file path is the only thing missing for full closed-loop iteration).

#### Phase 1.3 summary template (variant: `offline`)

```
Self-hosted (websocket / offline) agent
  Prompt source: <"pasted text" | "file path (read-only)">
  Prompt length: <N> chars (~<M> tokens)
  Dynamic-variable placeholders detected: <list of {{...}} or "none">
  Failure source: pasted failures (<N> items)

Note: This variant produces a rewritten prompt at every iteration but does
not edit any file or run validation against a live agent. Applying the new
prompt and re-running your tests is your responsibility. The skill will ask
for the next batch of pasted failures after each iteration.
```

## Phase 2.4 — Provider call state inspection

### Variant: `file` (live websocket)

The user's websocket server controls what Cekura sees. The signals available depend on what the user's code reports back:

- **Variable injection** — typically NOT observable. Most websocket agents do not echo `assistantOverrides.variableValues` back to Cekura, and the rendered system message lives in-process. Treat substitution as not-observable unless the agent's transcript literally shows `{{varName}}` or the user's code is known to forward a rendered prompt to Cekura.
- **Tool calls** — the convention for self-hosted websocket agents is to send `{"role": "Function Call", "data": {...}}` and `{"role": "Function Call Result", "data": {...}}` messages to Cekura when tools fire (see `main.py`-style implementations). When present, tool-call arguments are recoverable from the transcript. When absent, treat tool-call observability as the same as the transcript itself.
- **Transcript** — always available, the same way it is for VAPI / pipecat.

Mark anything not observable as such in Phase 3 ("suspected upstream — runtime state not observable") rather than guessing.

### Variant: `offline` (pasted failures)

Only signals 3 and 4-partial are available — what the transcript shows and what the verdict says. Treat any literal `{{varName}}` appearing in the pasted transcript as the only substitution-failure signal. There is no `assistantOverrides.variableValues`, no rendered system message, no structured tool-call arguments.

If a failure looks variable-injection-shaped in either variant and runtime state can't be confirmed, mark the diagnosis "suspected upstream — runtime state not observable" rather than blindly proposing a prompt edit.

## Phase 3 — Edit-surface scope

### Variant: `file`

Editable:

- **System prompt** — the located string constant / file. Edits land via `Edit` in Phase 4.1d.
- **Tool definitions** — if they live in the same file (or a file the skill can reach). Edits land via `Edit` in Phase 4.1d. Tool definition edits in websocket mode are *live* edits — they take effect after the server restart, unlike pipecat mock-tool edits which only change the testing contract.
- **Orchestration code** — when the failure's root cause is in conversation plumbing rather than prompt wording. Concrete sub-surfaces:
  - History-management code: window size, slice indices, truncation policy, role-filter conditions. Common bug: an `if len(history) > 12: tail = history[-10:]` slice that drops earlier collected info before booking — raise the window or summarize-and-prepend.
  - Tool-call dispatch and result-forwarding: ensuring `tool_call_id` is propagated, the tool result is appended back to `history` as a `"role": "tool"` message with the right id, and the LLM gets a chance to read it before the next user turn.
  - Message-forwarding to Cekura: the `{"role": "Function Call", ...}` and `{"role": "Function Call Result", ...}` sends so Cekura captures the full picture (mostly observability, but affects what evaluators can see).
  - Keepalive / connection-management: ping interval, pre-emptive cancels, error handlers that swallow disconnects.
  These edits land via `Edit` in Phase 4.1d, same as prompt edits, and take effect after the server restart. **Always show the user the unified diff before applying** (auto mode still renders, then proceeds — code edits especially benefit from transparency).

Not editable (surface as upstream hand-offs):

- **Tool implementation bodies** — the function that computes the answer or calls an external service. The skill edits schemas and orchestration, not business logic. If a schema change requires the implementation to change too, surface that explicitly.
- **Security-sensitive code** — API keys, auth flow, OAuth signing, secret management, header generation, request signing. Never edit, even when the failure is plausibly auth-related.
- **LLM client configuration** — model name, temperature, max_tokens, base_url. Touch only if the user explicitly asks. If a CodeBug diagnosis suggests "model is too small for this prompt complexity" surface as a hand-off, don't silently change it.
- **Dependencies / requirements** — never add or remove imports beyond what's already in the file. Don't propose `pip install X` mid-loop.
- **Framework upgrades / multi-file refactors** — if the fix requires changes across files, helper-function extraction, or new abstractions, hand off rather than attempting.

### Variant: `offline`

Only prompt edits. Tool-shaped findings become upstream hand-offs ("the prompt depends on a `bookAppointment` tool but the transcript shows the agent improvising — if you don't already have that tool wired up, add it; this skill can't reach your tool config in offline mode"). Code-shaped findings also become hand-offs — no live file to edit. Same rule as the legacy single-prompt mode.

## Phase 4.1d — Apply

### Variant: `file`

Apply in this order:

1. **Orchestration-code edits first** — one `Edit` call per logical change to the message loop / history management / tool dispatch / keepalive. Use 5–10 lines of surrounding context for every `old_string` to avoid ambiguous-match failures. Render the unified diff for each before applying (auto mode renders and proceeds; non-auto pauses for explicit approval). If multiple orchestration changes are needed and they're independent, apply them as separate `Edit` calls — easier to roll back individually if validation regresses. Skip this step entirely if there are no CodeBug diagnoses this iteration.
2. **Tool-definition edits next** — one `Edit` call per changed tool block in the source file. Use enough surrounding context to make each `old_string` unique.
3. **New tool additions** next — same file, `Edit` inserting the new tool block into the `TOOLS` list (or equivalent). If the addition requires a corresponding implementation function and that function is missing, surface a hand-off rather than silently inserting only the schema.
4. **System prompt edit** — single `Edit` call on the prompt string. For very long prompts (>5K chars) and a small diff, consider multiple smaller `Edit` calls each targeting a distinct section instead of one massive replacement.
5. **Optional: sync to Cekura description** — if the user wants Cekura's dashboard to mirror the live prompt, also call `mcp__cekura__aiagents_partial_update` with the new prompt text. Skip by default; the live source of truth is the file, not Cekura.
6. **Restart step** (see "Restart" below). Runs after the file edits land and before Step 4.2 sync verification.

Show the user the unified diff(s) of the file edits — prompt, tools, AND orchestration code — and a list of all changes for transparency. Code edits especially: surface what changed and why (cite the failure shape that motivated each edit).

#### Restart

Three paths depending on `redeploy_command` (collected in main SKILL.md Step 1.4) and `auto_mode`:

**Path 1: `redeploy_command` is a real shell command — preferred.** Execute it via the Bash tool with a reasonable timeout (default 120s; bump if the user's command does cloud deploys). Capture exit code and stderr.

- **Exit 0** → proceed to Step 4.2 sync. If the first iteration returned connection errors during validation, suggest appending `&& sleep 3` (or similar) so the new process is fully bound before validation hits it.
- **Non-zero exit** → surface stderr + exit code; do NOT proceed to validation. Ask: retry / edit the command (update `redeploy_command` on the run for future iterations) / abort.
- **Timeout** → surface explicitly; ask whether the command is expected to run longer (bump timeout) or whether something is hung (the user may need to make a `pkill` pattern more specific, or remove an interactive prompt from the command).

Watch for known foot-guns:
- `pkill python` matches every python process on the host. Suggest narrowing to `pkill -f "python main.py"` only if the first iteration's restart kills more than expected (e.g., the user's IDE-spawned interpreter disappears).
- Backgrounded servers (`nohup python main.py &`, `disown`) are fine — Bash returns once the foreground portion is done.
- SSH-to-remote restarts require non-interactive sessions (keys, no MFA). Hanging command = surface clearly.

**Path 2: `redeploy_command == "manual"` (or unset and `auto_mode: false`).** Render the canonical restart gate:

```
Source file updated:
  <path>: <N> lines changed (prompt: <M> chars Δ, tools: <K> changed)

Validation runs against your live websocket at <wss://...>, which is still
running the *previous* code until you restart the server.

Before continuing:
  1. Confirm the file changes look right (diff is above).
  2. Restart your websocket server so the new code is live.
  3. Confirm the restart is live ("done", "restarted", "yes").

Reply "skip" to validate against the current live server anyway (the result
will reflect the *old* code) or "abort" to halt the loop.
```

Treat any of `"done"`, `"restarted"`, `"yes"`, `"y"`, `"reloaded"` (case-insensitive) as confirmation. `"skip"` continues but flags the iteration as `restart_skipped: true`. Anything else, ask once for clarification before treating as abort.

**Path 3: `redeploy_command` unset and `auto_mode: true`.** Proceed straight to Step 4.2 sync and Step 4.4 validation without pausing. The live websocket may still be running the pre-edit code — the skill trusts the user has either restarted already or is OK with the next validation reflecting whatever state the live server is in. The Step 4.5 no-change detector surfaces stale-state hypotheses after the fact. This is the legacy auto-mode behavior; if results come back unchanged across iterations, encourage the user to provide `redeploy_command` so the loop converges faster.

### Variant: `offline`

There is no PATCH and no file edit. Render the rewritten prompt and the next step depends on `auto_mode`.

**Auto mode (default `auto_mode: true`):** ask once, concisely, for the next batch of pasted failures. No multi-step "before continuing" block. Example:

```
Iteration <N> proposed prompt:

──────── BEGIN REWRITTEN PROMPT ────────
<full rewritten prompt, or unified diff if long / user-preferred>
──────── END REWRITTEN PROMPT ────────

Apply this prompt to your system, re-run your tests, and paste the new
failures (transcript + expected_outcome + verdict per failure). Reply
"pass" if everything passes, or "abort" to stop.
```

**Non-auto mode (`auto_mode: false`):** render the canonical manual-apply gate and wait:

```
Iteration <N> proposed prompt is below. The skill cannot apply this for you
in the offline variant.

──────── BEGIN REWRITTEN PROMPT ────────
<full rewritten prompt, or unified diff if long / user-preferred>
──────── END REWRITTEN PROMPT ────────

Before continuing:
  1. Copy the prompt above into your agent's system prompt.
  2. If your agent runs on a deployed system, deploy the change.
  3. Re-run your tests against the new prompt.
  4. Reply with one of:
       • "done" / "applied" / "ready" — proceed with new failures
       • "diff please" — re-render the change as a unified diff
       • "skip" — keep iterating against the *previous* prompt (no apply)
       • "abort" — halt the loop
```

Treat "skip" as valid — the user may want to compare two diagnoses before picking — but record it on the iteration and use the prior prompt as the diagnosis baseline next time.

## Phase 4.2 — Sync verification

### Variant: `file`

Re-read the source file (the `Read` tool, not a cached copy) and verify the changed regions match the intended `Edit` output. The `Edit` tool returns the post-edit content snippet — diff it against expectation. If a tool-definition edit was supposed to extend `TOOLS` but the post-edit file shows the old length, the edit either landed in the wrong location or matched a partial-but-ambiguous `old_string`. Roll back (re-`Edit` with corrected anchor) before continuing.

There is no "live agent" sync to verify from this side — that's what the restart gate (non-auto) or the no-change detector (auto) is for.

### Variant: `offline`

Skip — there's nothing to sync. The user's reply to the Step 4.1d manual-apply gate ("done" / "applied" / "ready") is itself the only sync confirmation available. If the next iteration's failures look identical to the prior iteration's, surface the no-change hypothesis in Step 4.6.

## Phase 4.5 / 4.6 — Re-collect & exit framing

When the iteration ran with `restart_skipped: true` (variant `file`), the new failure summary is **not** evidence the edit didn't work — it reflects the live server's *prior* code. Surface this clearly the same way pipecat mode does:

```
Iteration N validation completed without a server restart.
The failures below describe your *current live* websocket agent, which is
still running the code from before this iteration's edits.

Before treating these failures as Phase 3 input, restart your websocket
server with the iteration N file changes and re-run validation.
```

Do not feed `restart_skipped` failure sets into the next Phase 3 — they will produce phantom edits stacked on top of changes that haven't taken effect yet.

When two consecutive iterations show identical failures (same scenarios, same transcript shapes), surface the no-restart hypothesis even if the user nominally confirmed restart:

```
The failures from iteration N look identical to iteration N-1. The most
likely cause is that the live websocket server didn't pick up the new code —
possibly the restart didn't actually happen, the file edit landed in the
wrong location, or another process is serving from a stale copy. Please
verify your live server is running the iteration N file before continuing.
```

The 100% pass exit is the same as the other modes.

## Edge cases

- **`description` on the Cekura record is empty or stub.** Expected for websocket agents — the prompt lives in code. Don't treat this as misconfiguration; proceed with the file as the source of truth. Surface a one-line note in Phase 1.3 so the user knows.
- **`description` on the Cekura record is populated and clearly out of sync with the file.** Ask once whether the Cekura description is meant to mirror the live prompt. If yes, offer to sync (PATCH the description) as part of Phase 4.1d's optional step. If no, leave it alone — the file is canonical regardless.
- **`websocket_url` is missing or empty.** The agent isn't fully configured for validation runs even though file edits would land fine. Stop and point the user at `cekura-create-agent` (Phase 3: Configure Provider Integration) to populate the URL, or fall back to the `offline` variant if the user just wants the rewritten prompt.
- **File contains the prompt across multiple non-contiguous strings (concatenation, f-string interpolation, helper functions).** Stop and ask the user to identify the *effective* prompt that gets passed to the LLM at runtime, or to consolidate the prompt into one string before iterating. Don't guess at the concatenation order.
- **Prompt or tool blob has placeholder dynamic variables (`{{...}}`) that the user's code substitutes at request time.** Same handling as the other modes — do not edit placeholders unless the user explicitly asks. They're owned by the calling system, not the prompt.
- **Source file is in a git working tree with uncommitted changes.** Don't roll those back as part of a failed `Edit` rollback. If a roll back is needed, only undo the lines this skill touched. Surface to the user if the situation is ambiguous.
- **Source file is read-only or outside the workspace.** `Edit` will fail. Stop and offer the `offline` variant — there's no path to direct editing.
- **Multiple websocket agents share one source file (parameterized by env var / config).** The file edits will affect all agents that read from that file. Surface this before applying — the user may want to copy the file first or branch on the variable.
- **Server is in a hot-reload container (Pipecat Cloud, fly.io, etc.) where "restart" is a deploy.** Same treatment as pipecat redeploy — the user does the deploy; the skill waits or trusts auto mode.

## Anti-patterns specific to websocket-flavor

- **Treating the Cekura `description` as the source of truth.** It is at best a mirror. The live prompt is in the user's source code. Editing the `description` does nothing to the live agent unless the user's code reads from it (rare for websocket agents — most have the prompt as a constant in code).
- **Iterating prompt-wording when the diagnosis is CodeBug.** If oscillation or a no-change signature surfaces and the failure shape matches a CodeBug signal (agent forgets earlier turns despite an explicit clause, tool result never reaches the LLM, conversation drops mid-flow), the prompt is fine — the plumbing is broken. Move to orchestration-code edits. Repeated prompt-only edits will not converge.
- **Crossing the orchestration / business-logic line.** Orchestration code (message loop, history management, tool dispatch, message forwarding, keepalive) IS editable. Tool implementation bodies (what a tool *computes*), security-sensitive code (API keys, auth, signing, secrets), LLM client config (model name, temperature), and dependencies are NOT. When in doubt about which side a piece of code falls on, hand off — false hand-offs are recoverable; an unwanted code change is not.
- **Proposing speculative refactors.** An orchestration-code fix should be the smallest `Edit` that addresses the failure — change the slice size, add the missing append, fix the role mapping. Do not rewrite whole functions, introduce new helpers, or restructure data flow just because the surrounding code "could be cleaner". If the fix genuinely needs more than one `Edit` or new function definitions, hand off instead.
- **Applying `Edit` with a non-unique `old_string`.** The Edit tool's failure mode is "ambiguous match". Use enough surrounding context (5–10 lines on either side of the actual change) to make every anchor unique. For multi-tool list edits, target each tool block separately rather than the whole list. Same rule applies to orchestration-code edits — code blocks often have repeated patterns (`for ... in ...:`, `if not ...:`), so anchor on the surrounding distinctive context.
- **Rendering the restart gate in auto mode.** Auto mode is opt-out for a reason — the gate breaks the autonomous loop. The no-change detector at Step 4.5 handles the stale-state case after the fact. (In `auto_mode: false` the gate fires every iteration — that's the trade-off the user opted into.)
- **Editing a tool's schema without confirming the live implementation matches.** Unlike pipecat where mock tools and live implementations are deliberately separate, websocket tools are usually one and the same — but the skill is only editing the schema. If the implementation in `call_tool()` (or wherever) returns a different shape than the schema declares, the agent will get confusing errors at runtime. Surface this as a hand-off when in doubt.
- **Iterating in `offline` variant when the user has a live websocket they could expose.** The full closed loop runs much faster — encourage `file` whenever feasible. The offline variant also can't access the orchestration-code surface, so CodeBug-shaped failures stay stuck as hand-offs there.
