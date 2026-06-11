# Dynamic Variables and Provider Call State Reference

The reference appendix for the default Step 2.4 inspection. The goal is to inspect four signals about a specific call: (1) what the caller passed in to VAPI as `assistantOverrides.variableValues`, (2) what VAPI saw after merging defaults in `artifact.variableValues`, (3) what the LLM actually saw in its rendered system message, and (4) what the LLM passed back as tool-call arguments. Each answers a different question and they're rarely all in the same place.

Step 2.4 is the entry point on every iteration — don't gate this work on whether a failure "looks ambiguous"; the inspection is cheap and catches phantom-prompt-fix failure modes that pure transcript reading does not.

## Where the data lives

The result-batch retrieve does **not** include provider call state in its run summaries. For test runs, use the bulk-retrieve for runs; for production calls, use the per-id call-log retrieve. Both expose the VAPI call object inline:

| Cekura field | What's there |
|---|---|
| `provider_call_id` | The VAPI call UUID. Useful for direct VAPI lookups (`GET /call/{id}`) when the inline blob is missing fields or looks stale. |
| `provider_call_details.assistantOverrides.variableValues` | **Signal 1 — intent.** What the caller (Cekura) passed into VAPI when starting the call. If a key is absent here, the variable was never provided. |
| `provider_call_details.artifact.variableValues` | **Signal 2 — runtime.** What VAPI substituted at call time after merging overrides + assistant/project defaults. Compare against Signal 1 to spot rename mismatches. |
| `provider_call_details.artifact.messages` | **Signal 3 — what the LLM saw.** The full message array sent to the model. Search for literal `{{...}}` strings — if any survive here, substitution failed even though the call was made. |
| `provider_call_details.artifact.messages[*].toolCalls` | **Signal 4 — what the LLM did.** For any handoff or tool call, the actual `arguments` JSON. Reveals `[]`, hallucinated arrays, or relayed-correctly cases. |
| `provider_call_details.artifact.assistantActivations` | Sequence of which squad members were active when. Useful for attributing a failure to the correct member when transcripts are ambiguous. |

Bulk-retrieve payloads can be large (250–500 KB per run). Expect the result to overflow the inline limit and land in a saved file — extract the specific fields with `jq` or python rather than re-reading the whole blob into context.

## Direct VAPI lookup (fallback)

If `provider_call_details` is missing or looks truncated, fetch the call object directly from VAPI:

```
curl -fsS -H "Authorization: Bearer $VAPI_KEY" https://api.vapi.ai/call/$PROVIDER_CALL_ID
```

The shape is identical to what's embedded in `provider_call_details`. The direct fetch is most useful for very recent calls where Cekura hasn't yet ingested the artifact, or when an inline copy looks stale relative to a known-recent VAPI dashboard edit.

## ElevenLabs provider call state (note)

This reference is written for VAPI's rich `artifact` surface. ElevenLabs does not expose a fully-rendered system message or a merged `artifact.variableValues` the same way. For ElevenLabs failures the observable signals are usually: the dynamic-variable values Cekura passed at conversation start (Signal 1, intent, on the run record), the transcript, captured tool-call records (Signal 4, when present), and `metadata.ended_reason` (Signal 5). Substitution failure (Signal 3) is confirmable only when the transcript literally shows a `{{var}}` placeholder. The direct-provider fallback is `GET https://api.elevenlabs.io/v1/convai/conversations/{conversation_id}` (header `xi-api-key`) — it returns the transcript and analysis, not a VAPI-style rendered message array. When ElevenLabs runtime state can't confirm a variable-injection hypothesis, mark the diagnosis "suspected upstream — runtime state not observable" rather than proposing a phantom prompt edit, exactly as in the self-hosted modes.

## Decision tree

For a single suspect run (Cekura `run_id`):

1. Bulk-retrieve with `run_ids="<run_id>"` (bare comma-separated string, not a JSON array) → grab `provider_call_id` + `provider_call_details`.
2. Check `provider_call_details.assistantOverrides.variableValues`:
   - **Key absent** → variable was never provided. Failure is upstream of the agent (test profile config, scenario setup, or production caller). Prompt edits cannot fix this alone; surface as a hand-off to test-config or whoever populates the variable, and decide whether to also harden the prompt to handle the missing-variable case.
   - **Key present with expected value** → variable was provided correctly. Move to step 3.
   - **Key present with a different name than the prompt expects** (e.g. `phoneUpgrade` vs. `shouldAskForPhoneUpgrade`) → name mismatch. Either the prompt's placeholder or the caller's key is wrong. Pick whichever is canonical and fix the other side.
3. Check `provider_call_details.artifact.messages[0].content` (the rendered system message) for literal `{{...}}` placeholders:
   - **Literal placeholders present** → substitution failed despite the override being passed. Rare, but happens when placeholder syntax is malformed. Inspect the prompt for nested or escaped braces.
   - **Placeholders fully substituted** → the LLM saw the right input. Failure is downstream — the LLM didn't act on it correctly. This is a genuine prompt-following issue; Phase 3 should fix it.
4. If the failure involves a tool call, find the relevant `toolCalls` entry and inspect `arguments`:
   - **Literal string `{{...}}` in args** → schema validator likely rejected the call; transcripts will show repeated tool calls or stalls.
   - **Empty array / null where data was expected** → upstream didn't supply, or the LLM didn't relay it forward. Cross-reference with Signal 1.
   - **Plausible-looking but unverifiable values** → likely hallucination. Compare against the upstream member's own tool-call arguments (the source of the handoff) to confirm.

## Output format (per-failure observation)

A short observation per failure (or grouped, when patterns repeat) that travels into Phase 3:

```
- Run 3031835: appointment_rules=[] (empty), leadId=null, zipcode=null, currentDate=null;
  rendered system message contains literal {{leadId}}, {{zipcode}}, {{currentDate}};
  schedule_lab_appointment fired with leadId="{{leadId}}" (literal).
- Same pattern across runs 3031836, 3031838.
```

Group when patterns repeat — "all 3 failed runs show the same variable-injection failure" is more actionable for Phase 3 than per-run repetition.

## When the data isn't available

- **Text-mode runs without provider artifacts** and some chat call logs don't expose `provider_call_details`. Skip the inspection for those items and surface the gap in Step 2.5 — Phase 3 should know it's diagnosing on partial data.
- **Errored runs** that never produced a transcript also won't have meaningful artifact state; treat as no-signal, not as upstream-OK.

## Caveats

- The artifact's `variableValues` and the `assistantOverrides.variableValues` are **not** the same object. Overrides are what was passed in; artifact values are the merged result after VAPI applied defaults. A variable can appear in artifact even if it wasn't in overrides — that means a project- or assistant-level default supplied it.
- Squad calls have **per-member** message arrays. The artifact's top-level `messages` may show the entry assistant's view; use `assistantActivations` and the per-activation message logs (under each activation entry) to inspect downstream members.
- The bulk-retrieve for runs requires `run_ids` as a bare comma-separated string (e.g. `"3031399"`), not a JSON array. Passing `[3031399]` returns a 400.
- Direct VAPI fetches require `VAPI_KEY` (Phase 1 environment). Don't echo it back to chat or write it to a file.
