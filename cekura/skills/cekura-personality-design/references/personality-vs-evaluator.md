# Personality vs. Evaluator vs. Metric

## Why this matters

These three are the only places test behavior can live, and they do not overlap. Putting a request in the wrong one is the most expensive mistake in Cekura, because **it does not error**. The evaluator runs, the report comes back green, and the thing the user asked for never happened. They then debug their agent's prompt for a behavior the test never exercised.

| | Personality | Evaluator | Metric |
|---|---|---|---|
| Question | Who is calling, and how do they sound? | What are they trying to do? | Did the call go well? |
| When it applies | As the call is dialled | Turn by turn during the call | After the call ends |
| Reusable across | Many evaluators | Many runs | Many calls |
| Tools | `personalities_*` | `scenarios_*`, `test_profiles_*` | `metrics_*` |

## Routing by duration, not by wording

The deciding question is never *how the user phrased it* — it is **how long the behavior lasts**.

| Request | Goes to | Why |
|---|---|---|
| "Caller has a thick Scottish accent" | Personality (`voice_id`) | Every syllable of the call |
| "Caller is impatient and cuts in constantly" | Personality (`interruption_level`) | A habit, not an event |
| "There's constant street noise" | Personality (`background_noise`) | Environmental, call-wide |
| "Caller speaks slowly and simply" | Personality (`speed` + `prompt`) | Consistent speech pattern |
| "Caller is on a terrible connection" | Personality (`network_simulation`) | Line condition |
| "Caller is barely audible" | Personality (`voice_volume`) | Not a thing they say |
| "Caller goes quiet for 30s waiting for the agent" | Personality (`message_plan.idle_timeout_seconds`) or a `<hold>` step | The idle prompt fires regardless of instructions |
| "At step 4 the caller gets frustrated" | Evaluator instructions | One moment |
| "Caller interrupts once to ask about the wait" | Evaluator condition | A single event |
| "Caller says this in a panicked tone" | Evaluator instructions | One utterance |
| "Caller refuses to give their DOB until pushed" | Evaluator instructions | Task logic |
| "Agent must never quote a price" | Metric | A judgement on the finished call |
| "Score how natural the agent sounded" | Metric | Post-call scoring |

Rule of thumb: **if removing it would change how the caller sounds on every single turn, it is a personality.** Otherwise it is an evaluator step or a metric.

## Symptom → cause → fix

Users report all of these as agent problems or evaluator problems. Every one is a personality setting.

| Reported | Actual cause | Fix |
|---|---|---|
| "The testing agent keeps asking 'are you still there?' mid-test" | Idle timeout (default 10s) | Raise `message_plan.idle_timeout_seconds` on a personality the org owns |
| "I told it to stay silent and it talks anyway" | Idle prompt fires regardless of instructions | Same — or a `<hold time="Xs" />` step for a bounded, scripted pause |
| "It talks over my agent" | Interruption preset | Lower `interruption_level` |
| "It never lets my agent finish a sentence" | Interruption preset | Same |
| "It speaks too fast" | `speed` | Patch `speed` |
| "Wrong accent" / "it sounds American, I need Indian" | `voice_id` | Different voice — see `voice-and-accent.md` |
| "The accent field says British but it sounds American" | `accent` was set by hand before it became derived | Re-patch `voice_id`; the label re-derives from the voice |
| "I set accent to Indian and nothing changed" | `accent` is a derived label, not a knob | Pick an Indian-accented voice |
| "There's no background noise" | `background_noise` is `off` | Set it, or pick a Bg Noise variant |
| "My agent can hear it fine — I wanted a hard-to-hear caller" | `voice_volume` | Lower it |
| "The call sounds too clean for a mobile test" | No `network_simulation` | Enable packet loss / jitter / latency |
| "It read the phone number as words" | Language / voice model mismatch | Fix `language`, then the voice |
| "My multilingual test only speaks English" | Personality is single-language | Use a `language=multi` personality |

**Never** propose an Agent Description or evaluator-instruction edit as the fix for any row in this table. Those surfaces cannot reach the voice layer, so the attempt always fails silently — and it teaches the user that the platform is unreliable rather than that the setting lives elsewhere.

## When the fix is an evaluator change after all

Not everything that *sounds* like a voice problem is one:

- "It asked for the account number before verifying identity" — evaluator turn order.
- "It hung up before the transfer completed" — the evaluator's end-call tool choice (`TOOL_END_CALL_ONLY_ON_TRANSFER`).
- "It gave up after one rejection" — evaluator instructions; persistence is task logic.
- "It said it was a new patient but the profile says established" — test profile data.

The tell: these are all about *content and sequence*. If you can describe the fix as words the caller should or shouldn't say, it is an evaluator.

## Ownership and blast radius

- A personality with no `project`/`organization` owner is **globally available** — shared across all organizations and not editable. Fork it into the project first.
- Patching a personality the org owns affects **every evaluator already using it**, on the next run. There is no per-evaluator override. Fork when the change should be narrow.
- A per-run override exists for sweeps only: `personality_ids` on the run call swaps the personality for that run without touching any evaluator.
- Confirm before creating a fork the user did not ask for — it is a new resource in their workspace.
