# Test Coverage Patterns

## Coverage Strategy

A comprehensive eval suite covers all major workflows, their edge cases, and adversarial scenarios. This reference shows real-world coverage patterns from deployed agents.

## Example: Medical Clinic Agent (BCHS/Kouper — 54 evaluators)

### Category Breakdown

| Category | Code | Count | Description |
|----------|------|-------|-------------|
| Scheduling | S | 10 | New/established patients, adult/pediatric, insurance/no-insurance, sliding scale |
| Rescheduling | RS | 6 | Same/different provider, no appointments, multiple appointments, tool failures |
| Cancellation | CN | 6 | Cancel + decline reschedule, cancel + rebook, no appointments, tool errors |
| Verification | V | 7 | Spouse/authorized rep, name spelling corrections, patient not found retries |
| Intake | I | 3 | Ambiguous visit reason, billing concerns, multiple insurance plans |
| Scheduling Edge Cases | SC | 4 | No slots, confirmation rejected, tool failures |
| Overall Flow | OF | 4 | FAQ-only, behavioral health transfer, billing transfer, human request |
| Safety | SA | 9 | Chest pain, emergency symptoms, suicidal ideation, symptom triage |
| Error | ER | 4 | Angry caller, deceased patient, clinical question, silent tool failure |
| Spanish | SP | 1 | Full scheduling call in Spanish |

### Priority Distribution

- **Must-have**: 39 evaluators (72%) — core workflows that must work correctly
- **Nice-to-have**: 15 evaluators (28%) — edge cases and enhancements

### Coverage Principles from BCHS

1. **Every workflow gets a happy path**: S-01 through S-10 cover all scheduling variants
2. **Every workflow gets error paths**: RS-06 (tool fails 3+ times), CN-05 (cancel tool error)
3. **Verification gets its own category**: Identity verification is critical for medical — 7 dedicated scenarios
4. **Safety is heavily covered**: 9 scenarios for medical emergency handling (highest consequence of failure)
5. **Cross-workflow scenarios exist**: CN-02 tests cancel → immediately rebook (two workflows in one call)

## Example: Staffing Platform Agent (Traba — 3 metrics, implicit eval patterns)

### Coverage Areas

| Area | What to Test |
|------|-------------|
| Interview Flow | Pay expectations, commute, availability, work experience questions |
| Tool Performance | evaluate_transcript_prod timing, tool chain stalls |
| Onboarding | App installation guidance, silence persistence, step-by-step navigation |
| Escalation | Get Help redirect when user is stuck |
| Multi-agent Transfer | Handoff between interview → evaluation → onboarding agents |

### Key Insight: Traba has fewer evals but more metrics

Traba's testing strategy relies more on metrics (measuring call quality on real production calls) than on simulated evals. This is appropriate for outbound calls where the agent initiates — you can't easily simulate the full multi-agent flow. Instead, real calls are evaluated by metrics.

## Building a Coverage Matrix

For any new agent, build coverage by:

1. **List all workflows** from the agent description (booking, cancellation, transfer, etc.)
2. **For each workflow, identify**:
   - Happy path (standard successful completion)
   - User variations (new vs existing, adult vs pediatric, etc.)
   - Error paths (tool failures, retries exhausted)
   - Edge cases (multiple items, confirmation rejection, user changes mind)
3. **Add cross-cutting concerns**:
   - Verification / authorization
   - Safety / emergency handling
   - Language support
   - Adversarial / red team scenarios
4. **Prioritize**: Must-have = workflows that handle real money, safety, or core business logic

## Naming Convention

Use consistent ID + name format for easy tracking:

```
{CATEGORY_CODE}-{NUMBER}: {Brief Description}
```

Examples:
- `S-01: New adult patient with insurance`
- `RS-03: No future appointments nothing to reschedule`
- `SA-07: Suicidal ideation immediate transfer`

Keep names under 80 chars (API limit on the `name` field).

## Eval Types

A complete suite has coverage across these categories. Each type can be authored as **behavioral** (free-form instructions) or **conditional actions** (structured `{role, conditions[]}`) — see "Choosing Authoring Mode" in `SKILL.md` for the decision rule.

### Workflow Evals (Core)

Happy path for each major workflow the agent supports — appointment booking, account lookup, password reset, etc. Cover every primary action the agent is supposed to perform end-to-end.

### Deterministic / Unit Test Evals

Conditional-actions evaluators for repeatable, structured testing of specific flows. Use when you need byte-identical behavior every run (regression, compliance verbatim, IVR navigation, DTMF entry).

### Edge Case Evals

Tool failures, multiple matching records, confirmation rejection, retry exhaustion, ambiguous user input. Each edge case is a separate evaluator with its own expected outcome.

### Red Team Evals

Prompt injection, social engineering, information extraction, off-topic manipulation, jailbreak attempts. Specific scripted attacks belong in conditional-actions evaluators (one evaluator per expected outcome — refusal vs compliance). Free-form probing stays behavioral.

### Error Handling Evals

Angry caller, deceased patient, clinical questions, silent tool failures, hostile callers. Tone-driven scenarios are usually behavioral; specific de-escalation flows can be conditional actions.

### Multi-Language Evals

Coverage across every language the agent supports. Set `scenario_language` and pair with a personality that matches. Behavioral covers tone/quality testing; conditional actions cover compliance-verbatim phrasing in the target language.

## Execution Modes

| Mode | Speed | Cost | Best For |
|------|-------|------|----------|
| **Voice** | Slow | High | Final validation, voice-specific testing (latency, interruptions, TTS quality) |
| **Text/Chat** | Fast | Low | Logic testing, rapid iteration, flow validation without voice overhead |
| **WebSocket** | Medium | Medium | Real-time agents, agents using WebSocket-based providers |
| **Pipecat** | Medium | Medium | Pipecat framework agents |

**Practical guidance:** Use text/chat for development iteration (fast, cheap, tests logic). Switch to voice for final validation before deployment. WebSocket for agents built on WebSocket providers.

**Test profiles in chat/websocket:** Test profile data is passed to the main agent in chat and websocket runs, enabling tool verification without voice calls.

## Create Evaluator from Transcript

Cekura can create an evaluator directly from a real call transcript. Useful when:
- A production call demonstrates an important scenario
- You want to reproduce a specific customer interaction as a repeatable test
- You're building regression tests from real-world edge cases

**Endpoint:** `POST /test_framework/v1/scenarios/create_scenario_from_transcript/`

**How it works:** Pass an observability call log ID. The endpoint analyzes the transcript, extracts the caller's behavior, and creates an evaluator that replays a similar conversation. The generated scenario captures the caller's intent, actions, and conversational flow — not an exact script replay.

**When to use:** After reviewing production calls in observability, identify calls that represent important test scenarios (edge cases, failures, complex workflows) and convert them directly into evaluators. This is faster and more accurate than manually writing instructions to reproduce the scenario.

**Post-creation:** Always review the generated evaluator — the auto-extraction may need refinement. Attach metrics, assign a test profile if identity data is involved, set the folder path, and enable tools.

