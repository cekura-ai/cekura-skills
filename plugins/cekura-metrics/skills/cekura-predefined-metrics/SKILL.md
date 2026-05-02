---
name: cekura-predefined-metrics
description: >
  Use when the user asks "what predefined metrics are available", "which built-in metrics should I use",
  "what does CSAT measure", "how does hallucination detection work", "what's the difference between
  Interruption Score and AI Interrupting User", "which metrics are free", "which metrics need audio",
  "configure silence threshold", "set up sentiment metric", or any question about Cekura's out-of-the-box
  metrics. Covers the full catalog of predefined metrics — what each does, costs, constraints,
  configuration options, and when to use each one.
license: MIT
compatibility: Requires a Cekura account (https://dashboard.cekura.ai) — sign in via OAuth or use an API key.
metadata:
  author: cekura
  version: "0.1.0"
---

# Cekura Predefined Metrics

## Purpose

Predefined metrics are Cekura's built-in evaluators — ready to enable on any agent with no prompt writing required. They cover the most common quality dimensions across accuracy, conversation quality, customer experience, and speech quality. Use this skill to decide which predefined metrics to enable and how to configure them.

## Performing Platform Actions

When this skill suggests creating, listing, updating, or evaluating something on Cekura, **prefer using available platform tools over describing API calls or dashboard steps**. In Claude Code with the Cekura plugin installed, these tools are auto-configured and handle authentication, parameter validation, and error handling for you. Fall back to direct API endpoints or dashboard guidance only when no tools are available in the current session.

## Predefined vs Custom Metrics

Enable predefined metrics first. They require zero prompt engineering and cover the most common quality dimensions out of the box. Only reach for a custom metric when:
- You need to evaluate a business-specific workflow (booking flow, escalation protocol, etc.)
- You need to check agent behavior against your specific system prompt
- You need to combine multiple signals into one score

For everything else, a predefined metric will give you reliable, consistent results faster.

## Enabling Predefined Metrics

Two steps are required — missing either means the metric never fires:

1. **Toggle on at the project level** — enables the metric for simulation runs
2. **Add to individual evaluators** — attaches the metric to specific test scenarios

Use `GET /test_framework/v1/predefined-metrics/` to retrieve the full list of available predefined metrics and their IDs. Pass a predefined metric's `code` field when adding it to an agent's metric set.

---

## Catalog: Accuracy

| Metric | Output | Cost | Sim | Obs | Notes |
|--------|--------|------|-----|-----|-------|
| **Expected Outcome** | 0–100 score | Free | ✓ | — | Requires `expected_outcome_prompt` set on the evaluator. Scores how well the agent achieved the scenario goal. Without this, runs only pass/fail on call completion. |
| **Hallucination** | True/False | 0.2 credits | ✓ | ✓ | Compares agent responses against the Knowledge Base to detect unsupported claims. |
| **Mock Tool Call Accuracy** | 0–100 score | Free | ✓ | — | Scores whether the right mock tools were called with the right inputs. Requires mock tools configured on the agent. |
| **Relevancy** | True/False | 0.2 credits | ✓ | ✓ | Checks if agent responses addressed the question asked. Flags off-topic or deflecting replies. |
| **Response Consistency** | True/False | 0.2 credits | ✓ | ✓ | Detects contradictions — when the agent repeats information incorrectly or contradicts a prior statement. |
| **Tool Call Success** | True/False | Free | ✓ | ✓ | Checks if any tool call result contains "Error" or "failed". Requires provider integration (assistant ID + API keys) so tool call data appears in the transcript. |
| **Transcription Accuracy** | 0–100 score | 1 credit/min | ✓ | — | Uses two transcription models for call logs, compares against ground truth for runs. **Requires audio.** Expensive — use selectively. |
| **Voicemail Detection** | True/False | 0.2 credits | ✓ | ✓ | Detects if the call reached a voicemail or automated system. Beta. |

---

## Catalog: Conversation Quality

| Metric | Output | Cost | Sim | Obs | Notes |
|--------|--------|------|-----|-----|-------|
| **AI Interrupting User** | Count | Free | ✓ | ✓ | Counts how often the agent interrupted the user. For observability, requires stereo audio with separate speaker channels. |
| **Appropriate Call Termination by Main Agent** | True/False | 0.2 credits | ✓ | ✓ | Checks whether the agent ended the call prematurely and whether the user's concern was resolved. |
| **Appropriate Call Termination by Testing Agent** | True/False | 0.2 credits | ✓ | ✓ | Checks if the user (testing agent) ended the call abruptly — a signal of poor experience or unresolved issues. |
| **Detect Silence in Conversation** | True/False | Free | ✓ | ✓ | Returns False if neither speaker speaks for longer than `silence_duration` seconds. Default: 10s. Configurable. |
| **Infrastructure Issues** | True/False | Free | ✓ | ✓ | Returns False when the main agent goes silent for longer than `infra_issues_timeout` seconds. Default: 10s. Configurable. Distinct from Detect Silence — this is agent-specific. |
| **Interruption Score** | 0–100 score | Free | ✓ | ✓ | Continuous score for how often the agent interrupts the user. Higher = fewer interruptions = better. |
| **Latency (in ms)** | ms average | Free | ✓ | ✓ | Average response latency. Also reports P25/P50/P75/P90/P95/P99 percentiles. Under 2000ms is considered good. |
| **Stop Time after User Interruption (ms)** | ms | Free | ✓ | ✓ | Time from user interruption until the agent stops speaking. Lower = more responsive. |
| **Unnecessary Repetition Count** | Count | 0.2 credits | ✓ | ✓ | Counts how many times the agent unnecessarily repeated itself. |
| **Unnecessary Repetition Score** | 0–100 score | Free | ✓ | ✓ | Continuous score for repetition quality. Higher = more concise = better. Prefer this over the count metric for trend tracking. |
| **User Interrupting AI** | Count | Free | ✓ | ✓ | Counts customer interruptions of the agent. High counts signal frustration or poor turn-taking. |

---

## Catalog: Customer Experience

| Metric | Output | Cost | Sim | Obs | Notes |
|--------|--------|------|-----|-----|-------|
| **CSAT** | 0–100 score | 0.2 credits | ✓ | ✓ | Overall customer satisfaction. Scores above 70 indicate satisfaction. Evaluates tone, cooperation, and resolution. |
| **Dropoff Node** | Enum | 0.2 credits | — | ✓ | Identifies the conversation stage where the call ended. **Requires `dropoff_nodes` configuration** with predefined stage names. Observability only. |
| **Sentiment** | Enum | 0.2 credits | ✓ | ✓ | Classifies user sentiment as Happy, Angry, Neutral, or Disappointed based on tone and word choice across the call. |
| **Topic of Call** | Enum | 0.2 credits | — | ✓ | Categorizes what the call was about (e.g., billing, technical support). **Requires `topic_nodes` configuration**. Observability only. |

---

## Catalog: Speech Quality

| Metric | Output | Cost | Sim | Obs | Notes |
|--------|--------|------|-----|-----|-------|
| **Average Pitch (in Hz)** | Hz | Free | ✓ | ✓ | Average vocal pitch of the main agent during the call. Useful for monitoring voice consistency. |
| **Gibberish Detection** | True/False | 0.3 credits/min | ✓ | ✓ | Detects garbled or incoherent speech. **Requires stereo audio.** Beta. |
| **Letterwise Pronunciation Detection** | True/False | 0.2 credits | ✓ | ✓ | Checks if the agent spells things out letter-by-letter when appropriate (e.g., confirming phone numbers). **Requires `spelling_word_types` configuration.** |
| **Pronunciation Check** | 0–100 score | 0.2 credits | ✓ | ✓ | Custom word accuracy — compares spoken output against a list of expected phonemes. **Requires `pronunciation_words` configuration** as phoneme pairs. Beta. |
| **Speaking Rate** | True/False | 0.2 credits | ✓ | ✓ | Detects abrupt changes in the agent's speaking pace. English only. Beta. |
| **Talk Ratio** | 0.0–1.0 | Free | ✓ | ✓ | Ratio of agent speaking time vs user speaking time. Typical healthy range: 0.4–0.6. Requires stereo audio for observability. |
| **Voice Change Detection** | True/False | 0.2 credits | ✓ | ✓ | Detects if the agent's voice changes unexpectedly (different speaker, voice model issue). Beta. |
| **Voice Tone + Clarity** | 0–100 score | 0.2 credits | ✓ | ✓ | Audio quality score — analyzes clarity and jitter. Scores above 70 indicate quality. |
| **Words Per Minute (WPM)** | WPM | Free | ✓ | ✓ | Speaking speed of the main agent. Useful baseline alongside Average Pitch and Talk Ratio. |

---

## Configuration Reference

Some predefined metrics require or support configuration. Pass these as key-value pairs in the metric's `configuration` object.

| Metric | Config Key | Type | Default | Description |
|--------|------------|------|---------|-------------|
| Detect Silence in Conversation | `silence_duration` | int (seconds) | 10 | Silence threshold for either speaker |
| Infrastructure Issues | `infra_issues_timeout` | int (seconds) | 10 | Silence threshold for the main agent only |
| Dropoff Node | `dropoff_nodes` | array of strings | required | Conversation stage names (e.g., `["greeting", "verification", "booking", "closing"]`) |
| Topic of Call | `topic_nodes` | array of strings | required | Topic categories (e.g., `["billing", "technical_support", "cancellation"]`) |
| Letterwise Pronunciation | `spelling_word_types` | array of strings | required | Word categories to check (e.g., `["phone_number", "confirmation_code"]`) |
| Pronunciation Check | `pronunciation_words` | array of objects | required | Phoneme pairs: `[{"word": "Cekura", "phoneme": "sɛˈkjʊrə"}]` |

---

## Cost & Credits Quick Reference

| Cost | Metrics |
|------|---------|
| **Free (0 credits)** | Expected Outcome, Tool Call Success, Mock Tool Call Accuracy, AI Interrupting User, User Interrupting AI, Stop Time after User Interruption, Latency, Detect Silence, Infrastructure Issues, Interruption Score, Unnecessary Repetition Score, Average Pitch, Talk Ratio, Words Per Minute |
| **0.2 credits/call** | Hallucination, Relevancy, Response Consistency, Voicemail Detection, Appropriate Call Termination (both), Unnecessary Repetition Count, CSAT, Dropoff Node, Sentiment, Topic of Call, Letterwise Pronunciation, Pronunciation Check, Speaking Rate, Voice Change Detection, Voice Tone + Clarity |
| **0.3 credits/min** | Gibberish Detection |
| **1 credit/min** | Transcription Accuracy |

---

## Baseline — Always Enable

At minimum, every agent should have these four enabled for simulation (and the last three also for observability):

| Metric | Why |
|--------|-----|
| **Expected Outcome** | Without this, runs only tell you if the call completed — not if the agent actually did the right thing |
| **Infrastructure Issues** | Catches the agent going silent for 10+ seconds — invisible in pass/fail |
| **Tool Call Success** | Detects broken integrations before they impact real users |
| **Latency** | Baseline performance tracking; P95/P99 reveal outliers that averages hide |

For a richer baseline, also add: **CSAT**, **Sentiment**, and **Unnecessary Repetition Score**.

---

## Key Constraints

- **Audio required:** Transcription Accuracy and Gibberish Detection need audio data. Not available for text-only runs.
- **Stereo required (observability):** AI Interrupting User, User Interrupting AI, Talk Ratio, and Gibberish Detection require stereo recordings with separate speaker channels for observability calls.
- **Simulation only:** Transcription Accuracy, Mock Tool Call Accuracy, Expected Outcome.
- **Observability only:** Dropoff Node, Topic of Call.
- **English only:** Speaking Rate.
- **Requires configuration:** Dropoff Node, Topic of Call, Letterwise Pronunciation Detection, Pronunciation Check — will not produce meaningful results without the configuration keys set.
- **Requires provider integration:** Tool Call Success requires the agent's provider assistant ID configured on Cekura so tool call data appears in transcripts.

---

## Common Pitfalls

- Enabling metrics without completing both activation steps (project toggle AND evaluator assignment) — metrics appear available but never fire
- Using Detect Silence and Infrastructure Issues interchangeably — they measure different things (both speakers vs agent only)
- Expecting Transcription Accuracy on observability calls — it's simulation-only
- Forgetting `expected_outcome_prompt` when using Expected Outcome — without it the metric has nothing to evaluate against
- Enabling Dropoff Node or Topic of Call without configuring `dropoff_nodes`/`topic_nodes` — results will be meaningless
- Using Gibberish Detection on mono recordings — it requires stereo audio

---

## Next Steps

After selecting predefined metrics, the user typically needs:
- **Create or configure metrics** → invoke **cekura-metric-design** for custom metrics to complement predefined ones
- **Improve a metric that's underperforming** → invoke **cekura-metric-improvement** for the feedback and labs cycle
- **Attach metrics to test scenarios** → invoke **cekura-eval-design** to wire up metrics in evaluators

## Documentation

- Pre-defined metrics reference: https://docs.cekura.ai/documentation/key-concepts/metrics/pre-defined-metrics
- Public docs: https://docs.cekura.ai
- Concepts: https://docs.cekura.ai/documentation/key-concepts/
