# Recipe · customer-operated mock server

For teams whose agent's tools call their own mock/stub server during testing
instead of (or alongside) Cekura's built-in mock tools. The mock server is a
**simulation fixture**: it must be reset/seeded deterministically before every
batch, and its failures are infra flake, never agent behavior.

Add to any base recipe:

```yaml
simulate:
  runner: <scenarios_run_*>
  reset_fixtures:
    - { run: "curl -sf -X POST <mock-base>/reset", network: local, writes: true }
    - { run: "curl -sf -X POST <mock-base>/seed -d @fixtures/{session_id}.json", network: local, writes: true }
  flake_policy:
    max_infra_failures: 1
    retry_on: [timeout, transport_error, mock_unavailable]
```

Rules:

1. **Reset before must-fail, before every verify batch, and before the
   regression sweep.** A batch after a failed reset is invalid — rerun it;
   never count it toward any gate.
2. **Seed from the failure's own trace** during Reproduce: the mock must
   return what production actually returned (argument-keyed, per-invocation),
   or the reproduction is testing a different world.
3. **Classify mock-server errors as infra.** 5xx/connection-refused from the
   mock, or tool calls that never reached it, are `mock_unavailable` — retry
   per flake policy and report the discard count.
4. **State bleed check.** If scenario outcomes change with run order, the mock
   holds cross-call state the reset doesn't clear — surface this as a fixture
   bug to the user; do not tune the prompt around it.
5. Mock endpoints/credentials follow the same secrets policy: env-var names in
   the manifest, values never persisted.
