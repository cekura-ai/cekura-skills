# Self-Hosted Mode — Overview

`self_hosted` is the umbrella mode for any agent whose live runtime is **not** a managed provider that this skill can PATCH directly. The user owns the live agent code; this skill operates on whichever artifact best approximates the system prompt for that runtime.

Self-hosted resolves to a single sub-flavor: **`websocket`** — custom servers the user runs themselves. See `websocket.md` for the full sub-flavor doc.

| Sub-flavor | When to use | Editable surface | Live-agent sync |
|------------|-------------|------------------|-----------------|
| **websocket** | The user's agent is a custom websocket server they run themselves (e.g., `wss://...ngrok.io/...` pointing at a Python/Node/Go process). The system prompt lives in the user's source code as a string constant; tool definitions usually live in the same file. Also the fallback for any agent whose prompt the user wants to iterate on offline without a live target. | The user's source file directly, via the `Edit` tool. Tool definitions in the same file are editable the same way. If no live websocket is reachable, the mode degrades to pasted-prompt / pasted-failures (the old "single prompt" behavior). | User restarts their websocket server before re-validation (auto-mode skips the gate; surfaced as a no-change hypothesis after the fact). When no live websocket is reachable, validation is the user re-running their tests externally and pasting new failures back. |

## Routing into the sub-flavor (Phase 1.2)

When `assistant_provider` resolves to `self_hosted` (either directly or via a confirmation for `custom` / `agentforce` / similar tags), route to the **websocket** sub-flavor. See `websocket.md` for the source-file vs. `offline` distinction.

If the user cannot point at the file (or there is no live websocket to reach), proceed with the **websocket** sub-flavor in its degraded `offline` variant — pasted prompt text, pasted failures, no `Edit`, no auto re-validation. See `websocket.md` § "Degenerate variant: no live websocket".

## Shared characteristics

Across the self-hosted sub-flavor:

- **Cekura is never the source of truth for the live behavior.** It is at most an entry-point reference (the `websocket_url` field plus an informational `description`).
- **There is no provider PATCH that pushes the prompt into the running agent.** File-system edits only take effect after the user restarts the live process.
- **Validation runs through Cekura** when a live agent is reachable (the user's running server). Cekura drives the scenario, captures the transcript, and runs metrics. The skill consumes those results the same way as VAPI mode.
- **Redeploy is automated when `redeploy_command` is configured** — the skill runs it after each apply step (Phase 4.1) so the live agent is ready before validation. When the command isn't configured, the loop falls back to either the auto-mode "trust and surface no-change after the fact" behavior or the non-auto manual restart gate. See "Redeploy command flow" below.

## Redeploy command flow

The single biggest source of friction in the legacy self-hosted loops is the per-iteration "restart your server" pause. With `redeploy_command` configured, the loop runs end-to-end autonomously: apply → redeploy → validate → diagnose → apply → ... Without it, the user has to manually unblock every iteration.

### Collection (Phase 1.4)

The main SKILL.md's Step 1.4 collects this once at the start of the run. The collection prompt template:

```
For end-to-end automation, I can run your redeployment automatically after each
prompt edit so the live agent is ready before re-validation. What shell command
(or commands) restarts your live agent?

Examples:
  Local Python websocket server:    pkill -f main.py; nohup python main.py &
  Docker compose:                   docker compose restart agent
  systemd:                          sudo systemctl restart my-agent
  SSH'd remote host:                ssh user@host 'systemctl restart agent'
  Fly.io:                           fly deploy --strategy immediate

Reply with the shell command, OR reply "manual" if you'd rather restart the
agent yourself between iterations (I'll pause and ask "done" before each
re-validation).
```

Skip the collection prompt when:

- `redeploy_command` was passed in the run inputs.
- The resolved mode is `vapi` (VAPI edits land live; nothing to redeploy).
- The resolved sub-flavor is `websocket` with `websocket_variant: offline` (no live agent at all).

### Sentinel handling

- `"manual"` (case-insensitive, possibly with whitespace) → record as `redeploy_command: "manual"` and fall through to the per-sub-flavor manual restart gate at every Phase 4.1.
- Empty string or "skip" → same as `"manual"` — surface to the user that you've recorded the manual fallback rather than treating empty as "no redeploy needed".
- Anything else → treat as a shell command. Do not validate the command's correctness in Phase 1; the user owns that.

### Execution (Phase 4.1)

After the apply step lands (file edits / VAPI PATCH equivalent for self-hosted), and before Step 4.2 sync verification:

1. Run the recorded `redeploy_command` via the Bash tool. Use a generous timeout (default 120s; bump to 600s if the user's command contains hints like `deploy`, `cloud`, `image`, `push`).
2. Capture the exit code, stdout, and stderr.
3. On exit code 0 → proceed to Step 4.2.
4. On non-zero exit → surface the failure to the user with stderr + exit code, do NOT proceed to validation. Ask whether to retry, edit the command (in which case update `redeploy_command` on the run for future iterations), or abort the loop.
5. On timeout → same as non-zero exit, but make the "is this command interactive / long-running?" question explicit. If the user confirms it's expected to take longer, bump the timeout for future iterations.

For backgrounded servers (e.g., `pkill -f main.py; nohup python main.py &`), the Bash tool returns once the foreground portion completes — this is the intended behavior. Consider adding a short `sleep` after the restart command (e.g., `... && sleep 3`) so the new process is fully bound to its port before validation hits it. The skill should suggest this proactively only if the first iteration's validation comes back with connection errors.

### Websocket-specific notes

For local Python / Node websocket servers, `pkill` patterns can match too broadly — verify the user's command is scoped to the right process (e.g., `pkill -f "python main.py"` is safer than `pkill python`). Don't suggest changes to the command unless the user asks; the skill is a runner, not a linter, on this surface.

For SSH-to-remote restarts, the user's SSH config must support non-interactive sessions (keys, no MFA prompts). If the redeploy command hangs waiting for input, the Bash tool will time out — surface this clearly and ask the user to make the command non-interactive.

### What this skill will NOT do

- **Modify the user's deploy infrastructure.** If the systemd unit is misconfigured, that's the user's problem to fix — surface and pause.
- **Verify the new prompt is actually live.** There's no general-purpose way to check this across runtimes. The Step 4.5 no-change detector is the only signal the skill has; if results look unchanged, surface the "redeploy may not have taken effect" hypothesis.
- **Run anything destructive without confirmation.** If `redeploy_command` contains `rm -rf`, `DROP`, `--force-push`, or similar, pause and ask before the first execution. Subsequent iterations can reuse the confirmed command.

## What is NOT in scope for self-hosted mode

- Squad members, `model.toolIds`, spoken `request-start` / `request-complete` / `request-failed` messages, and handoff `destinations` — those are VAPI-only concepts. Do not propose edits to those surfaces.
- For websocket-mode, tool definitions in the user's source file ARE the live implementation's contract — editing them lands in the running process after a restart, no separate "mock vs. live" reconciliation needed.
