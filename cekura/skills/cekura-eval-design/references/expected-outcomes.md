# Expected Outcomes Reference

## What Is Expected Outcome

`expected_outcome_prompt` is a string field on each evaluator that describes what the main agent should achieve in the test. After each run, an LLM judge reads the call transcript and checks every statement against what actually happened.

Key facts:
- **Transcript-only** — the judge has no access to audio; it cannot evaluate tone, pronunciation, or speech quality
- **Requires the metric** — the `expected_outcome_prompt` field alone does nothing; you must also attach the **Expected Outcome** predefined metric to the evaluator
- **Speaker labels** — always refer to speakers as **"main agent"** and **"testing agent"**; never "user", "bot", "AI", or "assistant"

---

## Scoring Model

The judge evaluates each statement independently and assigns an alignment status:

| Alignment | Meaning |
|-----------|---------|
| `yes` | The main agent's behavior satisfies the requirement |
| `no` | The main agent violated or failed to meet the requirement |
| `blocked` | The prerequisite for this requirement never occurred in the call |

Final score:

| Outcome | Score |
|---------|-------|
| All statements `yes` | **100** — pass |
| Any statement `no` | **0** — fail |
| Any statement `blocked`, none `no` | **50** — needs review |

**When to expect "blocked":** Use sparingly. It applies when the condition that would trigger the tested behavior never arose — e.g., `"The main agent should transfer the call when the testing agent asks about prescriptions"` will be blocked if no prescription question was asked. When the testing agent ends the call before the agent can act, that is also blocked, not a failure.

**Transfer attempts count as success:** If the expected outcome requires a transfer and the agent attempted one (even if the call dropped), the judge marks it `yes`.

**Volunteered information counts:** If the testing agent volunteered information the main agent was supposed to ask for, the judge treats the requirement as met.

---

## Writing Rules

Every statement must start with **"The main agent should"**. Beyond that, these rules apply:

### 0. One statement per line
Write each statement on its own line. Separate multiple statements with a newline — do NOT concatenate them into a single paragraph separated by ". ".

✅ Correct:
```
The main agent should respond to the DTMF input 123 sent with the hash terminator.
The main agent should respond to DTMF input 45 sent without a terminator after the 2 second timeout flush.
The main agent should respond to DTMF input 7 as a single digit flushed after 2 seconds.
```

❌ Wrong:
```
The main agent should respond to the DTMF input 123 sent with the hash terminator. The main agent should respond to DTMF input 45 sent without a terminator after the 2 second timeout flush. The main agent should respond to DTMF input 7 as a single digit flushed after 2 seconds.
```

### 1. Max 2 actions per statement
Each string may describe at most two distinct actions. If a logical step has three or more sub-actions, break it into multiple sequential statements.

### 2. Semantic content only — except for fact lookups
Outcomes test functional intent, not verbatim wording. The agent paraphrasing a response is still a pass. Do not quote expected sentences.

**Exception — KB/fact lookups:** When the test is verifying that the agent retrieved and stated a specific piece of data (phone number, address, name, date), the exact value is required. Use backticks to mark the expected data point:
```
The main agent should state the office address as `123 Medical Lane, Suite 100`
```
For descriptive KB data (policies, how-to explanations), check core meaning — phrasing variation is acceptable:
```
The main agent should explain that appointments can be cancelled up to 24 hours in advance
```
Specific names and identifiers are acceptable in lookup statements because the fact itself is what's being tested.

### 3. No subjective descriptors
Ban: "appropriately", "warmly", "empathetically", "politely", "professionally", "briefly", "clearly", "naturally". Replace with functional descriptions of what the agent says or does.

### 4. Binary verifiability
Every statement must be objectively True/False from the transcript. If a reasonable reader could disagree on whether the transcript satisfies the requirement, rewrite it.

### 5. Agent-centric
Focus on what the **main agent** does — not what the caller experiences, feels, or receives. "The caller will feel helped" is not a valid outcome.

### 6. No call closing / farewells
Do not test goodbye or farewell statements unless the `extra_instructions` explicitly require testing that behavior. The last testable outcome is the agent's response to the testing agent's final substantive statement.

---

## Prioritization Hierarchy

When choosing which statements to include, follow this priority order — if you need to cut, sacrifice lower-priority items first:

