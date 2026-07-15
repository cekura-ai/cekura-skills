# Stressor Catalog

The canonical set of adversarial infrastructure conditions. Each family is universal: it applies to any voice pipeline whether or not the code was written to handle it. For each family this file gives the mechanism (which personality field or instruction pattern injects it), graded intensities, and the resilience question the run answers.

**Two ways to inject each stressor** (see SKILL.md "Core Insight"): attach a **personality** that carries the trait, or use a **conditional-action tag** on the Normal personality. Prefer selecting an already-enabled personality (`personalities_list` → `projects_enable_personalities_create`); `personalities_create` is often 403, and most traits already exist globally. For stressors no personality carries (packet loss, precise fast speech), use the tag path: `<network_simulation packet_loss="N" />`, `<speed ratio="N" />`, `<hold time="Ns" />`, `<background_noise ...>` (tag at the start of a `fixed_message: true` action). If you do create a personality, inspect one existing personality first to copy the exact nested JSON shape of `network_simulation`, `background_sound_volume`, `stop_speaking_plan`, and `message_plan` rather than inventing it.

All personalities in this suite share a **neutral, cooperative caller `prompt`** ("You are a normal customer trying to complete a simple task"). The stressor, not the caller's attitude, is the variable under test. That keeps a failure attributable to the infra rather than to an adversarial script.

---

## 1. Degraded Network

**Mechanism:** `network_simulation` (packet loss, jitter, latency).

**Why it matters:** real calls ride mobile and VoIP links. Packet loss drops audio frames, so STT sees gaps and partial words; jitter reorders frames; latency delays endpointing and turn-taking. A pipeline with no confidence gating or no jitter buffer degrades badly here, and infra-test-suite never tests it unless the code explicitly implements handling.

**Graded intensities (create one personality each):**

| Name | Level | Intent |
|---|---|---|
| `Edge - Packet Loss 10%` | light | Baseline: agent should be essentially unaffected. |
| `Edge - Packet Loss 30%` | moderate | Where degradation starts to show. |
| `Edge - Packet Loss 50%` | severe | Should trigger graceful "trouble hearing you" behavior, not collapse. |

Add jitter and latency variants (`Edge - High Jitter`, `Edge - High Latency`) if the agent is latency-sensitive (barge-in heavy, or does real-time confirmations). Default minimum: light + severe packet loss.

**Resilience question:** Does the agent detect low-quality input and re-prompt / ask to repeat, or does it hallucinate a transcript, loop, or go silent?

---

## 2. Background / Ambient Noise

**Mechanism:** `background_noise` (e.g. `office`, `street`, `cafe`) + `background_sound_volume` (`{base, reduced}`, 0.0–1.0; `reduced` is the quieter level held during agent speech).

**Why it matters:** callers phone from cars, cafes, and streets. Noise raises the STT floor and can false-trigger VAD (spurious turns) or mask endpointing (turns that never close).

**Graded intensities:**

| Name | background_noise | base volume | Intent |
|---|---|---|---|
| `Edge - Office Noise` | office | ~0.15 | Mild, common condition. |
| `Edge - Cafe Noise Loud` | cafe | ~0.4 | Severe: babble near the caller's speech level. |
| `Edge - Street Noise` | street | ~0.3 | Traffic/wind, intermittent bursts. |

Default minimum: one mild + one loud.

**Resilience question:** Does VAD stay stable (no spurious turns from noise, turns still close), and does STT stay usable or does the agent re-prompt gracefully?

---

## 3. Boundary Silence / Idle Timeouts

**Mechanism:** `message_plan` (`idle_timeout_seconds`, `idle_message_max_spoken_count`) on the personality, plus **`conditional_actions` instructions** that script *when* the caller goes silent. This is the family Slang had zero coverage for.

**Why it matters:** callers pause. The dangerous moments are the boundaries: silence right at call start (before or during the greeting) and silence at the very end (task done, caller says nothing). A pipeline with no idle ladder either hangs forever or hangs up too early.

**Cases (create as conditional-action scenarios):**

