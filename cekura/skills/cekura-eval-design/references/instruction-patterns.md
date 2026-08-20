# Behavioral Instruction Patterns

Detailed guidance on what good behavioral instruction text (`scenario_type: "instruction"`) looks like. Loaded on demand from `SKILL.md`'s "Writing Instructions" section.

**Behavioral scenarios are generated, not hand-authored** (`generate-bg` — the create endpoint is for conditional actions). Use these patterns to write the `extra_instructions` you pass to the generator, to judge and PATCH what it returns, and for the verbatim exception where the user supplied the text.

## Instruction Style

- **First person**: "State your name when asked" — not "The caller should state their name"
- **Behavioral, not scripted**: "Report fever and cough, request same provider" — not "Say exactly: I have a fever"
- **Reference test profile data**: "Provide {{test_profile.date_of_birth}} when asked for verification" — the actual DOB comes from the test profile

## Step-Writing Rules

Each numbered step in the scenario body must follow these rules. They are what separates a scenario that runs deterministically from one that stalls, drifts, or produces coin-flip results.

### Trigger rule — every step needs a "when [situation]" trigger

No unconditional actions. Every step pairs one caller action with the situation that triggers it, in **passive voice**: "when asked for X", "when offered Y", "when prompted for Z".

Never use the words "agent", "AI", "bot", "system", "IVR", "caller", or "customer" anywhere in a step, including the trigger — describe **what the step asks about, not who asks it**.

- ✅ `State the reason for calling when asked for the reason of the call.`
- ✅ `Agree to receive a confirmation link when offered to send one.`
- ❌ `Open with a request to reschedule.` (no trigger)
- ❌ `State the reason when the agent asks for the reason.` (uses "agent")
- ❌ `Constantly push back throughout the call.` (unschedulable — no discrete trigger)

**Trigger precision:** the trigger must identify the EXACT question or offer, not narrative context.
- ❌ `State your preference when asked about general options.`
- ✅ `State your preference for a morning slot when asked for a preferred appointment time.`
- ❌ `Confirm your name when asked.` (bare "when asked" — asked what?)

**Opening step:** derive the first trigger from the agent description — mirror the first caller-observable question or statement the main agent is prompted to open with. Do not assume a default opening question. If the main agent is reactive and the caller must lead, put the first proactive request in `first_message`, not in a step, and key subsequent triggers off the responses to each previous step ("when told the requested information") — never off the caller's own state ("when ready to proceed"), which stalls the conversation.

### One action per step

Never join two independent actions in a single step ("do X and Y when …") — the testing agent reliably performs only the first and silently drops the second. Two similar-but-distinct moments (state a preference, later confirm it) are TWO steps with different, specific triggers.

Sole exception — the **volunteer pattern**: "when asked <guaranteed question>, answer and also mention Z" is one conversational turn and is allowed. Use it for facts the caller must volunteer that the agent will never ask about; anchor it to a question the flow guarantees.

### No passive or non-verbal actions

Never use "Wait", "Listen", "Remain silent", "Stay silent", "Mumble", "Interrupt", "Pause", or "Acknowledge" in any step. Non-verbal behaviors — silence, interruption, background noise, speaking style — are **personality attributes**, not steps. Do not create steps for passively receiving information (hearing a wait time, hearing a goodbye). Hanging up IS allowed as a step.

Dropping the step is not the whole fix. If the user actually needs the testing agent to stay quiet, the silence is bounded by the personality's idle timeout (default 10s), after which it prompts "Are you still there?" regardless of what the instructions say. For a bounded pause in one step of a conditional-actions scenario use `<hold time="Xs" />`, which pauses the idle timer for its duration; for open-ended silence, or a behavioral scenario with no `conditions[]` to hang a tag on, raise `message_plan.idle_timeout_seconds` on a personality they own — see `references/choosing-personality.md`.

Never script intra-utterance timing ("interrupt before the disclaimer finishes") — sub-utterance timing is not schedulable; every trigger anchors to a completed turn. Want interruptions? Pick an interruptive personality.

### Action closure — every graded behavior needs a causing step

The testing agent does ONLY what the steps say. Every behavior the expected outcome will check must be caused by an explicit caller step with a precise trigger, or the outcome is a coin flip.

