# Behavioral Instruction Patterns

Detailed guidance for authoring behavioral evaluators (`scenario_type: "instruction"`). Loaded on demand from `SKILL.md`'s "Writing Instructions" section.

## Instruction Style

- **First person**: "State your name when asked" — not "The caller should state their name"
- **Behavioral, not scripted**: "Report fever and cough, request same provider" — not "Say exactly: I have a fever"
- **Reference test profile data**: "Provide your date of birth when asked for verification" — the actual DOB comes from the test profile

## Good Instructions Pattern

Wrap instructions in `<scenario>` tags with a step-by-step format:

```
<scenario>
SCENARIO: [Brief scenario name]

YOUR BEHAVIOR:
1. State your intent to [action]
2. Confirm you are the patient when asked
3. Say and spell your first name when asked for verification
4. Provide your date of birth when asked
5. If the agent says no slots are available, say you are flexible with timing

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
1. When the agent asks for your name or tries to verify your identity, say this is the wrong number and you don't know the person they're looking for
2. If the agent asks for any additional information, decline — you have no connection to the intended person
3. If the agent apologizes and offers to remove your number, confirm that's fine
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
1. State you're a new patient and need to schedule a first visit with a primary care provider
2. When asked about insurance, say you have Blue Cross PPO
3. Provide your date of birth and spell your full name when asked for verification
4. Request a morning appointment if given timing options
5. If no morning slots are available, accept the earliest available afternoon slot
6. Confirm the appointment details when the agent reads them back

KEY INTERACTION POINTS:
- New patient registration flow
- Insurance verification
- Appointment slot selection with preference constraints
</scenario>
```
