# PR Phase — Ship the Fix (Raise a PR, or Emit a PR-Ready Summary)

Final phase. Runs once, after [`regression.md`](regression.md) passes. Packages the verified fix with all its evidence and either raises a PR automatically or hands the user a copy-pasteable summary. **The path is detected, not asked** — only ask if detection is genuinely ambiguous.

**Managed providers never enter or announce this phase.** Stop after Regression
with the validated clone diff and evidence. Never patch or repoint production.

---

## Step PR.1 — Determine the change kind

- **Owned source code in a repo (self-hosted source-file edits, incl. a forked/vendored SDK in the tree)** → real code changes on disk; there's a diff to commit and review. This is the PR path — continue to PR.2. Evidence in the PR body is the Cekura scenario URLs (repro fail-runs + verification/regression pass-runs) — source edits are validated on Cekura like every other fix.
- **Self-hosted non-repo edits** (Cekura mock tools, a DB row) → skip to PR.4 and emit a summary with the validated cumulative diff and result URLs.
- **Render-only (no repo, no live target)** → emit the PR-ready summary (PR.4) with the rendered prompt diff and result URLs; the user applies it.

---

## Step PR.2 — Detect the runtime (PR path only)

Probe — **do not ask**:

1. **Repo checkout?** `git rev-parse --is-inside-work-tree` — is the edited file in a git working tree.
2. **Forge CLI available + authed?** `gh auth status` (or equivalent).
3. **Push access?** Remote writable — `git push --dry-run` succeeds, or `gh repo view` shows write.

Outcome:

- **All three yes** → raise the PR automatically (PR.3).
- **Any clearly no** (no repo, no `gh`, headless, read-only remote) → emit the PR-ready summary (PR.4). Don't ask — the absence is the answer.
- **Ambiguous only** (repo present and committable but `gh` missing / auth unclear) → *this* is the one case to ask: "I can commit locally but couldn't confirm `gh`/push access — raise the PR, or give you a PR-ready summary to push yourself?"

---

## Step PR.3 — Raise the PR automatically

The fix was committed during the loop (the Apply step landed the edits; commit on a fix branch if not already — never the default branch). Push and open:

```bash
gh pr create --title "<fix title>" --body "<body from PR.5>"
```

`PROJECT_ID` for result URLs is the `project` field on the agent record (from Setup / Collect COLLECT.6).

---

## Step PR.4 — Emit a PR-ready summary in-panel

When an automatic PR isn't possible (or the change is render-only), emit a structured, copy-pasteable block:

- **Branch name** — suggested (e.g. `fix/<short-slug>`).
- **Commit message** — the conventional-commit one-liner.
- **Diff** — unified diff of the changed file(s), or the cumulative config / prompt diff for self-hosted non-repo and render-only changes.
- **Full Cekura result URLs** — repro fail-runs, verification pass-runs, regression pass-runs (the PR.5 body).
- **Copy-pasteable PR description** — the PR.5 body, ready for the forge UI.

---

## Step PR.5 — PR body / summary template

```
## What changed
<one-sentence root cause + fix>

## Test evidence
<Cekura E2E simulations on the same transport as the prod call>

### Bug reproduction (REPRO.6 — expected to FAIL, proves the bug)
| Scenario | Runs | Result |
|---|---|---|
| Bug repro | <M/N FAIL> | https://dashboard.cekura.ai/PROJECT_ID/results/RESULT_ID ❌ |

### Fix verification (EVAL.2 — expected to PASS)
| Scenario | Runs | Result |
|---|---|---|
| Bug repro | <M/N PASS> | https://dashboard.cekura.ai/PROJECT_ID/results/RESULT_ID ✅ |

### Regression (Regression phase — all expected to PASS)
| Case | Runs | Result |
|---|---|---|
| <Happy path> | <M/N PASS> | https://dashboard.cekura.ai/PROJECT_ID/results/RESULT_ID ✅ |
| <Edge case>  | <M/N PASS> | https://dashboard.cekura.ai/PROJECT_ID/results/RESULT_ID ✅ |

Prod call: #CALL_ID — https://dashboard.cekura.ai/PROJECT_ID/call-logs/CALL_ID
Failure class: <LLM-based | infra / code>
Iterations to converge: <N>
Cumulative diff: <summary of edits across iterations>
```

The `Prod call` line is optional if the signal was a diagnosed code bug rather than a call.

---

## Done

After raising the PR (PR.3) or emitting the summary (PR.4), report the final outcome: pass rate, iterations used, scenarios that changed verdict, the PR link or in-panel summary, and any upstream hand-offs surfaced during the loop. Stop.
