# Benchmark conventions

## Provider bar colors

Use the same color for a provider across every bar chart:

| Provider | Color |
| --- | --- |
| Retell | #3b6ea5 |
| LiveKit | #d98a45 |
| ElevenLabs | #c0685f |
| GPT Realtime | #6474ad |
| Pipecat | #9b6fa3 |
| Vapi | #4f9d8a |
| Gemini Live | #9b7b35 |

The selected agent uses #0f172a, a visible outline, and the prefix ★ SELECTED ·. Do not append “your agent” or another overflow-prone suffix.

## Interpretation

Published Bench values must be fetched from the live benchmark source at the time the report is generated, and the report must record that retrieval date. Never reuse a prior report's provider values. The selected agent's bars are directional when its scenario suite differs from Bench. Its task-completion chart should state that caveat immediately below the chart description.

## Calculation notes

- **Task completion:** fully met Expected Outcome calls ÷ expected-outcome evaluated calls.
- **Infrastructure reliability:** clean Infrastructure Issues calls ÷ evaluated calls.
- **Interruption handling:** aggregate Interruption Score (five-point scale).
- **Voice naturalness:** aggregate Voice Tone + Clarity (five-point scale).
- **Latency charts:** use individual main-agent latency observations; calculate scenario P95 from the pooled observations within that scenario, not an average of call-level P95 values.
