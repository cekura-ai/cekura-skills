---
name: cekura-fixing-prod-issues
description: Debugs a failing production call, reproduces the bug with Cekura evaluators, implements a fix, verifies it, runs regression tests, then raises a PR with evidence. Use when the user wants to fix a production call bug, investigate a failing prod call, reproduce and fix a production issue, run regression tests before a PR, or says things like "fix this prod call issue", "debug and fix call ID", "test my fix against prod scenarios", "reproduce this production bug", or "regression test before raising PR".
license: MIT
compatibility: Requires a Cekura account (https://dashboard.cekura.ai) — sign in via OAuth or use an API key.
---

# Fixing Production Call Issues

Full workflow — **debug first, reproduce before fixing, test thoroughly, then PR**.

```
Phase 1      Phase 2         Phase 3     Phase 4        Phase 5        Phase 6
Debug   →   Reproduce   →   Fix    →   Verify    →   Regression  →   PR
Understand   Confirm bug     Write the   Same eval      Happy paths    All result
root cause   on Cekura       code fix    must PASS      + edge cases   URLs in PR
             BEFORE fix      + commit    now            pass too
```

## The 6 Phases

| Phase | File | What happens |
|---|---|---|
| 1 | [phase1-debug.md](phase1-debug.md) | Fetch prod call + logs, identify root cause, confirm with user |
| 2 | [phase2-reproduce.md](phase2-reproduce.md) | Build evaluator, attach metrics, run — eval **must fail** before any fix |
| 3 | [phase3-fix.md](phase3-fix.md) | Write the code fix, commit locally |
| 4 | [phase4-verify.md](phase4-verify.md) | Re-run same evaluator — eval **must pass** now |
| 5 | [phase5-regression.md](phase5-regression.md) | Test all affected happy paths and edge cases |
| 6 | [phase6-pr.md](phase6-pr.md) | Raise PR with all Cekura result URLs |

---

## Strictness Rules — Read Before Starting

These rules are non-negotiable. Do not proceed past a gate without satisfying it.

### Rule 0 — Use the same connection medium as the production call. No exceptions.

**Every reproduction, verification, and regression test MUST be a full end-to-end simulation on Cekura using the same transport the agent is configured for.** Retrieve the agent record (`GET /test_framework/v1/ai-agents/{id}/`) to confirm its transport. Most likely telephony, but follow what the agent is actually configured to use.

❌ Text mode is never a valid substitute. ❌ Do not switch transports between phases.

The bug lives in the real call path; only a simulation over the same medium can confirm it.

### Rule 1 — Phases are sequential. No skipping.

Each phase has a gate. A gate is not passed by assumption — it is passed by evidence. The sequence exists because:
- You cannot write a good fix without understanding the root cause (Phase 1 gate)
- You cannot trust a fix without first proving the bug exists in a controlled way (Phase 2 gate)
- You cannot call regression tests meaningful without a passing fix verification (Phase 4 gate)

### Rule 2 — Phase 2 is the hardest gate. Treat it as such.

Reproducing the bug is the most critical step. **Do not move to Phase 3 until the eval definitively fails on Cekura with metric scores showing the failure.** If there is any doubt about whether the bug is truly reproduced, stop and ask the user. Do not guess.

### Rule 3 — When in doubt, ask.

If you are unsure which metrics to use, whether the root cause is correct, whether the edge conditions are right, or whether a result is ambiguous — **stop and ask the user**. A wrong assumption here wastes the entire workflow.

### Rule 4 — Never push code until Phase 5 is complete.

The commit happens in Phase 3. The push happens only after all regression tests pass in Phase 5.
