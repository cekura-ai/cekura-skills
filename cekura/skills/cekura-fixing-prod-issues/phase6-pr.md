# Phase 6 — Raise the PR

All phases passed. Raise the PR.

---

## 6a. Create the PR

```bash
gh pr create --title "<fix title>" --body "..."
```

The `project_id` is the `project` field from the agent config fetched in Phase 1.

---

## 6b. PR body template

```
## What changed
<one sentence root cause + fix>

## Test evidence

### Bug reproduction (Phase 2 — expected to FAIL, confirms bug exists)
| Scenario | Result |
|---|---|
| Bug repro | https://dashboard.cekura.ai/PROJECT_ID/results/RESULT_ID ❌ |

### Fix verification (Phase 4 — expected to PASS)
| Scenario | Result |
|---|---|
| Bug repro | https://dashboard.cekura.ai/PROJECT_ID/results/RESULT_ID ✅ |

### Regression tests (Phase 5 — all expected to PASS)
| Case | Result |
|---|---|
| <Happy path>  | https://dashboard.cekura.ai/PROJECT_ID/results/RESULT_ID ✅ |
| <Edge case>   | https://dashboard.cekura.ai/PROJECT_ID/results/RESULT_ID ✅ |

Prod call: #CALL_ID — https://dashboard.cekura.ai/PROJECT_ID/call-logs/CALL_ID
Edge conditions used to reproduce: <e.g. invalid API key, 2s sleep in handler>
```
