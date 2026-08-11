# Phase 1 · Setup — manifest discovery, validation, self-test

Goal: leave this phase with a validated `.cekura/selfimprove.yaml`, a passing
self-test, and the session recorded. No failure collection, no edits here.

## SETUP.1 — locate or build the manifest

1. If `manifest_path` (default `.cekura/selfimprove.yaml`) exists: load it,
   validate against `references/manifest.schema.json`, and go to SETUP.3.
2. Otherwise **discover**: explore the repo for agent config (prompt files,
   deploy scripts, provider SDK calls, Langfuse clients, DB schemas for
   tools), and check whether one of the `recipes/` matches (provider-managed,
   runtime-created, custom-mocks). Draft a manifest from the best match.
3. **Interview** for what discovery can't infer — one grouped question set,
   not a drip: which environment is safe to iterate in, the deploy command,
   how the live config can be read back, per-component rollback, env-var
   names for credentials. A missing `read_live` when a deploy step exists is
   a blocker, not a nice-to-have.
4. Write the manifest, show it to the user, get confirmation. This is a
   privileged artifact: any later edit to it re-enters SETUP.3.

## SETUP.2 — register commands

Register every manifest command verbatim; run the dangerous-command lint from
`references/manifest-guide.md`. Reject placeholders other than
`{agent_ref} {session_id} {env} {build_sha}`. Record for the session: command,
declared network/write scope, timeout, env-var names.

## SETUP.3 — manifest self-test (mandatory, cheap, catches drift early)

Run in order; any step failing stops the session as `manifest_invalid` with a
repair offer (never continue on guessed mechanics):

1. **Read**: each component's `read` (or file presence for repo paths) returns
   plausible, non-empty config. Hash it — this is the source baseline.
2. **Render**: `render_intended` (if declared) produces output; hash it.
3. **Deploy or noop**: run `deploy.sandbox_command` if present, else
   `deploy.command` against the non-production `target_env`, else noop for
   live-on-save. Capture `produces` identities (runtime_agent_id, build_sha).
4. **Read live**: `read_live` returns config; compare to the render. Declared
   acceptable differences aside, a mismatch here is drift — surface it now.
5. **Smoke scenario**: run one Cekura scenario through `simulate.runner`
   against the deployed target; confirm it connects and produces a transcript.
6. **Trace correlation**: confirm the smoke run's trace/metadata points at the
   identity captured in step 3 (the eval hit the thing we deployed, not an
   older build or a different agent).

## SETUP.4 — session bookkeeping

- Take the concurrency lock (`.cekura/selfimprove.lock`); a live foreign lock
  → stop and ask.
- Repo components: create the session worktree/branch
  (`cekura/selfimprove-{session_id}`); one commit per iteration.
- Persist run setup to `.claude/MEMORY.md`: manifest path + hash, environment,
  runner, identities, thresholds. **No secret values, env-var names only.**
- Record the audit-trail header: manifest hash, source baseline hash, rendered
  hash, live hash, smoke scenario id.

Then announce `Iteration 1 · Collect` and continue with the collect phase from
`cekura-self-improving-agent` (same verdict filters and funnel rules), adding
any manifest `evidence` sources (Langfuse traces, custom logs) to COLLECT.4's
inspection inputs.
