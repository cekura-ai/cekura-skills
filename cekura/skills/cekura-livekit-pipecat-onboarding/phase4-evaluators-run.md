# Phase 4 — Evaluators and the first run (LiveKit / Pipecat, testing variant)

> **Start:** Announce the step in plain words ("Generating your first evaluators from the prompt") — never a phase number.

**Observability variant: this file does not apply.** Go from [phase3-create.md](phase3-create.md) straight to [phase5-sdk-pr.md](phase5-sdk-pr.md).

## 4a. Generate — no questions

Default metrics are already enabled at project creation; confirm silently with one `metrics_list` (Expected Outcome present) and say nothing unless something is missing.

**You started this at the end of phase 3** ([phase3-create.md](phase3-create.md) 3a-bis), so the work has been running while the user fetched their credentials — go straight to the wait below with the `progress_id` you already have. Only if you somehow reached here without firing it, call **`scenarios_generate_bg`** now. Either way: do not ask whether to, which cases to cover, how many, or which personality.

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

**Say how long before you block on it.** `wait_for_scenario_generation` returns nothing until the work finishes, so from the user's side the chat simply stops. Silence for two minutes reads as a hang; the same two minutes with "this takes a couple of minutes — writing ten evaluators against your prompt" reads as work. One line, before the call, with the real number in it. Never promise to "come back to you" — you are blocking on it right now, and the answer arrives in this same turn.

**Sanity-check the set silently** — this is your check, not a review meeting. Instructions specific and behavioral; expected outcomes achievable; tools right; `scenario_language` patched for a non-English agent. Attach **Expected Outcome** plus one connection metric to every evaluator with one `scenarios_bulk_update`. Fix what is clearly wrong; do not present the set for approval.

## 4a-bis. If they got back before generation finished — ask the run question early

**This is the normal case, not the edge case.** A user who has replaced provider credentials before is done in well under a minute; generation takes two to three. Starting it early (phase 3) bought back the minute they spent, not the whole three.

So when they confirm, **read `scenarios_generate_progress` once** — one call, not a loop; the runtime throttles progress reads to one per 30s and will tell you to use the waiter instead.

- **Finished** → straight on to the sanity check, then 4b as written.
- **Still running** → say where it actually is, and **ask the run question now**, while it finishes:

> "Almost there — 6 of the 10 evaluators are written, another minute or so. Want me to run them against your agent as soon as they're all ready?"

Options: `["Run them as soon as they're ready", "Run just one first", "Not now"]`

Then block on `wait_for_scenario_generation`, sanity-check the set, and **run immediately — do not ask again.** The question has been asked and answered; a second one after the wait is the same interruption moved later, and it makes the first ask look like it was for nothing.

**The count is read, never estimated.** "6 of 10" comes from `completed_scenarios` / `total_scenarios` in the progress payload. Inventing a number to sound precise is worse than saying "still writing them, about another minute" — which is what to say if the read did not come back with counts.

This is the same fallback **F4** as 4b; only the wording and the timing change.

## 4b. Ask before running — this is fallback **F4**

Now — and only now — one `<clarification>`:

> "Ten evaluators are ready for `<agent name>`. Run them against your agent now? Each one is a real call placed to your worker through the credentials you just entered. They run in parallel, so it's three to four minutes for the whole set, not thirty."

Options: `["Run them", "Run just one first", "Not now"]`

- **Run them** → 4c with all ten, `frequency: 1`.
- **Run just one first** → 4c with the first generated scenario, then the question in 4e — not a one-line prose offer of the other nine.
- **Not now** → exit: close with the summary in [phase6-close.md](phase6-close.md), open item "no verified run". **Skip the SDK offer** — nothing has run, so there is nothing to build on.

The credentials are the reason this is a question rather than an automatic step: the run is the first thing that touches them, and a run against a wrong or still-placeholder value fails looking exactly like a broken agent.

## 4c. Run

Tool by provider — the agent's `provider.type` from `aiagents_retrieve`, never a guess:

| Provider | Tool |
|---|---|
| `livekit` | `scenarios_run_livekit_v2` |
| `pipecat` | `scenarios_run_pipecat_v2` |

Pass `scenarios` and `frequency: 1`. Then wait: **dashboard** `wait_for_result`; **local** poll `results_retrieve` / `runs_bulk_retrieve` with 30s between reads. Never claim a result you have not read.

**Same rule as generation: say the number before you block.** Ten calls run in parallel and take three to four minutes end to end — say that, once, in the message that precedes the wait. A run is the longest silence in this flow and the only one the user can picture, so give them the picture: real calls are being placed to their agent right now.

## 4d. Verify and share

### The switch: once one call has a two-sided transcript, the SDK is on the table

**The moment any run in this conversation produces a two-sided transcript, the user has seen what Cekura does** — evaluators, a real call to their agent, results to read. From that point on, **every question you ask in this phase carries a way forward to the SDK, and none of them offers a bare exit.**

Three things that are NOT part of that bar:

- **Whether the evaluation passed.** A failed evaluator is a finding to report and link, never a gate. Say what failed, point at the results page, and ask the question anyway.
- **Whether the scores are in.** Metric evaluation trails the call by a minute or two.
- **Whether the other nine finished.** One is enough to have seen it.

