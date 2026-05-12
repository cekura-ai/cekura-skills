# Selection by Use Case

Recommended predefined metric sets for common voice agent types. Use these as starting points — every agent should also have the universal **Baseline** set enabled (Expected Outcome, Infrastructure Issues, Tool Call Success, Latency).

Sim = enable for simulation runs. Obs = enable for observability (production calls).

---

## Booking / Scheduling Agents

Agents that schedule appointments, reservations, or callbacks. Tool calls and outcome correctness dominate.

| Metric | Sim | Obs | Why |
|--------|-----|-----|-----|
| Expected Outcome | ✓ | — | Did the booking actually get created? |
| Mock Tool Call Accuracy | ✓ | — | Right scheduling tool, right inputs |
| Tool Call Success | ✓ | ✓ | Detect broken booking integrations |
| Hallucination | ✓ | ✓ | Wrong availability, wrong policies |
| CSAT | ✓ | ✓ | End-to-end satisfaction signal |
| Sentiment | ✓ | ✓ | Frustration signal during scheduling friction |
| Latency | ✓ | ✓ | Booking flows feel slow with high P95 |
| Infrastructure Issues | ✓ | ✓ | Catches dead air after tool calls |
| Unnecessary Repetition Score | ✓ | ✓ | Common booking failure mode: re-asking for the same date |
| Appropriate Call Termination by Main Agent | ✓ | ✓ | Booking complete → did the agent close cleanly? |

---

## Collections / Outbound Agents

Agents that initiate outbound calls (collections, surveys, reminders). Voicemail handling and tone are critical.

| Metric | Sim | Obs | Why |
|--------|-----|-----|-----|
| Expected Outcome | ✓ | — | Did the agent achieve the call objective? |
| Voicemail Detection | ✓ | ✓ | Outbound calls hit voicemail constantly — must detect to leave correct message |
| Sentiment | ✓ | ✓ | Customer reaction signal — angry/disappointed users need different routing |
| Appropriate Call Termination by Main Agent | ✓ | ✓ | Did the agent end professionally? |
| Appropriate Call Termination by Testing Agent | ✓ | ✓ | Did the user hang up abruptly? Common in collections |
| CSAT | ✓ | ✓ | Quality signal even on adversarial calls |
| Tool Call Success | ✓ | ✓ | Payment / scheduling tool failures |
| Talk Ratio | — | ✓ | Healthy outbound: agent talks slightly more than user |
| Latency | ✓ | ✓ | Long pauses kill outbound conversion |

---

## Customer Support Agents

Agents handling inbound support tickets. Accuracy of information and topic classification matter most.

| Metric | Sim | Obs | Why |
|--------|-----|-----|-----|
| Hallucination | ✓ | ✓ | Wrong answer = ticket reopen — highest-impact metric |
| Relevancy | ✓ | ✓ | Off-topic / deflecting answers |
| Response Consistency | ✓ | ✓ | Contradicting earlier statements within the call |
| CSAT | ✓ | ✓ | Primary support quality KPI |
| Sentiment | ✓ | ✓ | Escalation signal |
| Topic of Call | — | ✓ | Volume distribution by issue type |
| Dropoff Node | — | ✓ | Where the conversation breaks down |
| Latency | ✓ | ✓ | Slow agents tank CSAT |
| Unnecessary Repetition Score | ✓ | ✓ | Caller frustration when forced to repeat |

---

## Healthcare / Regulated Agents

Pharmacy, clinical intake, insurance verification. Pronunciation accuracy and protocol adherence are non-negotiable.

| Metric | Sim | Obs | Why |
|--------|-----|-----|-----|
| Hallucination | ✓ | ✓ | Highest weight — wrong drug info = patient harm |
| Response Consistency | ✓ | ✓ | Contradictions in medication / dose / appointment info |
| Letterwise Pronunciation Detection | ✓ | ✓ | Confirming prescription numbers, member IDs, DOBs |
| Pronunciation Check | ✓ | ✓ | Drug names, conditions, procedure names — IPA pairs required |
| Voice Tone + Clarity | ✓ | ✓ | Audio quality directly affects comprehension |
| Appropriate Call Termination by Main Agent | ✓ | ✓ | HIPAA-aware closing protocol |
| Appropriate Call Termination by Testing Agent | ✓ | ✓ | Patient hangup mid-flow = unresolved care |
| CSAT | ✓ | ✓ | Patient experience signal |
| Tool Call Success | ✓ | ✓ | EHR / pharmacy tool integrations |
| Expected Outcome | ✓ | — | Refill placed? Prior auth started? |

---

## Voice Quality Investigation

When the user is debugging audio / voice issues rather than business outcomes. These are diagnostic, not pass/fail.

| Metric | Sim | Obs | Why |
|--------|-----|-----|-----|
| Average Pitch (in Hz) | ✓ | ✓ | Detects voice model regressions |
| Words Per Minute (WPM) | ✓ | ✓ | Pacing baseline |
| Talk Ratio | — | ✓ | Identify dominating / passive agents |
| Voice Change Detection | ✓ | ✓ | Voice model swap mid-call |
| Gibberish Detection | ✓ | ✓ | Garbled output (requires stereo audio) |
| Voice Tone + Clarity | ✓ | ✓ | Clarity / jitter scoring |
| Speaking Rate | ✓ | ✓ | Pace fluctuations (English only) |
| AI Interrupting User | ✓ | ✓ | Turn-taking issues |
| User Interrupting AI | ✓ | ✓ | Frustration signal |
| Stop Time after User Interruption (ms) | ✓ | ✓ | Responsiveness to barge-in |

---

## Universal Baseline (always add)

Every agent type above should also have these enabled. They are the lowest-cost, highest-coverage set.

| Metric | Sim | Obs | Cost |
|--------|-----|-----|------|
| Expected Outcome | ✓ | — | Free |
| Infrastructure Issues | ✓ | ✓ | Free |
| Tool Call Success | ✓ | ✓ | Free |
| Latency | ✓ | ✓ | Free |

---

## Sizing the cost

Most predefined metrics are 0.2 credits/call. A typical "rich" set of 10 paid metrics ≈ 2 credits/call. Free metrics (Expected Outcome, Infra Issues, Tool Call Success, Latency, AI/User Interruption counts, Detect Silence, Interruption Score, Repetition Score, Average Pitch, Talk Ratio, WPM) add no cost.

Two metrics are charged per minute, not per call — budget accordingly:
- **Transcription Accuracy** — Free for simulation runs; 1 credit/min when evaluating call logs (only enable when investigating ASR quality)
- **Gibberish Detection** — 0.3 credits/min (only enable when debugging audio)
