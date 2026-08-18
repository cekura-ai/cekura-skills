# Recipe · runtime-created agent (source in the customer's stack)

For teams that keep agent config in their own stack (repo, database, or a
prompt registry such as Langfuse) and materialize the runtime provider agent
(VAPI, Retell, ElevenLabs, or any other) at deploy time. **Never edit the
provider object** — it is a build artifact; the next deploy overwrites it.

Discovery hints: provider SDK calls in deploy scripts
(`client.assistants.create/update`, `create_agent`), prompt files rendered
through templates, Langfuse `get_prompt`/`create_prompt` calls, a DB table of
tool definitions, CI jobs named deploy-agents.

```yaml
version: 1
agent:
  cekura_agent_id: <id>
  source_ref: <agent name/slug in the customer's config>
  runtime_refs:
    staging: <provider id the staging deploy produces>
environments:
  staging: { kind: deployed, production: false }
  prod:    { kind: deployed, production: true, promote_requires: manual }
authority:
  allowed_paths: [<prompt/config dirs>]
  forbidden_paths: [<billing, infra/prod, unrelated services>]
  secrets_policy: redact
source_of_truth:
  components:
    - name: prompt
      kind: repo
      paths: [<prompt file(s)>]
      rollback: { how: git }
    - name: tools            # only if tools live outside the repo
      kind: database | prompt_registry   # add vendor: langfuse etc. if useful
      read:  { run: "<dump command>", writes: false }
      apply: { mode: command, command: { run: "<update command>", writes: true } }
      rollback: { how: command | versioned }
render_intended: { run: "<render command>", writes: false }   # strongly recommended
read_live:       { run: "<live dump command>", network: environment, writes: false }  # REQUIRED
validate:        { run: "<dry-run/schema check>", writes: false }
deploy:
  target_env: staging
  command: { run: "<deploy command>", network: environment, writes: true, timeout_seconds: 600 }
  produces: [runtime_agent_id, build_sha]
attestation:
  acceptable_differences: ["$.id", "$.updatedAt"]   # provider-assigned fields
  trace_correlation:
    fields: [assistant_id, build_sha]
    identity_source: deploy_produces
evidence:
  traces: { run: "<langfuse/trace fetch by call id>", writes: false }
simulate:
  runner: <scenarios_run_* for the provider/transport>
  flake_policy: { max_infra_failures: 1, retry_on: [timeout, transport_error] }
promote:
  how: pr        # the customer's own review + deploy pipeline promotes
```

Non-negotiables for this recipe:

- `read_live` must exist. Without it the loop cannot attest that the eval hit
  the deployed fix (stale-deploy verifications are the #1 failure mode here).
- Trace correlation: capture the provider id / build sha the deploy produces
  and confirm each Cekura batch's traces reference it.
- Promotion is a PR whenever the repo is a source — the diff, audit summary,
  and eval numbers go in the PR body; the customer's pipeline does the rest.
