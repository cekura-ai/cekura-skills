# Phase 9 — Advanced Configuration

Optional settings for outbound behavior. Ask the user which apply.

---

## 10a. Outbound agent config

`auto_dial_outbound` is inside the `provider` block; `outbound_numbers` is inside the `telephony` block:

```json
{
  "telephony": {
    "inbound": false,
    "outbound_numbers": ["+14155551234"]
  },
  "provider": {
    "type": "vapi",
    "auto_dial_outbound": true,
    "credentials": { "..." : "..." }
  }
}
```

Works with VAPI and Retell only. Test profile fields are forwarded as dynamic variables when the call is placed.

---

## 10b. Apply via PATCH

```bash
curl -X PATCH https://api.cekura.ai/test_framework/v2/aiagents/{id}/ \
  -H "X-CEKURA-API-KEY: $CEKURA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{ <fields from above> }'
```

---

## Phase 10 Gate

**Apply whichever settings are relevant. Skip any that don't apply.**

Move to [Phase 10 — Verify Setup](phase10-verify.md).
