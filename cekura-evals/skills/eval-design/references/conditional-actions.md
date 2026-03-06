# Conditional Actions

## What They Are

Conditional actions create structured, repeatable test flows — essentially **unit tests for voice agents**. The testing agent follows a predefined sequence of conditions and actions, but adapts if the main agent deviates from the expected flow.

**When to use:** Deterministic testing, regression testing, exact flow validation, IVR navigation, compliance testing.

**When NOT to use:** Adaptive behavior testing, general quality assessment, exploratory scenarios — use behavioral instructions instead.

## Structure

A conditional actions evaluator has two top-level fields:

```json
{
  "role": "You are a patient calling to schedule an appointment",
  "conditions": [
    {
      "id": 0,
      "condition": "",
      "action": "Hi, I'd like to schedule an appointment please",
      "fixed_message": true
    },
    {
      "id": 1,
      "condition": "The agent asks for your name",
      "action": "Provide your full name for verification",
      "fixed_message": false
    },
    {
      "id": 2,
      "condition": "The agent asks for your date of birth",
      "action": "My date of birth is January 1st, 1990",
      "fixed_message": true
    }
  ]
}
```

- **role**: The testing agent's persona/context (similar to a system prompt)
- **conditions**: Ordered array of condition-action pairs

## Condition Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | integer | Yes | Unique identifier. Start at 0 for first message. |
| `condition` | string or integer | Contextual | Empty string for id:0. String trigger for standard. Integer (previous ID) for action_followup. |
| `action` | string | Yes | Instructions (fixed_message=false) or exact text (fixed_message=true) |
| `type` | string | No | `"standard"` (default) or `"action_followup"` |
| `fixed_message` | boolean | No | Default `false`. When `true`, action is spoken verbatim. |

## First Message (id: 0)

The first condition is special:
- `id` must be `0`
- `condition` must be empty string `""`
- `fixed_message` is always `true` (the opening message is spoken exactly)

```json
{
  "id": 0,
  "condition": "",
  "action": "Hi, I need to cancel my appointment for next Tuesday",
  "fixed_message": true
}
```

## fixed_message: true vs false

### fixed_message: false (default)
The `action` field provides **instructions** — the testing agent generates natural language:

```json
{
  "id": 1,
  "condition": "The agent asks for your name",
  "action": "Provide your full name",
  "fixed_message": false
}
```
Could produce: "My name is John Smith" or "It's John Smith" or "John, John Smith"

### fixed_message: true
The `action` field contains **exact text** — spoken word-for-word:

```json
{
  "id": 2,
  "condition": "The agent asks for your date of birth",
  "action": "My date of birth is January first, nineteen ninety",
  "fixed_message": true
}
```

**Use `true` for:** Compliance testing, specific keywords, reproducible flows, XML tags.
**Use `false` for:** Natural conversation variation, adaptive responses.

## Action Types

### Standard (default)
Triggers when the conversation context matches the condition string:

```json
{
  "id": 3,
  "condition": "The agent offers available time slots",
  "action": "Select the earliest available slot",
  "type": "standard"
}
```

### Action Followup
Executes immediately after a previous action, regardless of agent response. The `condition` field contains the **integer ID** of the preceding action:

```json
{
  "id": 4,
  "condition": "The agent confirms the booking",
  "action": "Thank you for the confirmation",
  "type": "standard",
  "fixed_message": true
},
{
  "id": 5,
  "type": "action_followup",
  "condition": 4,
  "action": "Also, can you send me a confirmation email?",
  "fixed_message": true
}
```

Use action_followup for multi-part responses or adding detail after a primary action.

## XML Tags

XML tags are available when `fixed_message: true`. They control voice behavior, IVR interaction, and environmental simulation.

### Communication Tags

| Tag | Purpose | Syntax |
|-----|---------|--------|
| `<ivr>` | Non-interruptible IVR message | `<ivr text="Press 1 for sales, press 2 for support" />` |
| `<voicemail>` | Voicemail greeting with beep | `<voicemail text="You've reached our office. Please leave a message after the beep." />` |
| `<endcall>` | Terminate the call | `Thank you for your help <endcall />` |

### Speech Control Tags

| Tag | Purpose | Syntax | Notes |
|-----|---------|--------|-------|
| `<silence>` | Add pauses | `Let me think <silence time="2s" />` | Time in seconds |
| `<hold>` | Wait before next message | `<hold time="5s" />` | Multiple allowed; simulates hold time |
| `<spell>` | Spell text letter-by-letter | `My name is <spell>SMITH</spell>` | Good for names, codes |
| `<speed>` | Control speech speed | `<speed ratio="1.5" />Fast talking here` | Must start the message; ratio multiplier |
| `<volume>` | Control volume | `<volume ratio="1.3" />Louder speech` | Must start message; Cartesia only |