- ❌ `Ask for help with the issue.` → ✅ `Accept the offered handoff when asked if you want additional help.`
- ❌ `Show confusion about the process.` → ✅ `Ask the same clarification question again when asked if the explanation is clear.`
- ❌ `Express interest in the option.` → ✅ `Choose {{test_profile.selected_option}} when asked which option you prefer.`

### Verify format — data read-backs

When the main agent reads back personal data and asks to confirm, use exactly: **"Verify [item] when asked to confirm [item] and correct if wrong."** The phrase "and correct if wrong" is required. This applies to personal-data read-backs only, not to accepting offers.

- ❌ `Confirm your details when asked.`
- ✅ `Verify the name is correct when asked to confirm the name and correct if wrong.`

### Mandatory final step — end the call

Every scenario's LAST step must be `End the call when <specific passive condition>.` — the only allowed call-management step. Two exceptions: the user explicitly asked not to end the call, or the scenario ends in a terminal transfer (then the final step is accepting/requesting the transfer — never add a competing end-call step).

- The end-call trigger must name the RESULT of the last scripted action, never a generic close ("when the closing statement is given") that could fire early.
- The final substantive action must PRECEDE the end-call step — never an end-call trigger that still requires a caller action.
- No extra acknowledgment/goodbye/wrap-up steps before it (scope rule).

### Stop at the fork — script only deterministic ground

Only script steps whose triggers the agent description guarantees will occur:

- **"When asked about X" is valid only if the agent is actually prompted to ask about X.** Facts the caller must volunteer get a volunteer-pattern step — never "when asked about X".
- **When the description doesn't mandate the main agent's reaction to a scripted state, end the scenario there** ("End the call when <the last deterministic event>"). Never script arcs that depend on improvised continuations or assumed retries. A short deterministic scenario beats a long speculative one.
- **Never premise a step or scenario on non-controllable state**: call/channel properties, backend results no mock fixes, or the main agent's own misbehavior (a correctly behaving agent never produces that trigger — test forbidden behavior via expected outcomes demanding its ABSENCE instead). States the scenario itself fixes (a dynamic variable it sets, a mock tool output it supplies with a triggering step) ARE controllable.
- **Wrong-value friction** is testable only when the main agent holds the stored ground truth (via dynamic variable or mock output); otherwise script only detectable errors (format or internal-consistency violations).
- **Relational values** (a pickup time relative to an appointment time): an earlier step must script the anchor value as its own `{{test_profile.<anchor>}}` field so the relation always holds.

### Placeholders — all caller-provided data, including choices

Never hardcode personal data in steps. Use `{{test_profile.field}}` for anything the caller provides:

- ❌ `Provide 'John Smith' when asked for name.` → ✅ `Provide {{test_profile.name}} when asked for name.`
- ❌ `State 'March 15, 1990' when asked for date of birth.` → ✅ `State {{test_profile.date_of_birth}} when asked for date of birth.`

**The most-missed case — caller choices and confirmations.** Values the caller selects, agrees to, or confirms (a plan, a tier, a delivery method, an option the agent proposed) are still caller data:

- ❌ `Select express shipping when asked for a delivery speed.` → ✅ `Select {{test_profile.delivery_speed}} when asked for a delivery speed.`
- ❌ `State you prefer the premium tier when asked.` → ✅ `Choose {{test_profile.preferred_tier}} when asked which tier you prefer.`

**Every mention:** use the same placeholder every time the attribute appears — never placeholder once and the bare word elsewhere. Copy the identical token into any expected-outcome line that references the value.

**Don't fabricate placeholders:** a placeholder is justified only for configured dynamic variables, mock-tool input keys, or fields already in the test profile. One-shot topics, agenda items, and labels go inline ("Ask about the cancellation policy when offered help") — not as invented `{{test_profile.*}}` fields.

**Placeholder closure:** every `{{test_profile.X}}` used in steps or outcomes must exist with a concrete value in the attached test profile — an unresolved placeholder resolves to nothing at call time.

**Intentional wrong values:** when a step deliberately provides a wrong value (validation-failure test), the wrong value may stay hardcoded; only the final correct value uses the placeholder.

### Personality, not steps, for sustained behavior

Only SUSTAINED, call-wide behaviors map to personality (interruptive, background noise, accent, speed). A temporary state at one step ("gets frustrated at step 4") stays in the steps with a Normal personality. Pick language FIRST, then tone — the wrong language personality produces incorrect TTS pronunciation.

