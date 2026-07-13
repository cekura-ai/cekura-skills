# The Improvement Loop

The edge-case suite is only worth running if the failures turn into fixes. This file maps each stressor family's failure signatures to the **infra-layer** change that resolves it, and defines when a family graduates into the CI/CD regression gate.

## Read transcripts, do not trust status

A red run is not a finding. *How* it went red is the finding, and it determines the fix. Read the transcript for each failing scenario and classify the failure signature before recommending anything. The same red status can mean "hung silently" (needs an idle ladder) or "hallucinated a confirmation" (needs STT confidence gating); opposite fixes.

## Two "fail" signals, and the gap taxonomy

A run's `success=false` conflates two different signals. Separating them is the core of the report:

- **`Expected Outcome`** = the scenario's own resilience verdict (graceful degradation = pass, pathological = fail). This is the signal that matches this skill's intent.
- **`Infrastructure Issues`** = a hard check (agent silent >10s). It can mark a run failed *even when `Expected Outcome=100`* and the task completed. That is a distinct *stall* finding, not "the agent can't handle the stressor."

Classify every run into one of four buckets. Only the first two are agent gaps:

| Bucket | Signature | What it means | Action |
|---|---|---|---|
| **Logic gap** | `Expected Outcome` failed; pathological behavior | Highest-value finding (context loss, hallucinated confirmation, loop) | Pipeline/logic fix below |
| **Stall / latency gap** | `Expected Outcome` passed but `Infrastructure Issues` fired (>10s dead air) | Real, but a different fix; easy to over-report as a logic failure | Timeout / retry / keep-alive |
| **Graceful pass** | `Expected Outcome` passed, no infra breach | The agent genuinely copes | Report as a family the agent survives; do not pad a pass rate |
| **Broken probe** | The stressor never bit (DTMF landed after the turn, tag stored as text) | An eval bug, not an agent finding | Fix the eval and re-run |

**Report gaps, not a pass rate.** These are gap probes; "N% passed" is the wrong headline and hides the findings. Lead with the distinct gaps (grouped, with quoted timestamped evidence), the families the agent survives, and any broken probes.

**Intermittency.** Gaps are often timing-sensitive (a stall on run 2 but not run 1). Run each scenario `frequency: 3–5` and report a rate ("failed 2/5"), not a single coin flip.

## Failure-signature to infra-fix mapping

These are pipeline/infrastructure changes, not prompt edits. If the fix is really a prompt or tool-config change, hand off to **cekura-self-improving-agent** instead.

### Degraded network

| Failure signature (in transcript) | Infra fix |
|---|---|
| Agent acts on garbled input as if correct (hallucinated transcript). | STT confidence gating: discard or re-prompt on below-threshold transcripts. |
| Agent repeats the same line or greeting and never advances. | Add a low-confidence fallback: after N unclear turns, say "I'm having trouble hearing you" and offer a path forward (repeat, callback, transfer). |
| Long dead air / permanent silence. | Jitter buffer + a no-transcript timer that fires a re-prompt instead of waiting forever. |
| Turns close mid-word / clip the caller. | Loosen endpointing under detected packet loss, or gate turn-close on transcript stability. |

### Background noise

| Failure signature | Infra fix |
|---|---|
| Spurious agent turns triggered by noise (agent talks into a gap). | Raise VAD threshold or add noise-floor calibration; suppress turns below a confidence/energy gate. |
| Turns never close (endpointing masked by babble). | Add a hard max-turn duration and energy-based endpointing rather than silence-only. |
| STT garbage acted on as valid. | Same confidence gating as above; a "could you repeat that in a quieter spot?" fallback. |

### Boundary silence / idle

| Failure signature | Infra fix |
|---|---|
| Agent waits indefinitely on caller silence. | Idle re-prompt ladder: prompt at T1, escalate at T2, end/transfer at T3. |
| Agent hangs up too fast on a normal pause. | Increase first idle threshold; separate call-start silence from mid-call silence. |
| Agent loops the same idle prompt forever. | Cap `idle_message_max_spoken_count`; take a terminal action after the cap. |
| At end of task, agent neither closes nor stays useful. | Explicit end-of-call handling: close cleanly after a short grace period of silence. |

### Barge-in / interruption

| Failure signature | Infra fix |
|---|---|
| Agent keeps talking over the caller. | Verify interruption is wired to actually cancel TTS playback and queued audio. |
| Interrupted bot turn corrupts context (agent references what it didn't finish saying). | Truncate the bot utterance in LLM context to what was actually spoken. |
| Audio artifacts / duplicate turns on back-to-back interrupts. | Serialize cancellation; ensure a clean pipeline reset before opening the new user turn. |

### Accent / speech rate

| Failure signature | Infra fix |
|---|---|
| Repeated mishears on accented speech, no recovery. | Consider a more robust STT model/locale; add the low-confidence re-prompt fallback. |
| Slow speaker cut off mid-sentence. | Increase endpointing silence threshold; require transcript stability before closing the turn. |
| Fast speaker's words merged / dropped. | STT segmentation tuning; do not act on partial/interim transcripts as final. |

### DTMF / rapid turns

| Failure signature | Infra fix |
|---|---|
| DTMF during bot speech dropped silently. | Buffer DTMF during TTS and process at turn boundary; document the intended gate. |
| Rapid turns queued, dropped, or duplicated. | Serialize end-of-turn events; guard against re-entrant turn handling. |

## CI/CD graduation

Shashij's constraint holds: an edge case an agent cannot yet survive does not belong in the CI/CD gate; it just produces red builds that everyone learns to ignore.

The lifecycle for each family:

1. **Probe.** It lives in the `Infrastructure Gaps` folder and is expected to fail. It is *not* in the CI gate.
2. **Fix.** The infra change lands (from the mapping above).
3. **Re-run.** Re-run just that family from this suite.
4. **Graduate.** Once it passes reliably, move it into the codebase-derived regression suite (the `Infrastructure Test Suite` folder / CI gate) via **cekura-infra-test-suite**, where it now protects against regressions. At that point the code *does* implement handling, so "only test what's there" applies and it is a legitimate gate test.

The improvement report should state, per family, which of these four stages it is in. That progression is the tangible "used to improve the infra" outcome.

## Report shape

Present the deliverable as one table:

| Stressor family | Ran | Failed | Failure signature (quoted) | Infra fix | Stage |
|---|---|---|---|---|---|
| Degraded network (50% loss) | 1 | 1 | "greeting repeated 4x then silence" | STT confidence gate + trouble-hearing fallback | Probe → needs fix |
| Boundary silence (end) | 1 | 1 | "waited 60s, never closed" | End-of-call idle terminal action | Probe → needs fix |
| Background noise (office) | 1 | 0 | n/a | none | Ready to graduate |

Keep failure signatures quoted from real transcripts so the recommendation is grounded, not inferred.
