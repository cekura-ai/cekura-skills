# Recipe · provider-managed agent (dashboard is the source of truth)

> **Skeleton, not a runnable manifest.** Setup must fill the `read` /
> `read_live` / clone commands from the classic skill's `providers/<mode>/`
> files before the SETUP.3 self-test can pass. The self-test maps as:
> component `read` = provider GET on the live agent; "deploy" = create the
> per-session clone; `read_live` = provider GET on the clone; trace
> correlation = the clone's assistant/agent id in the run metadata.

The classic `cekura-self-improving-agent` case expressed as a manifest: the
agent is created and edited in the provider dashboard/API; there is no repo
render step, so `read_live` and the component `read` are the same surface and
the "deploy" is a noop (provider writes are live immediately). The sandbox
equivalent is a provider-side clone.

```yaml
version: 1
agent:
  cekura_agent_id: <id>
  source_ref: <provider assistant/agent id>
environments:
  provider-clone: { kind: deployed, production: false }
  prod:           { kind: deployed, production: true, promote_requires: manual }
authority:
  secrets_policy: redact
source_of_truth:
  components:
    - name: agent_config
      kind: runtime_provider
      read: { argv: ["<provider GET command, e.g. curl .../assistant/{agent_ref}>"], network: external, writes: false }
      # read/apply via provider API exactly as the classic skill's
      # providers/<mode> files describe (VAPI /assistant, ElevenLabs
      # conversation_config.agent.prompt.prompt, Retell response_engine, …)
      apply: { mode: provider_api }
      rollback: { how: versioned, notes: "pre-edit GET stashed per iteration" }
deploy:
  target_env: provider-clone   # clone-per-session = the sandbox deploy
simulate:
  runner: <scenarios_run_* matching the provider/transport>
promote:
  how: provider_publish
```

Everything provider-specific — clone graphs (ElevenLabs transfer graph, VAPI
squads), editable paths, silent-failure sync checks, field denylist
(credentials, webhooks, phone numbers, transfer destinations) — follows the
classic skill's `providers/<mode>/` files unchanged. If the project matches
this recipe with no custom stack at all, prefer invoking
`cekura-self-improving-agent` directly.