| Name | Where the silence falls | Resilience question |
|---|---|---|
| `Edge - Silence At Start` | Caller says nothing for 15–20s after the greeting. | Does the agent re-prompt ("are you there?") on a ladder, then end cleanly, or loop / hang? |
| `Edge - Silence Mid-Call` | Caller goes quiet for 15s mid-task. | Does the agent hold the task context and re-prompt, or reset / abandon? |
| `Edge - Silence At End` | Task complete, caller stays silent. | Does the agent close the call gracefully, or wait indefinitely / repeat the closer? |

Set the personality `message_plan` to a short `idle_timeout_seconds` (e.g. 8–10) with `idle_message_max_spoken_count` of 2–3 so the ladder is exercised within the run.

---

## 4. Aggressive Barge-in / Interruption

**Mechanism:** `interruption_level` (`low`/`medium`/`high`) OR fine-grained `start_speaking_plan` (low wait = interrupts sooner) + `stop_speaking_plan` (`{num_words, voice_seconds, backoff_seconds}`). Note: if `interruption_level` is set, it overrides the manual plans.

**Why it matters:** impatient callers talk over the agent. This stresses interruption handling: does bot audio actually stop, does the pipeline reset cleanly, does the caller's speech get processed without the truncated bot turn corrupting context?

**Cases:**

| Name | Config | Intent |
|---|---|---|
| `Edge - Barge-in High` | `interruption_level: high` | Caller repeatedly cuts in immediately. |
| `Edge - Instant Talk-over` | low `start_speaking_plan` wait (~0.2s) | Caller starts before the agent finishes greeting. |

**Resilience question:** Does the agent yield promptly and recover, or keep talking over the caller, lose the interrupted context, or produce audio artifacts / duplicate turns?

---

## 5. Non-native Speech / Speech Rate

**Mechanism:** `speed` (0.8 slow to 1.2 fast) on the personality; plus, for a single clarity probe, a personality that speaks accented / imperfect English.

**Why it matters:** STT accuracy drops on fast, slow, or non-standard speech. This probes whether the pipeline degrades gracefully (asks to clarify) rather than acting on a misheard value.

**Do NOT enumerate accents by nationality or ethnicity.** For a monolingual agent, ONE generic "non-native / unclear speech" probe covers the STT-robustness dimension. Creating "Indian accent", "Spanish accent", "Chinese accent" variants is both off-target (handling a specific ethnic accent is not an infra gap the agent is designed for) and inappropriate. Test a SPECIFIC language or accent only when the agent's description explicitly lists it as a **supported language**; then it is a real capability test, authored properly in that language with its `scenario_language`.

**Cases (monolingual agent):**

| Name | Config | Intent |
|---|---|---|
| `Edge - Non-native / Unclear Speech` | one accented / imperfect-English personality, named and framed generically | STT robustness on non-standard speech (a single probe, not per-ethnicity). |
| `Edge - Slow Speaker` | `speed: 0.8` | Long pauses may prematurely close turns (endpointing too eager). |
| `Edge - Fast Speaker` | `speed: 1.2` | Words run together; STT segmentation stress. |

**Multilingual agent:** add one full booking probe **per supported language** (a real capability), using that language's personality and `scenario_language`. This is separate from the single non-native probe above.

**Resilience question:** Does the agent understand and complete the task, or repeatedly mishear and fail to recover? For the slow speaker specifically: does endpointing cut the caller off mid-sentence?

---

## 6. DTMF During Speech / Rapid Turns (telephony only)

**Mechanism:** scenario **instructions / `conditional_actions`** (DTMF and turn timing are scripted, not a personality voice trait). Skip entirely for non-telephony (web-widget) agents.

**Why it matters:** callers press keys at awkward moments and fire rapid short utterances. This probes DTMF gating (accepted vs. ignored during bot speech) and the pipeline's handling of back-to-back turns without state corruption.

**Cases:**

| Name | Pattern | Resilience question |
|---|---|---|
| `Edge - DTMF During Speech` | Caller sends DTMF **while the agent is mid-utterance**. | Is it buffered/handled or does it corrupt the turn / get dropped silently? |
| `Edge - Rapid Short Turns` | Several one-word turns back to back. | Does the pipeline serialize them, or queue/drop/duplicate? |