### Interaction Tags

| Tag | Purpose | Syntax | Notes |
|-----|---------|--------|-------|
| `<dtmf>` | Send touch-tone digits | `<dtmf digits="123" /> I entered the code` | For IVR menu navigation |
| `<send_sms>` | Trigger SMS | `<send_sms text="Confirmation code: 123456" />` | Test SMS workflows |
| `<interruption>` | Interrupt after timeout | `<interruption time="3s" /> Actually, let me clarify` | Simulates caller interrupting |

### Environmental Tags

| Tag | Purpose | Syntax | Notes |
|-----|---------|--------|-------|
| `<background_noise>` | Add ambient sounds | `<background_noise sound="office" volume="0.05">I'm calling from work</background_noise>` | Wraps spoken text |
| `<noise>` | Play sound effect | `Hold on <noise sound="typing" volume="0.8" />` | One-off sound |
| `<network_simulation>` | Simulate network issues | `<network_simulation packet_loss="5" jitter="50" latency="100" />` | Test degraded connections |

## Common Patterns

### IVR Navigation

```json
{
  "conditions": [
    {
      "id": 0,
      "condition": "",
      "action": "<ivr text='Welcome to Acme Corp. Press 1 for appointments, press 2 for billing.' />",
      "fixed_message": true
    },
    {
      "id": 1,
      "condition": "IVR menu is playing",
      "action": "<dtmf digits='1' /> I pressed 1 for appointments",
      "fixed_message": true
    }
  ]
}
```

### Verification Flow (Unit Test)

```json
{
  "role": "You are an established patient calling to check appointment status",
  "conditions": [
    {
      "id": 0,
      "condition": "",
      "action": "Hi, I'd like to check on my upcoming appointment",
      "fixed_message": true
    },
    {
      "id": 1,
      "condition": "The agent asks for your name",
      "action": "My name is Sarah Johnson",
      "fixed_message": true
    },
    {
      "id": 2,
      "condition": "The agent asks for your date of birth",
      "action": "January first, nineteen ninety",
      "fixed_message": true
    },
    {
      "id": 3,
      "condition": "The agent confirms your identity and provides appointment details",
      "action": "Thank you, that's all I needed <endcall />",
      "fixed_message": true
    }
  ]
}
```

### Cancellation with Rebook Attempt

```json
{
  "role": "You are a patient who wants to cancel but might rebook",
  "conditions": [
    {
      "id": 0,
      "condition": "",
      "action": "I need to cancel my appointment for next week",
      "fixed_message": true
    },
    {
      "id": 1,
      "condition": "The agent asks for verification",
      "action": "Provide your name and date of birth for verification",
      "fixed_message": false
    },
    {
      "id": 2,
      "condition": "The agent confirms the cancellation",
      "action": "Actually, could I reschedule instead of cancelling?",
      "fixed_message": true
    },
    {
      "id": 3,
      "condition": "The agent offers rescheduling options",
      "action": "Select the next available slot with the same provider",
      "fixed_message": false
    }
  ]
}
```

### Silence and Hold Testing

```json
{
  "id": 2,
  "condition": "The agent asks a question",
  "action": "<silence time='5s' /> Sorry, I was thinking. Can you repeat that?",
  "fixed_message": true
}
```

### Spelling Names

```json
{
  "id": 1,
  "condition": "The agent asks for your last name",
  "action": "It's <spell>SZCZEPANSKI</spell>",
  "fixed_message": true
}
```

## Writing Good Conditions

**Be specific and descriptive:**
- Good: `"The agent asks for your date of birth for verification"`
- Bad: `"DOB"` or `"verification"`

**Match natural conversation flow:**
- Order conditions sequentially as the conversation would progress
- Don't skip steps the agent would normally take

**Handle branching:**
- Include conditions for both success and failure paths
- Use clear conditions that distinguish between branches

## Best Practices

- **Start simple:** Build a basic linear flow first, add complexity incrementally
- **Mix fixed and flexible:** Use `fixed_message: true` for critical data points, `false` for natural responses
- **Test provider compatibility:** `<speed>` and `<silence>` require ElevenLabs turbo or Cartesia; `<volume>` is Cartesia only
- **Use with test profiles:** Combine conditional actions with test profiles for the data, conditional actions for the flow structure
- **Keep conditions specific:** Vague conditions cause unpredictable triggering
- **Include an end condition:** Always have a condition that ends the conversation naturally
