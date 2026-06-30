# Phase 10 — Advanced Configuration

Optional provider settings. Work through each section in order — apply what's relevant, skip what isn't.

---

> **Start:** Announce "Starting Phase 10 — Advanced Configuration" before doing anything in this phase.

## 10a. Outbound main agent config

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

Supported for: VAPI, Retell, ElevenLabs, Bland, LiveKit. Test profile fields are forwarded as dynamic variables when the call is placed.

---

## 10b. Auto-sync prompt (VAPI / Retell / ElevenLabs / Synthflow only)

**Skip this section for all other providers.**

`auto_sync_prompt: true` tells Cekura to periodically re-fetch the agent's system prompt from the provider so the Cekura description stays in sync whenever the prompt is updated on the provider side.

**Auto-import path** (`configure_from_provider: true`): `auto_sync_prompt` is **enabled automatically** after the import completes. Confirm it is on — no action needed unless the user explicitly wants to disable it.

**Manually-configured agents**: ask:
> "Would you like Cekura to automatically keep the agent description in sync with your provider? Cekura will re-fetch the system prompt on a schedule whenever you update it."

If yes, include in the PATCH:
```json
{
  "provider": {
    "auto_sync_prompt": true
  }
}
```

---

## 10c. Auto-import production calls (VAPI / Retell / ElevenLabs / Synthflow only)

**Skip this section for all other providers.**

`auto_import_calls: true` tells Cekura to fetch real production calls from the provider every 30 seconds. Imported calls appear in the Cekura dashboard for evaluation, observability, and scenario generation from real traffic.

**Off by default** — including after `configure_from_provider`. Always ask:
> "Would you like Cekura to automatically import your production calls for monitoring and analysis? This pulls real calls from your provider every 30 seconds."

Recommend enabling. If yes, include in the PATCH:
```json
{
  "provider": {
    "auto_import_calls": true
  }
}
```

---

## 10d. Apply via PATCH

Combine all relevant fields from 10a–10c into a single PATCH call:

```bash
curl -X PATCH https://api.cekura.ai/test_framework/v2/aiagents/{id}/ \
  -H "X-CEKURA-API-KEY: $CEKURA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "telephony": { "inbound": false, "outbound_numbers": ["+1..."] },
    "provider": {
      "auto_dial_outbound": true,
      "auto_sync_prompt": true,
      "auto_import_calls": true
    }
  }'
```

Only include fields that apply — omit any section the user declined or that doesn't apply to their provider.

---

## Phase 10 Gate

**Apply whichever settings are relevant. Skip any that don't apply.**

Announce: "Phase 10 complete." Then immediately begin [Phase 11 — Verify Setup](phase11-verify.md) without waiting for the user.
