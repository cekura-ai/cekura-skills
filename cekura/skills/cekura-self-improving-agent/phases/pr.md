# PR Phase — Ship the Fix (Raise a PR, or Emit a PR-Ready Summary)

Final phase. Runs once, after the Regression phase passes. It packages the verified fix with all its Cekura evidence and either raises a PR automatically or hands the user a copy-pasteable summary. **The path is detected, not asked** — only ask if detection is genuinely ambiguous.

---

## Step PR.1 — Determine what kind of change was made

The managed-provider modes and self-hosted runs ship differently:

- **Edits live in the user's source repo (self-hosted source-file edits)** → the fix is real code changes on disk. This is the PR path: there is a diff to commit and review. Continue to PR.2.
- **Edits live on a managed provider or in Cekura config (VAPI / ElevenLabs clone, or self-hosted edits that aren't source code in a repo — Cekura mock tools, a database row)** → there is no code diff in a repo to open a PR against. Skip straight to PR.4 and emit a **promotion summary** instead: the validated cumulative config diff plus the instruction to promote it to production (for VAPI / ElevenLabs, that's promoting the clone's diff to the live agent — never automatic; see [`clone.md`](clone.md)), with all the same Cekura result URLs.
- **Render-only (no repo, no live target)** → Emit the PR-ready summary (PR.4) with the rendered prompt diff and result URLs; the user applies it themselves.

---

## Step PR.2 — Detect the runtime (PR path only)

Auto-detect whether an automatic PR is possible. **Do not ask the user any of these — probe them:**

1. **Running inside a coding agent with a repo checkout?** Confirm the edited file is inside a git working tree (`git rev-parse --is-inside-work-tree`).
2. **Is `gh` (or the equivalent forge CLI) available and authenticated?** (`gh auth status`.)
3. **Does the user have push access?** (Remote is writable — e.g. `git push --dry-run` succeeds, or `gh repo view` shows write permission.)

Outcome:

- **All three yes →** raise the PR automatically (PR.3).
- **Any clearly no (no repo, no `gh`, headless, read-only remote) →** emit the PR-ready summary (PR.4). Do not ask — the absence is the answer.
- **Ambiguous only (e.g. repo present and committable but `gh` missing or auth state unclear) →** *this* is the one case to ask: "I can commit locally but couldn't confirm `gh`/push access — should I try to raise the PR, or give you a PR-ready summary to push yourself?"

---

## Step PR.3 — Raise the PR automatically

The fix was committed during the loop (the self-hosted source-file Apply step landed the edits; commit them on a fix branch if not already committed — never on the default branch). Push the branch and open the PR:

```bash
gh pr create --title "<fix title>" --body "<body from the template below>"
```

Use the PR body template in PR.5. The `PROJECT_ID` for result URLs is the `project` field on the agent record (from Setup / Reproduce REPRO.1).

---

## Step PR.4 — Emit a PR-ready summary in-panel

When an automatic PR isn't possible (or the change is managed-config, not code), emit a structured, copy-pasteable block in the coding agent's panel so the user can take it from there. Include:

- **Branch name** — a suggested branch (e.g. `fix/<short-slug>`).
- **Commit message** — the conventional-commit one-liner.
- **File diff** — the unified diff of the changed file(s) (PR path), OR the cumulative config / prompt diff (managed-config / render-only path), in a fenced block ready to apply.
- **Full Cekura result URLs** — reproduction fail-runs, verification pass-runs, regression pass-runs (the PR.5 template body).
- **A copy-pasteable PR description** — the PR.5 body, ready to drop into the forge UI.

For managed-config modes, replace "file diff" with the promotion instruction (which provider fields changed and that the user promotes the clone → live agent deliberately).

---

## Step PR.5 — PR body / summary template

```
## What changed
<one-sentence root cause + fix>

## Test evidence (all E2E simulations on Cekura, same transport as the prod call)

### Bug reproduction (Reproduce REPRO.6 — expected to FAIL, proves the bug)
| Scenario | Runs | Result |
|---|---|---|
| Bug repro | <M/N FAIL> | https://dashboard.cekura.ai/PROJECT_ID/results/RESULT_ID ❌ |

### Fix verification (Eval EVAL.2 — expected to PASS)
| Scenario | Runs | Result |
|---|---|---|
| Bug repro | <M/N PASS> | https://dashboard.cekura.ai/PROJECT_ID/results/RESULT_ID ✅ |

### Regression (Regression phase — all expected to PASS)
| Case | Runs | Result |
|---|---|---|
| <Happy path> | <M/N PASS> | https://dashboard.cekura.ai/PROJECT_ID/results/RESULT_ID ✅ |
| <Edge case>  | <M/N PASS> | https://dashboard.cekura.ai/PROJECT_ID/results/RESULT_ID ✅ |

Prod call: #CALL_ID — https://dashboard.cekura.ai/PROJECT_ID/call-logs/CALL_ID
Failure class: <LLM-based | infra>
Iterations to converge: <N>
Cumulative diff: <summary of edits across iterations>
```

---

## Done

After raising the PR (PR.3) or emitting the summary (PR.4), report the final outcome: pass rate, iterations used, scenarios that changed verdict, the PR link or the in-panel summary, and any upstream hand-offs surfaced during the loop. Stop.
