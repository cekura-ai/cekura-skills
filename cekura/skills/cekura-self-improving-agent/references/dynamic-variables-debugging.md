# Dynamic Variables and Provider Call State Reference

Reference for Step 2.4 inspection. Goal: inspect four signals for a specific call — (1) what the caller passed into the provider as `assistantOverrides.variableValues`, (2) what the provider saw after merging defaults in `artifact.variableValues`, (3) what the LLM actually saw in its rendered system message, and (4) what the LLM passed back as tool-call arguments. Each answers a different question and they're rarely in the same place.

Run Step 2.4 on every iteration — don't gate it on whether a failure "looks ambiguous." The inspection is cheap and catches phantom-prompt-fix failure modes that pure transcript reading does not.

## Where the data lives

The result-batch retrieve does **not** include provider call state in its run summaries. Use the bulk-retrieve for test runs; use the per-id call-log retrieve for production calls. Both expose the provider call object inline.

| Cekura field | What's there |
|---|---|
| `provider_call_id` | The provider call UUID. Use for direct provider lookups when the inline blob is missing fields or stale. |
| `provider_call_details.assistantOverrides.variableValues` | **Signal 1 — intent.** What the caller (Cekura) passed into the provider when starting the call. If a key is absent here, the variable was never provided. |
| `provider_call_details.artifact.variableValues` | **Signal 2 — runtime.** What the provider substituted after merging overrides + assistant/project defaults. Compare against Signal 1 to spot rename mismatches. |
| `provider_call_details.artifact.messages` | **Signal 3 — what the LLM saw.** Full message array sent to the model. Search for literal `{{...}}` strings — if any survive, substitution failed. |
| `provider_call_details.artifact.messages[*].toolCalls` | **Signal 4 — what the LLM did.** Actual `arguments` JSON for any handoff or tool call. Reveals `[]`, hallucinated arrays, or correct relay. |
| `provider_call_details.artifact.assistantActivations` | Sequence of which squad members were active when. Useful for attributing a failure to the correct member when transcripts are ambiguous. |

Bulk-retrieve payloads can be large (250–500 KB per run). Expect overflow into a saved file — extract specific fields with `jq` or python rather than re-reading the whole blob.

## Direct provider lookup (fallback)

If `provider_call_details` is missing or truncated, fetch directly:

**VAPI:**
```
curl -fsS -H "Authorization: Bearer $VAPI_KEY" https://api.vapi.ai/call/$PROVIDER_CALL_ID
```

**ElevenLabs:**
```
curl -fsS -H "xi-api-key: $XI_API_KEY" https://api.elevenlabs.io/v1/convai/conversations/$CONVERSATION_ID
```

The VAPI shape is identical to what's embedded in `provider_call_details`. The direct fetch is most useful for very recent calls where Cekura hasn't yet ingested the artifact, or when an inline copy looks stale.

## ElevenLabs provider call state

ElevenLabs does not expose a fully-rendered system message or a merged `artifact.variableValues` the same way VAPI does. Observable signals for ElevenLabs failures are: dynamic-variable values Cekura passed at conversation start (Signal 1, on the run record), the transcript, captured tool-call records (Signal 4, when present), and `metadata.ended_reason`. Substitution failure (Signal 3) is confirmable only when the transcript literally shows a `{{var}}` placeholder. When ElevenLabs runtime state can't confirm a variable-injection hypothesis, mark the diagnosis "suspected upstream — runtime state not observable" rather than proposing a phantom prompt edit.

## Decision tree

For a single suspect run (`run_id`):

1. Bulk-retrieve with `run_ids="<run_id>"` (bare comma-separated string, not a JSON array — see gotchas) → grab `provider_call_id` + `provider_call_details`.
2. Check `provider_call_details.assistantOverrides.variableValues`:
   - **Key absent** → variable was never provided. Failure is upstream (test profile config, scenario setup, or production caller). Surface as a hand-off; decide separately whether to also harden the prompt to handle the missing-variable case.
   - **Key present with expected value** → variable was provided correctly. Move to step 3.
   - **Key present with a different name than the prompt expects** (e.g. `phoneUpgrade` vs. `shouldAskForPhoneUpgrade`) → name mismatch. Pick whichever side is canonical and fix the other.
3. Check `provider_call_details.artifact.messages[0].content` (rendered system message) for literal `{{...}}` placeholders:
   - **Literal placeholders present** → substitution failed despite the override being passed. Inspect the prompt for nested or escaped braces.
   - **Placeholders fully substituted** → the LLM saw the right input. Failure is downstream — a genuine prompt-following issue for Phase 3.
4. If the failure involves a tool call, find the relevant `toolCalls` entry and inspect `arguments`:
   - **Literal `{{...}}` in args** → schema validator likely rejected the call; transcripts show repeated tool calls or stalls.
   - **Empty array / null where data was expected** → upstream didn't supply it, or the LLM didn't relay it forward. Cross-reference with Signal 1.
   - **Plausible-looking but unverifiable values** → likely hallucination. Compare against the upstream member's own tool-call arguments to confirm.

## Output format (per-failure observation)

```
- Run 3031835: appointment_rules=[] (empty), leadId=null, zipcode=null, currentDate=null;
  rendered system message contains literal {{leadId}}, {{zipcode}}, {{currentDate}};
  schedule_lab_appointment fired with leadId="{{leadId}}" (literal).
- Same pattern across runs 3031836, 3031838.
```

Group when patterns repeat — "all 3 failed runs show the same variable-injection failure" is more actionable than per-run repetition.

## When the data isn't available

- **Text-mode runs / chat call logs without provider artifacts**: skip inspection; note the gap in Step 2.5 so Phase 3 knows it's diagnosing on partial data.
- **Errored runs** that never produced a transcript: no meaningful artifact state — treat as no-signal, not as upstream-OK.

## Gotchas

- `artifact.variableValues` and `assistantOverrides.variableValues` are **not** the same object. Overrides are what was passed in; artifact values are the merged result after the provider applied defaults. A variable can appear in artifact even if it wasn't in overrides — a project- or assistant-level default supplied it.
- **Squad per-member messages.** The artifact's top-level `messages` may show only the entry assistant's view. Use `assistantActivations` and the per-activation message logs to inspect downstream members.
- **`runs_bulk_retrieve` bare-string gotcha.** The `run_ids` parameter is a bare comma-separated string (e.g. `"3031399"`), not a JSON array. Passing `[3031399]` returns a 400.
- Direct VAPI fetches require `VAPI_KEY` (Phase 1 environment). Don't echo it to chat or write it to a file.