## Good Instructions Pattern

Wrap instructions in `<scenario>` tags with a step-by-step format:

```
<scenario>
SCENARIO: [Brief scenario name]

YOUR BEHAVIOR:
1. State your intent to [action] when asked for the reason of the call
2. Confirm you are the patient when asked if you are the patient
3. Say and spell {{test_profile.first_name}} when asked for your name for verification
4. Provide {{test_profile.date_of_birth}} when asked for your date of birth
5. Say you are flexible with timing when told no slots are available
6. End the call when the appointment confirmation is provided

KEY INTERACTION POINTS:
[Specific workflow nodes or edge cases to exercise]
</scenario>
```

**Be explicit about exact phrases** when mock/backend behavior depends on them (e.g., `say "follow-up appointment" exactly` if the mock's reason-for-visit matching requires it).

## Common Instruction Mistakes

- **Filler steps that add nothing** — NEVER write steps like "Listen to the agent's response", "Wait for the agent to speak", "End the call politely", or "Respond accordingly". The testing agent already does these things automatically. Every step must describe a **specific action the caller takes** — information they provide, a decision they make, or a behavior they exhibit. If a step doesn't tell the caller to DO something specific, delete it.
- **Hardcoding profile data in instructions** — Names, DOBs, addresses, account numbers belong in test profiles, not instructions. When data is in both places and they differ, the testing agent hallucinates. This is the single most common mistake across clients.
- **Using instructions for voice characteristics** — Instructions like "speak in a mumbling voice" or "be interruptive" don't change the testing agent's vocal style. Use **personalities** for that — they control actual voice model parameters (accent, interruption level, background noise, speed).
- **Including examples of what the main agent "may say"** — Don't write `When the agent says "How can I help you", respond with...`. Instead, reference action points by topic: `When asked about what you need help with, explain that you need help with your billing address.` The former is brittle; the latter works regardless of exact agent phrasing.
- **Not providing enough context for multi-step flows** — If a scenario involves a complex process (scheduling, onboarding), the testing agent needs step-by-step context to avoid hallucinating after the first few steps. For structured flows, use conditional actions instead.
- **Vague or generic instructions** — "Call to schedule an appointment" is useless. Be specific: what type of appointment, what constraints, what complications should arise. The more specific the scenario, the more useful the test.
- Third-person perspective instead of first person
- Too scripted (exact dialogue) instead of behavioral goals
- Missing edge case triggers

## Bad vs Good Instructions

### Example 1 — Wrong-number scenario

**BAD** (filler, vague, passive):

```
<scenario>
1. When the agent asks to confirm your identity and whether you are the intended person, clearly state: "No, you have the wrong number."
2. Listen to the agent's response.
3. End the call politely.
</scenario>
```

**GOOD** (every step is a specific caller action):

```
<scenario>
SCENARIO: Wrong number — caller is not the intended recipient

YOUR BEHAVIOR:
1. Say this is the wrong number and you don't know the person being looked for when asked for your name or asked to verify your identity
2. Decline when asked for any additional information — you have no connection to the intended person
3. Confirm that's fine when offered to have your number removed
4. End the call when the number-removal confirmation is given
</scenario>
```

### Example 2 — New patient scheduling

**BAD** (generic, no specifics):

```
<scenario>
1. Call to schedule an appointment.
2. Provide your information when asked.
3. Confirm the appointment.
</scenario>
```

**GOOD** (specific scenario with constraints):

```
<scenario>
SCENARIO: New adult patient scheduling with insurance

YOUR BEHAVIOR:
1. State you're a new patient and need to schedule a first visit with a primary care provider when asked for the reason of the call
2. Say you have {{test_profile.insurance_plan}} when asked about insurance
3. Provide {{test_profile.date_of_birth}} when asked for your date of birth
4. Spell {{test_profile.full_name}} when asked for your name for verification
5. Request a morning appointment when asked for a preferred time
6. Accept the earliest available afternoon slot when told no morning slots are available
7. Verify the appointment details are correct when asked to confirm the appointment details and correct if wrong
8. End the call when the booking confirmation is provided

KEY INTERACTION POINTS:
- New patient registration flow
- Insurance verification
- Appointment slot selection with preference constraints
</scenario>
```
