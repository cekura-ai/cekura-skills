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

**Custom SIP/WebSocket headers:** if the user's agent expects custom headers on incoming calls (routing, tenant, or auth headers), create a test profile whose `main_agent_variables` contain the `X-` prefixed keys (`test_profiles_create`) and pass its ID in `test_profile_ids` on the run. For SIP runs that is the only mechanism — headers cannot be set on the agent record or in the run request body, and non-`X-` keys are not sent as headers. (WebSocket agents can also carry static headers in `websocket_headers` on the agent.)

**Pick the tool from the agent's ACTUAL connection — never downgrade.** `scenarios_run_text` is for chat/text agents only; running a voice agent's verification as a text simulation (e.g. because provider credentials are unverified) is NOT a verification — it proves nothing about the connection. If no working connection exists, that IS the finding: surface it and collect a connection (phone number, or fixed credentials) instead of running a fake check.

**LiveKit / Pipecat — this run is the first real check on the credentials.** They were created as placeholders and replaced by the user on the agent page; nothing reads them back, so this call is where a wrong or mistyped key, secret or URL first shows up. Two consequences: don't run before the user has confirmed they replaced them (phase2 Step 5), and if the call never connects, **say the credentials are the first thing to check** rather than reporting it as an unexplained failure. A placeholder or a typo fails exactly like a broken agent, and users spend hours debugging code that works.

## 5b. Execute

**Start the run immediately — no question first.** Not "ready to run?", not "which scenario should we start with?", not "shall I kick this off?". The user opted into onboarding, which is the authorization; pick one of the generated scenarios yourself (any of them proves the connection, which is this run's only job) and call the run tool.

Run **one single scenario, `frequency: 1`** — this run is the end-to-end verification, not a coverage sweep. Voice calls take 1–3 minutes. Once it verifies clean (5c), offer to run the rest of the suite.

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
