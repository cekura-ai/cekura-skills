# Phase 10 — Advanced Configuration

Optional settings that improve test quality, observability, and outbound behavior. Ask the user which of these apply to their agent.

---

## 10a. LLM simulation model

Controls which model simulates the caller during text/chat evaluations:

```json
{
  "llm_model": "gpt-4o",
  "llm_temperature": 0.0,
  "llm_max_tokens": 4096,
  "llm_system_prompt": "<optional: custom caller persona prompt>"
}
```

Options: `gpt-4o`, `gpt-4o-mini`, `gpt-4.1`, `gpt-4.1-mini`, `claude-sonnet-4-5`

Default temperature `0.0` gives consistent, reproducible tests. Raise it only if you want varied caller behavior across runs.

---

## 10b. Topic classification

Tell Cekura what topics the agent handles so call routing and topic-based metrics work correctly:

```json
{
  "topic_nodes": {"billing": "handle_billing", "scheduling": "book_appointment"},
  "auto_update_topic_nodes": true
}
```

`auto_update_topic_nodes: true` infers topic nodes from the agent description automatically — recommended as a starting point.

---

## 10c. Dropoff detection

Track where callers disengage or abandon the flow:

```json
{
  "dropoff_nodes": {"timeout": 30, "no_response": 15},
  "auto_update_dropoff_nodes": true
}
```

---

## 10d. Pronunciation and spelling analysis

For agents that read out words, spell names, or verify postcodes/emails:

```json
{
  "pronunciation_words": [["VAPI", "VAY-pee"], ["Cekura", "SEH-kyoo-rah"]],
  "spelling_word_types": ["name", "postcode", "email"]
}
```

---

## 10e. Outbound agent full config

```json
{
  "inbound": false,
  "outbound_auto_call": true,
  "outbound_numbers": ["+14155551234"]
}
```

`outbound_auto_call: true` triggers Cekura to place the call via the provider. Test profile fields are forwarded as dynamic variables. Works with VAPI and Retell only.

---

## 10f. Apply via PATCH

```bash
curl -X PATCH https://api.cekura.ai/test_framework/v1/aiagents/{id}/ \
  -H "X-CEKURA-API-KEY: $CEKURA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{ <fields from above> }'
```

---

## Phase 10 Gate

**Apply whichever advanced settings are relevant. Skip any that don't apply.**

Move to [Phase 11 — Verify Setup](phase11-verify.md).
