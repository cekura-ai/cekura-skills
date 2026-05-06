# Phase 4 — Verify the Fix

> ## ⚠️ E2E SIMULATION OVER TWILIO SIP TELEPHONY IS THE ONLY VALID VERIFICATION
>
> **Verification MUST be done through a full end-to-end Cekura voice simulation using Twilio SIP telephony** — the exact same evaluator from Phase 2, triggered via `run_voice`, with the local bot dialing Cekura over `twilio-sip-dial-out`.
>
> ❌ Do NOT use Daily/WebRTC. ❌ Do NOT use text mode. ❌ Do NOT use any transport other than Twilio SIP.
>
> The fix is not verified until Cekura's metric scores show it passing on a real voice call. A fix that passes code review or unit tests but fails the E2E simulation is not a valid fix.

Re-run the same evaluator from Phase 2 against the fixed code. The same conditions that reproduced the bug must now be handled correctly by the fix.

---

## 4a. Trigger a new voice run

Use the same `scenario_id` from Phase 2 — do not create a new evaluator:

```bash
source ${CLAUDE_PLUGIN_ROOT}/scripts/cekura-api.sh
run_voice "SCENARIO_ID" '{"agent_number": "+19789751706"}'
```

From the response, note the new Cekura outbound number and update `dialout_settings.sip_uri` in `local_runner.py`.

Run the local bot with the fix applied and edge conditions still active:

```bash
cd twilio-sip-dial-out && LOCAL_RUN=1 python bot.py &
```

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
