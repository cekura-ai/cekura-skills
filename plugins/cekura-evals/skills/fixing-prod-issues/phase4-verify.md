# Phase 4 — Verify the Fix

> ## ⚠️ E2E SIMULATION IS THE ONLY VALID VERIFICATION
>
> **Verification MUST be done through a full end-to-end Cekura simulation using the same connection medium as the production call** — the exact same evaluator from Phase 2, run over the same transport the agent is configured for.
>
> ❌ Do NOT use text mode. ❌ Do NOT switch to a different transport than what was used in the prod call.
>
> The fix is not verified until Cekura's metric scores show it passing over the same medium as production. A fix that passes code review or unit tests but fails the E2E simulation is not a valid fix.

Re-run the same evaluator from Phase 2 against the fixed code. The same conditions that reproduced the bug must now be handled correctly by the fix.

---

## 4a. Trigger a new run

Use the same `scenario_id` from Phase 2 — do not create a new evaluator:

```bash
source ${CLAUDE_PLUGIN_ROOT}/scripts/cekura-api.sh
run_voice "SCENARIO_ID" '{"agent_number": "<local_agent_caller_id>"}'
```

From the response, extract the connection details and pass them to the local agent using the setup instructions from `memory.md` / `CLAUDE.md` (same as Phase 2). Run the local agent with the fix applied and edge conditions still active.

Poll for results:

```bash
get_result "RESULT_ID"
```

---

## Phase 4 Gate

**The eval MUST pass on Cekura.** Check `runs[].evaluation.metrics[]` — the same metrics that were failing in Phase 2 must now be passing.

If the eval still fails:
- Read the transcript and compare with Phase 2's failing transcript — what changed and what didn't?
- Iterate on the fix and re-run
- Do not proceed to Phase 5 until this passes

Only when the **Cekura metric scores show the fix working** move to [Phase 5](phase5-regression.md).
