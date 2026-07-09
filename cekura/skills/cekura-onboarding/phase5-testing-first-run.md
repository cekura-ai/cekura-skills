# Phase 5 (testing) — First Test Run & Verification

> **Start:** Announce the step in plain words (e.g. "Let's connect your agent", "Generating your first evaluators") — never a phase number or the word "Phase"; the numbering below is internal navigation only.

This phase is the **finish line of onboarding**: one run completed and a transcript visible. Records existing is not success.

## 5a. Pick the run endpoint from the agent's connection

Retrieve the agent (`aiagents_retrieve`) and match its configured connection:

| Configured connection | Run tool |
|---|---|
| `telephony.phone_number` | `scenarios_run_voice` |
| `telephony.sip_uri` | `scenarios_run_sip` |
| `telephony.websocket_url` | `scenarios_run_chirp` |
| `provider.type` pipecat (WebRTC) | `scenarios_run_pipecat_v2` |
| `provider.type` livekit (WebRTC) | `scenarios_run_livekit_v2` |
| `provider.type` vapi / retell (WebRTC) | `scenarios_run_vapi_webrtc` / `scenarios_run_retell_webrtc` |
| `provider.type` elevenlabs | `scenarios_run_elevenlabs` |
| custom websocket | `scenarios_run_websocket` |
| chat/text | `scenarios_run_text` |

**Pick the tool from the agent's ACTUAL connection — never downgrade.** `scenarios_run_text` is for chat/text agents only; running a voice agent's verification as a text simulation (e.g. because provider credentials are unverified) is NOT a verification — it proves nothing about the connection. If no working connection exists, that IS the finding: surface it and collect a connection (phone number, or fixed credentials) instead of running a fake check.

## 5b. Execute

Run **one single scenario, `frequency: 1`** — this run is the end-to-end verification, not a coverage sweep. Voice calls take 1–3 minutes. Once it verifies clean (5c), the user can run the rest of the suite.

## 5c. Verification gate — the whole point

Poll the run's results (`results_retrieve` / `runs_bulk_retrieve`). Verify, for at least one run:

1. The call **connected and completed** (not busy / rejected / timed out).
2. A **transcript is present** with both sides talking (not empty, not one-sided silence).
3. Metric scores appeared.

**If verification fails: surface the finding, offer to fix now (default), but let the user skip.** Never fail silently — diagnose and present what's wrong with the run link:
- Call never connected / busy → wrong or unsupported number, SIP endpoint unreachable, WebRTC dispatch misconfigured (LiveKit `agent_name` mismatch is a classic).
- Connected but empty/one-sided transcript → the agent never spoke (agent-side error) or audio isn't flowing (SIP media/codec issue).

Then ask: **"Want me to fix this now and re-run?"** — fixing now is the default recommendation. If the user prefers to skip for now, continue to the next phase, but record the failure as an open item in every subsequent summary (what's broken + what to fix) so onboarding never ends with an implied success.

## 5d. Review results with the user

- **70–80% pass rate is realistic** for a first iteration; 90–95% after refinement. Don't aim for 100%.
- Walk through one failure: transcript, metric reasoning, what to change.

---

## Phase 5 Gate

**Preferred exit: at least one run with a completed call, a real two-sided transcript, and metric scores.** If the user chose to skip a failed verification, you may proceed — but the failure must be surfaced as an open item, never an implied success.

Confirm the step is done in plain words (no phase numbers). Then begin [Phase 6 — What's Next](phase6-testing-next.md).