1. **Core Test Goal** — the primary functional or behavioral objective of this specific test; always present
2. **Critical Prerequisites** — steps the main agent must complete to enable the core goal (e.g., collecting required data before booking); fully represent these
3. **The Hard Stop** — the main agent's final verbal action within the test's scope
4. **Other Key Functional Steps** — other mandatory actions from the agent description that fall within the test's scope

> **Behavioral tests:** If the test goal is to verify how the agent handles a specific caller behavior (e.g., unprofessionalism, confusion, hostility), at least one statement must explicitly test that behavioral reaction — e.g., `"The main agent should proceed with the next question without reacting to the testing agent's unprofessional comment."`

---

## Metric Variables in Expected Outcome

`expected_outcome_prompt` supports `{{variable_name}}` substitution — the same system used in LLM Judge metric prompts. This is useful when the expected outcome depends on test-profile data or dynamic call context.

> **Already injected automatically** — `{{transcript}}`, `{{call_end_reason}}`, and call duration are provided to the judge automatically. Do not include them in your prompt.

### Available Variables

#### System Variables (available everywhere)
| Variable | Description |
|----------|-------------|
| `{{date}}` | Current date as YYYY-MM-DD |
| `{{timestamp}}` | ISO 8601 timestamp with timezone |

#### Simulation Variables
| Variable | Description |
|----------|-------------|
| `{{test_profile.*}}` | Structured test profile data — names, DOB, phone, addresses, etc. |
| `{{metadata.*}}` | Custom key-value pairs plus system fields like `ringing_duration` |
| `{{provider_call_data.*}}` | Complete call details from VAPI, Retell, ElevenLabs, etc. |
| `{{evaluator.*}}` | Evaluator instructions and conditional action details |
| `{{agent.*}}` | Agent configuration — name, description, language code, inbound status, contact number |

Variables are **case-sensitive**. Access nested fields with dot notation: `{{test_profile.caller_name}}` or `{{metadata.customer_id}}`. Not all variables exist in every call context — handle missing values appropriately.

### Example

```
The main agent should greet the caller using the name {{test_profile.caller_name}} and ask for their date of birth to proceed with verification
```

This lets the expected outcome stay accurate across different test profiles without hardcoding identity data.

---

## Good vs Bad Examples

| Bad | Good | Why |
|-----|------|-----|
| `"The main agent should state the message: 'The best next step would be to call the facility directly.'"` | `"The main agent should advise the testing agent to contact the facility directly."` | Verbatim phrases cause false failures when the agent paraphrases |
| `"The main agent should ask for the caller's name, ask for their mother's date of birth, and state no appointment was found."` | `"The main agent should ask for the caller's name and the mother's date of birth."` + `"The main agent should state that no appointment was found for the specified date."` | 3 actions → split into 2 statements |
| `"The main agent should warmly and professionally handle the request."` | `"The main agent should proceed with the next question without reacting to the testing agent's unprofessional comment."` | Subjective descriptors ("warmly", "professionally") are not verifiable |
| `"The main agent should provide the caller with a great experience."` | `"The main agent should book the appointment and provide arrival instructions."` | Caller experience is not agent-centric or measurable |
| `"The main agent should confirm the appointment for Thursday at 2pm."` | `"The main agent should confirm the appointment date and time with the testing agent."` | Hardcoded values cause false failures across different test data |

---

## Common Pitfalls

- **Missing metric attachment** — the `expected_outcome_prompt` field alone does nothing; attach the Expected Outcome predefined metric to the evaluator
- **Including auto-injected variables** — `{{transcript}}`, `{{call_end_reason}}`, and call duration are provided automatically; adding them manually causes duplication
- **Wrong speaker labels** — always use "main agent" and "testing agent"; never "user", "assistant", "bot", or "AI"
- **Exact phrases or hardcoded values** — specifying exact dates, times, or verbatim sentences causes false failures when the agent paraphrases or uses different test data
- **Subjective descriptors** — "appropriately", "warmly", "professionally" are not verifiable; replace with functional descriptions
- **Testing call closing** — farewell statements are out of scope unless the test explicitly requires it
- **3+ actions in one statement** — split into multiple statements, each with max 2 distinct actions
