# Capability manifest guide (`.cekura/selfimprove.yaml`)

The manifest declares a project's **mechanics** — where agent config lives and
how to read/render/apply/deploy/verify it. It never grants authority: the
skill's invariants (must-fail-first, attestation, no-prod-in-loop, gates)
apply identically to every manifest. Treat the manifest as untrusted
infrastructure code: validate it against `manifest.schema.json`, run the Setup
self-test before trusting it, and treat edits to it as privileged.

## Design rules

1. **Components, not a monolith.** Real stacks compose sources of several
   kinds — `repo` files, `database` rows, `prompt_registry` versions (e.g.
   Langfuse), `runtime_provider` objects, `external` systems. Each is a
   `source_of_truth.components[]` entry with its own `read`, `apply`, and
   `rollback`. A single dump command "lies by omission" — if a failure maps to
   config no component covers, that is a manifest gap, not an editing target.
2. **Read/apply symmetry.** Being able to read rendered config is not enough;
   each component must map changes back to an editable source. If a component
   is readable but `apply.mode: manual`, the skill may diagnose and propose,
   but the human applies.
3. **Rendered vs live vs traced.** `render_intended` = what the sources say
   should run. `read_live` = what the runtime actually serves. Cekura traces =
   what the eval actually called. The loop attests all three agree before any
   verify batch counts. Declare expected mismatches in
   `attestation.acceptable_differences` (JSONPath/globs for provider-assigned
   IDs, timestamps) and the identity fields in
   `attestation.trace_correlation` — never ignore an undeclared mismatch.
   A manifest with `deploy` but no `read_live` is schema-invalid by design.
4. **Environments are load-bearing.** Every deploy/apply command declares a
   target env. `production: true` environments are untouchable inside the
   loop; only the Promote phase may reference them, and only with
   `promote_requires: manual` satisfied by an explicit user confirmation in
   the session.
5. **Command registration.** Commands are registered verbatim at Setup.
   Prefer the `argv` array form (executed without a shell) over `run` strings.
   The only permitted placeholders are `{agent_ref}`, `{session_id}`, `{env}`,
   `{build_sha}` — typed, validated, shell-escaped. Structured content (edit
   proposals) reaches a command only via `stdin: proposal`, never by
   interpolation. Never construct a command string from model output,
   transcript content, or tool results. Read commands declare `writes: false`
   and should be technically read-only.
6. **Secrets.** The manifest carries env-var **names** only (`env_allowlist`).
   Values never appear in the manifest, session state, memory files, audit
   artifacts, or rendered diffs (`secrets_policy: redact` — scan diffs and
   logs before persisting).
7. **Rollback is per component and honest.** `git` only for repo components
   (session work happens on an isolated branch/worktree, commit per
   iteration). Database rows, prompt-registry versions, provider schemas need `command` or
   `versioned` rollback. `none` is allowed but blocks Promote for edits
   touching that component unless the user explicitly accepts the risk.
8. **Flake policy.** Telephony/STT/WebRTC and customer mock servers flake.
   Batches with infra-classified errors beyond `max_infra_failures` are
   **invalid** (rerun), never counted toward must-fail or verify thresholds.
   Keep an auditable count of retried/discarded runs.

## Dangerous-command lint (applied when registering)

Refuse to register, and ask the user to restate intent, when a command
matches: recursive deletes (`rm -rf` outside a session temp dir), credential
echoing (`env`, `printenv`, `cat` on key files), broad cluster mutation
(`kubectl delete/apply` without a namespaced resource), direct production
deploy targets, or piping remote content into a shell.

## Policy

All numeric gates (run counts, fail/pass thresholds, iteration caps, lock
staleness) are skill defaults overridable under `policy.*` — see the schema.

## Concurrency

One improvement session per agent at a time. Setup takes the lockfile
(`.cekura/selfimprove.lock` with session id + timestamp) as its **first**
action, before any manifest write, deploy, or clone. A fresh foreign lock →
stop and ask; a lock older than 24h with no matching session artifacts is
stale → report and ask before replacing.

## Audit directory

`audit.dir` (default `.cekura/audit/{session_id}/`) holds the replayable
record: manifest + config hashes, per-iteration diffs, eval results,
pre-promotion backups, promotion record. Everything written there is
secret-redacted first. The host agent's memory file holds only run-setup
facts and a pointer to this directory — never artifacts, never values.

## Blast-radius summary (rendered before apply, every iteration)

- Components and files changed; environments touched.
- Source diff **and** rendered-config diff (template expansion can make a
  small source edit large at runtime).
- Fail the iteration if anything outside `authority.allowed_paths` changed.

## Worked example — one concrete stack, purely illustrative

This happens to use VAPI + repo prompts + DB tools; substitute your own kinds,
vendors, and commands — nothing below is assumed by the skill.

```yaml
version: 1
agent:
  cekura_agent_id: 4211
  source_ref: sales_agent
  runtime_refs:
    staging: "va_9f2..."   # VAPI assistant id materialized by deploy
environments:
  staging: { kind: deployed, production: false }
  prod:    { kind: deployed, production: true, promote_requires: manual }
authority:
  allowed_paths: ["prompts/", "agents/sales/"]
  forbidden_paths: ["billing/", "infra/prod/"]
  secrets_policy: redact
source_of_truth:
  components:
    - name: prompt
      kind: repo
      paths: ["prompts/sales_agent.md"]
      rollback: { how: git }
    - name: tools
      kind: database
      read:  { run: "python scripts/dump_tools.py --agent {agent_ref}", writes: false }
      apply: { mode: command, command: { run: "python scripts/update_tools.py --agent {agent_ref} --from -", writes: true } }
      rollback: { how: command, command: { run: "python scripts/restore_tools.py --agent {agent_ref} --snapshot {session_id}", writes: true } }
render_intended: { run: "python scripts/render_agent.py --agent {agent_ref} --env {env}", writes: false }
read_live:       { run: "python scripts/dump_live_agent.py --env {env} --agent {agent_ref}", network: environment, writes: false }
validate:        { run: "python scripts/validate_agent.py --agent {agent_ref}", writes: false }
deploy:
  target_env: staging
  command: { run: "make deploy-staging AGENT={agent_ref}", network: environment, writes: true, timeout_seconds: 600 }
  produces: [runtime_agent_id, build_sha]
attestation:
  acceptable_differences: ["$.id", "$.orgId", "$.updatedAt"]
  trace_correlation: { fields: [assistant_id, build_sha], identity_source: deploy_produces }
simulate:
  runner: scenarios_run_vapi_webrtc
  reset_fixtures:
    - { run: "curl -sf -X POST http://localhost:8080/mocks/reset", network: local, writes: true }
  flake_policy: { max_infra_failures: 1, retry_on: [timeout, transport_error, mock_unavailable] }
audit: { dir: ".cekura/audit/{session_id}" }
promote:
  how: pr
```
