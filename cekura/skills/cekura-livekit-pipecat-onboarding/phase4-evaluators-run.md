# Phase 4 — Evaluators and the first run (LiveKit / Pipecat, testing variant)

> **Start:** Announce the step in plain words ("Generating your first evaluators from the prompt") — never a phase number.

**Observability variant: this file does not apply.** Go from [phase3-create.md](phase3-create.md) straight to [phase5-sdk-pr.md](phase5-sdk-pr.md).

## 4a. Generate — no questions

Default metrics are already enabled at project creation; confirm silently with one `metrics_list` (Expected Outcome present) and say nothing unless something is missing.

Call **`scenarios_generate_bg`** immediately — do not ask whether to, which cases to cover, how many, or which personality:

```json
{
  "agent_id": <agent_id>,
  "num_scenarios": 10,
  "generate_expected_outcomes": true,
  "tool_ids": ["TOOL_END_CALL", "TOOL_END_CALL_ONLY_ON_TRANSFER"]
}
```

**Ten scenarios, one personality.** Omit `personalities` — the default is one; never spend a call or a question on it. `agent_speaks_first` on the agent already decides whether the generated evaluators wait for the agent's greeting.

Then wait: **dashboard** `wait_for_scenario_generation` with the returned `progress_id`; **local** poll `scenarios_generate_progress`. If generation fails, retry once with a smaller `num_scenarios`; if it fails again, stop and report — never hand-write a stopgap set.

**Sanity-check the set silently** — this is your check, not a review meeting. Instructions specific and behavioral; expected outcomes achievable; tools right; `scenario_language` patched for a non-English agent. Attach **Expected Outcome** plus one connection metric to every evaluator with one `scenarios_bulk_update`. Fix what is clearly wrong; do not present the set for approval.

## 4b. Ask before running — this is fallback **F4**

Now — and only now — one `<clarification>`:

> "Ten evaluators are ready for `<agent name>`. Run them against your agent now? Each is a real dispatch to your worker through the credentials you just entered, 1–3 minutes apiece."

Options: `["Run them", "Run just one first", "Not now"]`

- **Run them** → 4c with all ten, `frequency: 1`.
- **Run just one first** → 4c with the first generated scenario; once it verifies clean, offer the other nine in one line.
- **Not now** → exit: close with the summary in `cekura-onboarding/phase6-testing-next.md`, open item "no verified run". **Skip the SDK offer** — it is post-results only.

The credentials are the reason this is a question rather than an automatic step: the run is the first thing that touches them, and a run against a wrong or still-placeholder value fails looking exactly like a broken agent.

## 4c. Run

Tool by provider — the agent's `provider.type` from `aiagents_retrieve`, never a guess:

| Provider | Tool |
|---|---|
| `livekit` | `scenarios_run_livekit_v2` |
| `pipecat` | `scenarios_run_pipecat_v2` |

Pass `scenarios` and `frequency: 1`. Then wait: **dashboard** `wait_for_result`; **local** poll `results_retrieve` / `runs_bulk_retrieve` with 30s between reads. Never claim a result you have not read.

## 4d. Verify and share

For each run, three things must be true — say which are, plainly:

1. The call **connected and completed** (not rejected, not timed out).
2. A **two-sided transcript** — both the testing agent and the user's agent spoke.
3. **Metric scores** appeared.

Share the result with the dashboard link (`{dashboard_url}/{project_id}/results/{result_id}` — this one IS project-scoped), the pass/fail count, and one transcript worth reading. 70–80% passing is a normal first result; don't aim for 100%.

**If a call never connected — the credentials are the first thing to check, and say so.** They were placeholders the user replaced by hand; a typo in the API key, secret or server URL, or a dispatch name that doesn't match the worker's registration, fails exactly like a broken agent. Then a `<clarification>` — fallback **F5**:

> "The call didn't connect. Most often that's a mistyped credential or a dispatch name that doesn't match your worker. Want me to walk through it and re-run?"

Options: `["Check credentials and re-run", "Skip for now"]`. *Skip* → exit to the phase6 summary with the failure as an open item; never an implied success.

---

## Phase 4 Gate

At least one run with a completed call, a two-sided transcript and scores — or the user chose *Not now* / *Skip*, recorded as an open item. Then [phase5-sdk-pr.md](phase5-sdk-pr.md): the SDK is offered **only after** results are on screen.