The offer is always phrased as going forward, never as giving up: *"Tell me about the Cekura SDK and what else it captures"* — not "stop here", not "that's all for now".

**The one path where this does not apply is a run where nothing connected at all** — no call reached the agent, so there is nothing the SDK sentence can refer to and a PR against their repo will not fix a mistyped key. That is F5 below, and it stays a credentials question.

For each run, three things must be true — say which are, plainly:

1. The call **connected and completed** (not rejected, not timed out).
2. A **two-sided transcript** — both the testing agent and the user's agent spoke.
3. **Metric scores** appeared.

Share the result with the dashboard link (`{dashboard_url}/{project_id}/results/{result_id}` — this one IS project-scoped), the pass/fail count, and one transcript worth reading. 70–80% passing is a normal first result; don't aim for 100%.

### The call completed but the metrics are still evaluating

This is the common case: the voice call finishes in 1-3 minutes, the metric evaluation takes a few more. **A connected call is a success — never put "stop here" next to one.** The user has just watched their agent work; offering an exit at that exact moment reads as "we're done, nothing else here", and it throws away the flow's whole remaining half.

Say plainly what happened (the call connected, ran, and is being scored), then ask — `<clarification>`, alone — with the NEXT step as the alternative to waiting:

> "Your agent connected and the call ran clean — the metrics are still scoring. That usually takes another minute or two. While they finish, want to see what else Cekura can do for this agent? The next step wires the Cekura SDK into your repo, so every real production call gets traced and scored the same way, not just these test runs."

Options: `["Show me the SDK step", "Just wait for the scores"]`

- **Show me the SDK step** → [phase5-sdk-pr.md](phase5-sdk-pr.md) **now**, with the run still in flight. Note the result id so you can come back: after the PR is raised (or declined), read the results once more and share the scores before the closing summary. The user gets both.
- **Just wait for the scores** → keep polling, share the results, then the SDK offer as usual.

Never offer to abandon the run, and never end the turn on "let me know when you want to continue" — that is the stall this whole phase exists to avoid.

## 4e. The results are in — report them, then ask where next (fallback **F4c**)

This is the case that had no question at all: the run finishes, some pass, some don't, and the flow used to fall straight through to a closing summary. That is the dead end this phase exists to avoid.

**Report the failures; do not gate on them.** Name the count, say the transcripts and per-metric scores are on the results page, link it, and go straight into the question. Never "let's fix these first" — a first run at 70–80% is normal and the user has other things to see.

> "Six of the ten passed. The four that didn't are worth a look — the transcripts and per-metric scores are at {dashboard_url}/{project_id}/results/{result_id}. Where do you want to go next?"

Options: `["Run the rest", "Tell me about the Cekura SDK and what else it captures", "Walk me through a failure"]`

- **Run the rest** → back to 4c with the scenarios that have not run. When they come back, ask this same question again.
- **Tell me about the Cekura SDK…** → [phase5-sdk-pr.md](phase5-sdk-pr.md).
- **Walk me through a failure** → read one failing transcript, say what went wrong in two or three sentences, then **re-ask this same question**. It is a detour, not an ending.

**There is no fourth option, and no "that's all for now".** If the user wants to stop they will say so in prose, and that is when you go to [phase6-close.md](phase6-close.md) — but it is never something you offer them.

**"I'll run the rest later" is a real answer**, whether they pick it from the options or say it in prose. Treat it as choosing the SDK: the remaining scenarios are saved and ready, say so in one line, and move on to phase 5. It is not a reason to close.

**If every scenario ran and every one passed**, ask the same question without the failure half — `["Tell me about the Cekura SDK and what else it captures", "Walk me through a transcript"]`.

---

**If a call never connected — the credentials are the first thing to check, and say so.** They were placeholders the user replaced by hand; a typo in the API key, secret or server URL, or a dispatch name that doesn't match the worker's registration, fails exactly like a broken agent. Then a `<clarification>` — fallback **F5**:

> "The call didn't connect. Most often that's a mistyped credential or a dispatch name that doesn't match your worker. Want me to walk through it and re-run?"

Options: `["Check credentials and re-run", "I'll fix it and come back"]`.

- **Check credentials and re-run** → walk the fields, then 4c again.
- **I'll fix it and come back** → the phase6 summary, with "no call reached the agent" as the open item, said plainly — never an implied success.

**No SDK offer on this path**, and no third option that reads as giving up. Nothing connected, so "here's what more Cekura can capture" refers to nothing the user has seen, and a pull request against their repo does not fix a mistyped key. Fix the connection first; the rest of the flow is still there afterwards.

---

## Phase 4 Gate

**One two-sided transcript**, from any run in this conversation. That is the whole bar. Then [phase5-sdk-pr.md](phase5-sdk-pr.md).

Not preconditions: a passing evaluation, finished metric scores, or the other nine scenarios having run. A call the user's agent answered and spoke in has already proven the thing the run was for, and everything after it is detail they can read at their own pace.

The one real precondition is that a call connected. Offering the SDK on top of a run that never reached the agent buries a broken connection under new work — that path is F5 and it stays a credentials question.

The other way out is *Not now* at F4, where nothing ran at all: exit to [phase6-close.md](phase6-close.md) with "no verified run" as the open item, and no SDK offer. Every other path through this phase ends by offering the SDK, not by offering to stop.
