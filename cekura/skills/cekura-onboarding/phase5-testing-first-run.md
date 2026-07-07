# Phase 5 (testing) — First Test Run & Verification

> **Start:** Announce "Starting Phase 5 — First Test Run".

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

## 5b. Execute

Run **one single scenario, `frequency: 1`** — this run is the end-to-end verification, not a coverage sweep. Voice calls take 1–3 minutes. Once it verifies clean (5c), the user can run the rest of the suite.

## 5c. Verification gate — the whole point

Poll the run's results (`results_retrieve` / `runs_bulk_retrieve`). Verify, for at least one run:

1. The call **connected and completed** (not busy / rejected / timed out).
2. A **transcript is present** with both sides talking (not empty, not one-sided silence).
3. Metric scores appeared.

**If verification fails, onboarding is not done.** Diagnose now, while you're here:
- Call never connected / busy → wrong or unsupported number, SIP endpoint unreachable, WebRTC dispatch misconfigured (LiveKit `agent_name` mismatch is a classic). Fix the connection config from Phase 2 and re-run.
- Connected but empty/one-sided transcript → the agent never spoke (agent-side error) or audio isn't flowing (SIP media/codec issue). Surface the finding to the user with the run link.
- Repeat until one clean run exists. If truly blocked on the user's infrastructure, end with an explicit statement of what is broken and what they must fix — never with an implied success.

## 5d. Review results with the user

- **70–80% pass rate is realistic** for a first iteration; 90–95% after refinement. Don't aim for 100%.
- Walk through one failure: transcript, metric reasoning, what to change.

---

## Phase 5 Gate

**Do not declare onboarding complete until at least one run has a completed call with a real two-sided transcript and metric scores.**

Announce: "Phase 5 complete." Then begin [Phase 6 — What's Next](phase6-testing-next.md).
