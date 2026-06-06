# Choosing a Personality

## What Personality Controls

`personality` is a **required** field on every scenario. It controls the testing agent's voice at the infrastructure level:

- **Voice model and provider** — ElevenLabs, Cartesia, etc.
- **Language and accent** — American English, Spanish, Hindi, etc.
- **Interruption level** — how frequently the caller cuts in
- **Background noise** — office ambience, street noise, café, etc.
- **Speech speed and pattern** — slow, fast, mumbling, etc.

**Instructions cannot change any of these.** Instructions only control what the testing agent says, not how it sounds. If you write "speak in a mumbling voice and interrupt frequently" in instructions, the agent will ignore that phrasing at the voice layer. Use personalities instead.

---

## Core Selection Rule: Sustained vs. Temporary Behaviors

Only map a **sustained, call-wide behavior** to personality. A temporary state for a single utterance does not define the personality — it's just a scripted line.

| Behavior | Maps to personality? | Why |
|---|---|---|
| "Caller is impatient throughout the call" | ✅ Yes | Sustained emotional state |
| "There is constant background street noise" | ✅ Yes | Persistent environmental condition |
| "Caller speaks slowly and uses simple language" | ✅ Yes | Consistent speech pattern |
| "Caller waits silently on hold for 120 seconds" | ✅ Yes | Prolonged state (use Call Hold personality) |
| `Says in a panicked tone: 'I need this fixed now!'` | ❌ No | Single-utterance emotional tone — use Normal personality |
| "At step 4, the caller gets frustrated" | ❌ No | Isolated moment — encode in instructions, not personality |

**When in doubt, default to Normal.** A temporary behavior is better handled in instructions than by picking an interrupter personality that affects the entire call.

---

## Interruption Quantification

When a scenario describes interruptive or impatient behavior, quantify before selecting the tier:

| Description | Personality tier |
|---|---|
| 2 or more distinct interruptions described | Interruptive (High) |
| 1 isolated interruption described | Interruptive (Low) |
| General impatience or "in a hurry" — no specific count | Interruptive (Medium) |

Examples:
- "Interrupts the agent twice during the call" → Interruptive (High)
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
| Silent hold wait | Call Hold |

**Rough distribution for a balanced suite:**
- ~60% standard (Normal Male/Female in the scenario's language)
- ~20% challenging (interruptive, fast-paced, background noise)
- ~10% non-native or accented speakers
- ~10% edge cases (frustrated, extreme speech rate, hold wait)

### Conditional-actions scenarios

**Strongly prefer Normal** for the scenario's language — behavioral logic is encoded in `conditions[]`, not in personality.

The exception: use a non-Normal personality when a **call-wide, sustained trait** is needed alongside the scripted conditions — for example, persistent background noise or a specific accent throughout the entire conversation. In that case, pick the personality for that trait, not for any single-step behavior.

**Do not** select an Interruptive personality just to simulate one interruption. Encode it in a `conditions[]` entry instead.

---

## Language Selection — Always First

Language must be determined before personality, because personalities are language-specific. Running the wrong language personality against a non-English scenario produces incorrect TTS pronunciation.

1. **Identify the scenario language** from the scenario instructions or agent description.
2. **List personalities for the project** via `mcp__cekura__personalities_list` and filter by language.
3. **Match tone within the language-filtered list** — don't select a personality in the wrong language even if the tone matches better.
4. **For multilingual agents:** Use semantic matching for mixed-language labels — "Hinglish" matches Hindi + English personalities, "Spanglish" matches Spanish + English. If no exact dialect match exists, use the closest available option.

**Dialect precision matters** — Brazilian Portuguese and European Portuguese are distinct. When the agent description specifies a region, match it.

---

## Checking Enabled/Disabled Status

Always call `mcp__cekura__personalities_list` before assigning a personality. Available personalities vary per project — do not guess or invent names.

Rules:
- **Only assign personalities that are currently enabled for the project.**
- **Never use a personality name not returned by the API.**
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

**Safe hardcoded defaults:**
- English → ID 693 (Normal Male, en/American)
- Spanish → ID 362 (Normal Spanish Male)
- Other languages → use ID 693 + set `scenario_language` to the correct code so TTS uses the right language for pronunciation

---

## First Message vs. Personality

These are two separate fields with separate logic — don't conflate them.

| Field | Controls | Selection rule |
|---|---|---|
| `personality` | Voice characteristics (sound) | Match sustained behavior |
| `first_message` | Opening utterance (content) | See below |

**`first_message` selection:**

1. **Explicit greeting quote** — if instructions say `Say 'Hi, I need help with my bill'`, use that verbatim. Distinguish a simple greeting from a task-oriented question: "Ask for the account number" is a task, not a `first_message`.
2. **Initial silence / agent speaks first** — if instructions say the user must be silent from the very start (e.g., "wait for the agent to greet first"), set `first_message` to `""`.
3. **Default** — if neither applies, use `"Hello"`. Translate to the scenario's primary language if the entire call is in another language (e.g., `"Hola"` for Spanish).

A response or confirmation ("Yes, ...", "No, ...") that presupposes the agent has already spoken cannot be a `first_message`.

---

## Quick-Reference Decision Tree

```
Is it a conditional-actions scenario?
  Yes → Use Normal for the language (strong default)
          Need a call-wide sustained trait on top (bg noise, accent)?
            → Pick that personality; don't pick Interruptive for a single interrupt
  No ↓

What's the scenario language?
  → mcp__cekura__personalities_list → filter by language

Is there a sustained behavioral cue?
  No → Normal (fallback)
  Yes → match against personality name and description:
    Interruptive / impatient?
      Count distinct interruptions:
        2+ → Interruptive (High)
        1  → Interruptive (Low)
        General impatience → Interruptive (Medium)
    Background noise? → background noise personality
    Slow / fast speech? → speech rate personality
    Prolonged hold / silence? → Call Hold personality
    Specific accent? → language-specific accent personality

Is the matched personality ENABLED?
  Yes → use it
  No  → tell user, ask if they want to enable it,
         wait for response; always finalize with an enabled personality
```
