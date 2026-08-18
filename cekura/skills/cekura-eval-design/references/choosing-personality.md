# Choosing a Personality

## What Personality Controls

`personality` is a **required** field on every scenario. It controls the testing agent's voice and behavioral defaults at the infrastructure level.

### Personality Prompt

Every personality has a `prompt` field — a system prompt given to the **testing/simulated caller agent** that shapes its overall conversational style, tone, and role throughout the call. This is distinct from scenario instructions:

| | Personality prompt | Scenario instructions |
|---|---|---|
| **Scope** | Entire call — shapes baseline tone and role | Step-by-step — what to say and do |
| **Example** | "You are an impatient small business owner who speaks quickly and rarely elaborates" | "Ask about the refund policy. If the agent asks for your order number, provide it." |
| **Layer** | Infrastructure (baked into the caller agent's system prompt) | Runtime (scripted turn sequence) |

When selecting a personality, check its prompt to understand how the testing agent will behave — the name alone may not tell the full story.

### Voice and Audio Configuration

| Parameter | What it controls |
|---|---|
| Voice model / provider | ElevenLabs, Cartesia, etc. |
| Language and accent | American English, Spanish, Hindi, Brazilian Portuguese, etc. |
| Gender | Male, female, neutral |
| Speech speed | 0.8× (slow) to 1.2× (fast) relative to normal |
| Background noise | Off, office, street, café, etc. |
| Background sound volume | Base level and reduced level during agent speech (0.0–1.0) |

### Interruption Configuration

| Parameter | What it controls |
|---|---|
| Interruption level | Overall aggressiveness: low → medium → high |
| Start speaking delay | Seconds the caller waits before speaking (lower = more interruptive) |
| Stop speaking plan | How quickly the caller yields when the agent starts talking (num_words, voice_seconds, backoff_seconds) |

These three parameters work together. `interruption_level` applies a preset that sets both the start and stop speaking plans automatically. Fine-grained control is available by configuring `start_speaking_plan` and `stop_speaking_plan` directly — but if both an `interruption_level` and manual plans are set, the `interruption_level` preset overrides the manual values.

### Additional Configurations

| Parameter | What it controls |
|---|---|
| Idle timeout | Seconds of silence before the testing agent sends an idle message (default: 10s) |
| Idle message count | Max times the idle message is repeated before the agent gives up (default: 3) |
| Network simulation | Simulate packet loss, jitter, and latency (0–100%) for degraded-network testing |
| Cartesia emotion | Emotional tone applied to Cartesia Sonic-3 voice generation |
| Cartesia volume | Volume multiplier for Cartesia voice output |

Network simulation is especially useful for testing how the main agent handles real-world call quality degradation — poor mobile connections, VoIP jitter, etc.

**Instructions cannot change any of the above.** Instructions only control what the testing agent says, not how it sounds or behaves at the voice layer. If you write "speak in a mumbling voice and interrupt frequently" in instructions, the agent will ignore that phrasing at the infrastructure level. Use personalities instead.

---

## Changing Personality Behavior (Not Just Selecting One)

Selection is not the only lever. When no available personality has the behavior a test needs, **create or fork one** — do not fall back to writing the behavior into instructions, the expected outcome, or the agent's description. Those surfaces cannot override the voice layer, so that attempt always fails silently: the test runs, the personality wins, and the user is left debugging prose.

### Symptom → cause

Users describe these as agent problems. They are personality settings.

| What the user reports | Actual cause | Fix |
|---|---|---|
| "The testing agent keeps asking 'Are you still there?' mid-test" | Idle timeout (default 10s) | Raise `message_plan.idle_timeout_seconds` on a personality they own |
| "I told it to stay silent / not answer and it responds anyway" | Idle timeout — the idle prompt fires regardless of instructions | Same. Also see `<hold>` below for a single-step pause |
| "It talks over my agent" | Interruption preset | Personality with a lower `interruption_level` |
| "It speaks too fast / wrong accent / no background noise" | Voice config | Different personality, or fork and adjust |

**Never** propose an Agent Description or evaluator-instruction edit as the fix for any row in this table.

### How to change it

1. `GET /test_framework/v1/personalities/` (`personalities_list`) — read the current `message_plan` on the candidate personality. Its `idle_timeout_seconds` / `idle_message_max_spoken_count` come back in the response, so check before assuming the 10s / 3 defaults.
2. **The personality is global** (no `project` / `organization` owner — every pre-defined personality is): it is shared across all organizations and cannot be edited. Fork it into the user's project first, then update the copy — two calls:

   ```
   POST /test_framework/v1/personalities/{id}/fork/   (`personalities_fork_create`)
   {"project_id": 1234}

   PATCH /test_framework/v1/personalities/{fork_id}/  (`personalities_partial_update`)
   {"message_plan": {"idle_timeout_seconds": 45}}
   ```

   The fork inherits every setting from its source and is enabled for the project automatically. Assign the fork's id to the scenario.
3. **The personality is already owned by the user's org** (including a fork made earlier): patch it in place with `personalities_partial_update`. Note this affects every scenario already using it — if that is not wanted, fork it first.
4. Confirm before creating a fork the user did not ask for — "I'll fork it into this project and set the idle timeout to 45s." A fork is a new resource in their workspace.

`personalities_partial_update` is where every one of these settings is changed — not just idle. `personalities_fork_create` only copies; it takes no setting overrides. Both idle fields must be positive integers, and idle behavior cannot be switched off entirely — to keep the testing agent silent through a long pause, raise the timeout past the expected silence.

### `<hold>` vs. idle timeout

Both are valid; they solve different shapes of the problem.

| | `<hold time="Xs" />` | Personality idle timeout |
|---|---|---|
| Scope | One step of a conditional-actions scenario | Every silence in the call |
| Idle prompt | Suppressed — the idle timer is paused for the hold's duration, so a hold longer than the timeout is safe | Deferred until the new timeout elapses |
| Use when | The silence is scripted and you know where it falls | The silence is open-ended, or the scenario is behavioral (no `conditions[]` to hang a tag on) |

So a `<hold>` does not need a matching timeout change — it is the better tool for a known, bounded pause (see `references/conditional-actions.md`). Reach for the personality when the wait is not inside a hold: a behavioral scenario, or an unpredictable wait on the main agent.

---

## Core Selection Rule: Sustained vs. Temporary Behaviors

Only map a **sustained, call-wide behavior** to personality. A temporary state for a single utterance does not define the personality — it's just a scripted line.

| Behavior | Maps to personality? | Why |
|---|---|---|
| "Caller is impatient throughout the call" | ✅ Yes | Sustained emotional state |
| "There is constant background street noise" | ✅ Yes | Persistent environmental condition |
| "Caller speaks slowly and uses simple language" | ✅ Yes | Consistent speech pattern |
| `Says in a panicked tone: 'I need this fixed now!'` | ❌ No | Single-utterance emotional tone — use Normal personality |
| "At step 4, the caller gets frustrated" | ❌ No | Isolated moment — encode in instructions, not personality |

**When in doubt, default to Normal.** A temporary behavior is better handled in instructions than by picking an interrupter personality that affects the entire call.

---

## Interruption Quantification

When a scenario describes interruptive or impatient behavior, quantify before selecting the tier:

| Description | Personality tier |
|---|---|
| 4 or more distinct interruptions described | Interruptive (High) |
| 1 isolated interruption described | Interruptive (Low) |
| General impatience or "in a hurry" — no specific count | Interruptive (Medium) |

Examples:
- "Interrupts the agent four or more times during the call" → Interruptive (High)
- "Cuts in once to ask about the wait time" → Interruptive (Low)
- "Caller is impatient and wants things done quickly" → Interruptive (Medium)

---

## Scenario Type: Behavioral vs. Conditional-Actions

### Behavioral scenarios

Match personality to scenario intent. Recommended suite distribution for full coverage:

| Scenario intent | Personality to use |
|---|---|
| Happy path / baseline | Normal Male/Female (same language) |
| Urgent / fast-paced caller | Interruptive (Medium or High) |
| Real-world ambient noise | Background noise personality (street, café, office) |
| Non-native / accented speaker | Language-specific accent or Slow Speaker |
| Frustrated / aggressive caller | Interruptive (High) |


### Conditional-actions scenarios

**Strongly prefer Normal** for the scenario's language — behavioral logic is encoded in `conditions[]`, not in personality.

The exception: use a non-Normal personality when a **call-wide, sustained trait** is needed alongside the scripted conditions — for example, persistent background noise or a specific accent throughout the entire conversation. In that case, pick the personality for that trait, not for any single-step behavior.

**Do not** select an Interruptive personality just to simulate one interruption. Encode it in a `conditions[]` entry instead.

---

## Language Selection — Always First

Language must be determined before personality, because personalities are language-specific. Running the wrong language personality against a non-English scenario produces incorrect TTS pronunciation.

1. **Identify the scenario language** from the scenario instructions or agent description.
2. **List personalities for the project** via `GET /test_framework/v1/personalities/` and filter by language.
3. **Match tone within the language-filtered list** — don't select a personality in the wrong language even if the tone matches better.
4. **For multilingual agents:** Use semantic matching for mixed-language labels — "Hinglish" matches Hindi + English personalities, "Spanglish" matches Spanish + English. If no exact dialect match exists, use the closest available option.

**Dialect precision matters** — Brazilian Portuguese and European Portuguese are distinct. When the agent description specifies a region, match it.

---

## Checking Enabled/Disabled Status

Always list available personalities via `GET /test_framework/v1/personalities/` before assigning. Available personalities vary per project — do not guess or invent names.

Rules:
- **Only assign personalities that are currently enabled for the project.**
- **Never use a personality name not returned by the API.** Inventing a name is different from creating one: if the behavior needed does not exist yet, fork or create a personality (see "Changing Personality Behavior" above) and assign the id the API returns.
- **If the ideal personality is disabled:** tell the user which personality would be a better fit, ask if they want to enable it in project settings, and wait for their response. Do not write the scenario with a disabled personality — always use an enabled one in the final payload.

Example flow when the best match is disabled:
> "The 'Frustrated Customer (High)' personality would be a strong fit here, but it's currently disabled for this project. Would you like to enable it in project settings before creating this scenario? If not, I'll use 'Interruptive (Medium)' which is currently enabled."

---

## Fallback Logic

When no sustained behavioral cue is present, or no personality matches the described behavior:

| Situation | Fallback |
|---|---|
| Standard language agent, no behavioral cue | Normal personality for the scenario's language |
| Normal personality missing from the project | Most neutral available personality |
| Multilingual agent, specific personality set on the agent | Use that personality ID |
| Multilingual agent, no personality set | Most appropriate available personality for the detected language |

**Safe defaults (always look up the ID — never hardcode one):**
- Every scenario → pick the "Normal" personality matching the scenario's language via `personalities_list` with `language=<code>` (English included: `language=en`), and set `scenario_language` to the correct code so TTS uses the right language for pronunciation. When several "Normal" variants exist for the language, default to the **male** one ("Normal Male …") — the platform's historical default — unless the scenario's persona implies otherwise
- **Never pass `project_id` on these language lookups** — predefined personalities are global (no project owner), and a `project_id` filter silently excludes all of them, making it look like no language-matched personality exists
- Multiple languages / code-switching in one scenario → use a multilingual personality (`language=multi`, e.g. "Normal (Spanish + English)")
- Language-matched personality returns "Personality is not enabled" (or none exists) → `scenario_language` is **coupled to the personality's language by design** (the API rejects a mismatch — do not try to work around it). Resolve in this order: (1) enable or create/fork a personality in the target language (e.g. fork a Normal personality and set its language/voice) and use that; (2) if that isn't possible, fall back to a normal English personality and leave `scenario_language` as `en`, keeping the caller's content (first message, instructions/conditions) in the target language — and disclose plainly that TTS/transcription will be English-biased until a target-language personality exists
- Mixed-language scenario but no multilingual (`language=multi`) personality available → fall back to the Normal Male personality of the scenario's dominant non-English language (its voice model usually handles the English portions), note the limitation in your summary

---

## Quick-Reference Decision Tree

```
Is it a conditional-actions scenario?
  Yes → Use Normal for the language (strong default)
          Need a call-wide sustained trait on top (bg noise, accent)?
            → Pick that personality; don't pick Interruptive for a single interrupt
  No ↓

What's the scenario language?
  → GET /test_framework/v1/personalities/ → filter by language

Is the needed behavior about idle/stall timing, interruption, speed or noise?
  Yes → is there an enabled personality that already has it?
          No → patch one the org owns, or fork the closest match
               and patch the copy — never encode it in instructions
  No ↓

Is there a sustained behavioral cue?
  No → Normal (fallback)
  Yes → match against personality name and description:
    Interruptive / impatient?
      Count distinct interruptions:
        4+ → Interruptive (High)
        1  → Interruptive (Low)
        General impatience → Interruptive (Medium)
    Background noise? → background noise personality
    Slow / fast speech? → speech rate personality
    Specific accent? → language-specific accent personality

Is the matched personality ENABLED?
  Yes → use it
  No  → tell user, ask if they want to enable it,
         wait for response; always finalize with an enabled personality
```
