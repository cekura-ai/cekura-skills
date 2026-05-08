# Configuration Guide — Predefined Metrics

Six predefined metrics accept (or require) configuration. Pass these as key-value pairs in the metric's `configuration` object when attaching the metric to an agent or project. Metrics not listed here have no configurable options.

---

## Detect Silence in Conversation

Returns False if neither speaker speaks for longer than `silence_duration` seconds.

| Key | Type | Default | Notes |
|-----|------|---------|-------|
| `silence_duration` | int (seconds) | `10` | Threshold across BOTH speakers (mutual silence) |

**When to lower (e.g., 5s):** Short transactional flows where any pause is suspicious — quick verifications, single-purpose IVR.

**When to raise (e.g., 20s):** Calls with intentional hold periods, callback confirmations, or agent-initiated waits while tools resolve.

```json
{
  "configuration": {
    "silence_duration": 10
  }
}
```

---

## Infrastructure Issues

Returns False when the **main agent** goes silent for longer than `infra_issues_timeout` seconds. Distinct from Detect Silence — this measures only agent-side silence, isolating infra from natural pauses.

| Key | Type | Default | Notes |
|-----|------|---------|-------|
| `infra_issues_timeout` | int (seconds) | `10` | Main-agent-only silence threshold |

**Tuning:** Match this to your typical tool-call latency P95. If a database call commonly takes 7s, set this to 12–15s to avoid false positives on the slow path.

```json
{
  "configuration": {
    "infra_issues_timeout": 10
  }
}
```

---

## Dropoff Node

Identifies the conversation stage where the call ended. Observability only.

| Key | Type | Default | Notes |
|-----|------|---------|-------|
| `dropoff_nodes` | array of strings | required | Conversation stage names in flow order |

**Naming guidance:**
- Use lowercase, single words or snake_case (`greeting`, `verification`, `booking_confirm`)
- Order them as they appear in the flow — the metric uses ordering to disambiguate
- Keep the list short (5–8 stages); too many nodes blurs categorization

**Example — booking agent:**
```json
{
  "configuration": {
    "dropoff_nodes": [
      "greeting",
      "verification",
      "service_selection",
      "scheduling",
      "confirmation",
      "closing"
    ]
  }
}
```

---

## Topic of Call

Categorizes what the call was about. Observability only.

| Key | Type | Default | Notes |
|-----|------|---------|-------|
| `topic_nodes` | array of strings | required | Mutually exclusive topic categories |

**Naming guidance:**
- Use snake_case business categories (`billing`, `technical_support`, `cancellation`)
- Make categories mutually exclusive — overlapping categories produce inconsistent labels
- Include an `other` bucket only if the rest of the list is exhaustive

**Example — telecom support:**
```json
{
  "configuration": {
    "topic_nodes": [
      "billing",
      "technical_support",
      "service_change",
      "cancellation",
      "outage_report",
      "general_inquiry"
    ]
  }
}
```

---

## Letterwise Pronunciation Detection

Checks if the agent spells things out letter-by-letter when appropriate (e.g., confirming phone numbers, IDs).

| Key | Type | Default | Notes |
|-----|------|---------|-------|
| `spelling_word_types` | array of strings | required | Word categories the agent should spell |

**Common values:**
- `phone_number`
- `confirmation_code`
- `email_address`
- `account_number`
- `case_id`

The metric scans the transcript for these categories and verifies the agent spelled them character-by-character at least once during confirmation.

```json
{
  "configuration": {
    "spelling_word_types": [
      "phone_number",
      "confirmation_code",
      "email_address"
    ]
  }
}
```

---

## Pronunciation Check

Custom word accuracy — compares spoken output against a list of expected phonemes. Beta.

| Key | Type | Default | Notes |
|-----|------|---------|-------|
| `pronunciation_words` | array of objects | required | `{word, phoneme}` pairs in IPA |

**IPA tips:**
- Use the [International Phonetic Alphabet](https://en.wikipedia.org/wiki/Help:IPA) — not English spelling
- Tools like [tophonetics.com](https://tophonetics.com) can give a starting transcription
- Stress marks (`ˈ`, `ˌ`) matter for multi-syllable words

**Example — brand and drug names:**
```json
{
  "configuration": {
    "pronunciation_words": [
      {"word": "Cekura", "phoneme": "sɛˈkjʊrə"},
      {"word": "Acetaminophen", "phoneme": "əˌsiːtəˈmɪnəfɛn"},
      {"word": "Cromartie", "phoneme": "krəˈmɑːrti"}
    ]
  }
}
```

---

## Where the `configuration` field lives

When you attach a predefined metric to an agent, the configuration is part of the metric attachment payload, not the project-level toggle. Project-level toggles only enable/disable the metric; per-evaluator (or per-agent) attachment is where configuration is applied.

See `api-reference.md` for the full attach-with-config request shape.