**DTMF timing; do not use a plain `action_followup`.** An `action_followup` fires on the caller's *next* turn, i.e. **after** the agent's reply finishes, so `<dtmf>` sent that way lands in the silence *after* the turn and never tests "during speech" (a common broken probe). To land the digits *into* the agent's utterance, fire them on an interruption offset so they occur while the agent is still speaking:

```json
{ "id": 1, "condition": 0, "type": "action_followup", "fixed_message": true,
  "action": "<interruption time=\"1.5s\" /><dtmf digits=\"12345\" />" }
```

`<interruption time="Xs" />` fires `Xs` after the agent's next turn *begins* (it must be `action_followup` and at the very start of the action), so the DTMF arrives mid-utterance. Verify on the run that the digits' timestamp falls inside the agent's speaking window; if the provider does not support combining the two tags, treat DTMF-during-speech as not testable on that connection rather than shipping a probe that never bites.

---

## 7. Named Real-World Combinations

The one place stacking is allowed: a single named condition that co-occurs in reality. Keep the name descriptive so a failure is still attributable to the *scenario*, even if not to one field.

| Name | Combination | Represents |
|---|---|---|
| `Edge - Mobile Call` | moderate packet loss + street noise | Caller on a phone outdoors. |
| `Edge - Noisy Impatient` | cafe noise + `interruption_level: high` | Busy caller in a loud room. |

Use these sparingly (one or two), on top of the isolated single-variable cases, never as a replacement for them.

---

## Expected-outcome exemplars (write sharp, not lenient)

The single biggest content failure mode is a vague `expected_outcome_prompt` full of "OR" escape hatches ("completes the booking OR asks to repeat OR ends cleanly"); under that, a bot that stalled for 15 seconds still scores PASS because the booking eventually completed, and the probe misses the gap it existed to catch. Every expected outcome must be **falsifiable**: name the concrete pathological signal for that stressor as a hard FAIL, even when the task nominally completes.

Two rules for every family:
- **A >10s stretch of dead air is always a FAIL**, regardless of whether the task completed. Do not let the EO rely on the separate Infrastructure Issues metric to catch stalls; state it in the EO itself.
- **Confirming or acting on a value the caller never said is always a FAIL** (hallucinated slot/name/detail), even if it produces a "successful" booking.

Per-family FAIL signals to state explicitly (PASS = the agent avoids all of them and stays on task):

| Family | Hard FAIL signals to name in the EO |
|---|---|
| Degraded network | >10s dead air; confirms a value the caller never said; repeats the same line 2+ times without progressing; proceeds silently on garbled audio instead of asking to repeat |
| Background noise | responds to noise as if it were speech (spurious turn); a turn never closes; >10s dead air; confirms wrong/invented details |
| Boundary silence | no re-prompt at all (permanent dead air); hangs up before the first idle threshold; loops the same nudge more than its limit; never ends the call |
| Barge-in | keeps talking over the caller; **after yielding, contradicts or forgets a value/result established before the interruption**; repeats an already-completed step |
| Accent / speech rate | proceeds on a misheard value; asks the caller to repeat the same thing 3+ times with no progress; (slow speaker) commits the turn before the caller finished the sentence |
| DTMF / rapid turns | DTMF echoed back as spoken text or misread as speech; a turn dropped, duplicated, or reordered; state corrupted |

Write the EO as: one line of what graceful handling looks like for this stressor, then "FAIL if any of:" with the concrete signals above. Keep the PASS side to genuine graceful degradation, not a menu of ways to pass.

## Sizing the suite

A default run selecting the common families lands around 12–20 scenarios:

- Network: 2 (light + severe packet loss)
- Noise: 2 (mild + loud)
- Boundary silence: 3 (start / mid / end)
- Barge-in: 2
- Speech rate + non-native clarity: 3 for a monolingual agent (slow, fast, one generic non-native probe); for a multilingual agent add one probe per supported language
- DTMF / rapid turns: 2 (telephony only)
- Named combinations: 1–2

Drop network + DTMF for web-widget agents. Add graded jitter/latency and extra noise environments only when the agent's use case justifies the extra credits.
