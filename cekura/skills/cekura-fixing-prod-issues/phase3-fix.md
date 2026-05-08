# Phase 3 — Implement the Fix

> ## ⚠️ E2E SIMULATION REMAINS THE SOURCE OF TRUTH
>
> The only way to validate whether this fix works is through a full end-to-end Cekura voice simulation in Phase 4 — the same real phone call between Cekura's testing agent and your local agent. Unit tests, manual inspection, and code review are useful, but they are **not** a substitute. Do not assume the fix works until Phase 4's E2E simulation passes on Cekura.

The bug is confirmed reproduced. Now write the fix.

---

## 3a. Make code changes

Apply the fix to the relevant file(s). Keep the same edge conditions active in `local_runner.py` — the fix must handle those conditions, not just work under ideal circumstances. A fix that only passes under perfect conditions is not a real fix.

If the fix requires toggling a condition (e.g. re-enabling a valid API key), make it injectable via environment variable or config so it can be switched per test run without code changes.

---

## 3b. Commit locally

```bash
git add <changed files>
git commit -m "fix: <description of what was wrong and what was fixed>"
```

**Do not push.** The fix must pass Phase 4 and Phase 5 first.

---

Move to [Phase 4](phase4-verify.md).
