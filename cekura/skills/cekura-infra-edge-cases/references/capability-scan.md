# Phase 0: Pipeline Capability Scan (optional)

Run this **only when the agent's source repo is available**. It is an enrichment layer, not a gate. A hosted VAPI/Retell/ElevenLabs agent with no repo skips this entirely and the fixed catalog still runs blind.

## The one rule that makes this safe

**The scan never removes a stressor family.** Its output only:
1. **Prioritizes**; which families to probe hardest (more intensity levels), and which to lead with.
2. **Grounds the fix**; turns a generic recommendation ("add STT confidence gating") into a file:line pointer.
3. **Pre-states the gap**; "the code has no idle timer, so this probe confirms that gap and shows its user-facing symptom."

If you ever find yourself thinking "the code doesn't handle X, so skip the X test"; stop. That is the `infra-test-suite` blind spot this whole skill exists to avoid. "No handling" means **probe harder**, not skip.

## What to look for: mechanism checklist

For each stressor family, grep/read the pipeline for the resilience mechanism that would let the agent survive it. Presence is rarely a clean yes/no; record yes / partial / no with a file:line.

| Stressor family | Resilience mechanism to look for | Grep-ish signals |
|---|---|---|
| Degraded network | Jitter buffer / packet-loss smoothing; STT socket **reconnect** on drop; STT **confidence gating** | `jitter`, `buffer`, `reconnect`, `reopen`, `onClose`/`onError` handlers that re-establish, `confidence` |
| Background noise | STT confidence gating; VAD threshold / noise-floor calibration; hard max-turn duration | `confidence`, `vad`, `threshold`, `noise`, `maxTurn`, endpointing config |
| Boundary silence | Idle / no-transcript **timer** + re-prompt ladder; end-of-call idle handling | `idle`, `setTimeout` on caller silence, `no.?transcript`, `still there`, `reprompt` |
| Barge-in | Interruption **cancellation**: cancel token, flush queued audio, cancel in-flight LLM+TTS | `barge`, `interrupt`, `cancel`, `abort`, generation/epoch token, `clear` event |
| Accent / speech rate | STT confidence gating; **adaptive or generous endpointing**; STT model robustness | `confidence`, `vadSilence`/`endpoint` value (too-short cuts slow speakers), model id |
| Rapid turns / DTMF | Turn **serialization / supersede** token; DTMF buffering during TTS | generation token, queue, `dtmf`, `digit` |

## How to scan

1. **Find the pipeline files**; transport/websocket handler, STT wrapper, the turn orchestrator (where caller-final → LLM → TTS happens), TTS wrapper, and the config/thresholds file.
2. **Read the orchestrator end to end**; it holds turn-taking, barge-in, and (if any) idle logic. This is the highest-signal file.
3. **Check the config file** for fixed thresholds (VAD silence, timeouts); a single hardcoded value with no adaptation is a risk signal, not necessarily a bug.
4. **Grep the signals above** across the source (exclude tests/vendored code).
5. Record each mechanism as yes / partial / no with a file:line.

## Output: the capability matrix

Produce one table, then feed it into Step 1 (intensity) and Step 5 (grounded fixes):

| Mechanism | Present? | Evidence (file:line) | Families at risk | Predicted |
|---|---|---|---|---|
| Interruption cancellation | yes | `session.ts:174` (generation bump + `clear`) | Barge-in | likely PASS |
| STT confidence gating | no | `stt.ts:38` acts on any transcript | Network, Noise, Accent | likely FAIL |
| Idle / no-transcript timer | no | none in orchestrator | Boundary silence (all 3) | likely FAIL |
| Jitter buffer / STT reconnect | no | `session.ts:114` onClose just sets flag | Network | likely FAIL |
| Endpointing adaptivity | partial | `config.ts:31` fixed 0.6s | Slow speaker | risk |

**Reading the matrix:**
- `Present = yes` → still probe the family, but you can go lighter (fewer intensities). A pass confirms the mechanism works.
- `Present = no / partial` → probe **hardest** (full intensity ladder), expect a failure, and the "Evidence" cell is already your fix location for the Step 5 report.

## Worked example: the ElevenLabs/Gemini/Twilio TS reference agent

A speech-to-speech TS pipeline (ElevenLabs `scribe_v2_realtime` STT with VAD turns, Gemini brain, streaming TTS, Twilio μ-law transport). The scan found:

- **Barge-in: solid.** `session.ts` bumps a `generation` cancellation token on the caller's first partial while the agent is speaking, sends Twilio a `clear` event (flushes queued audio), and every in-flight Gemini/TTS callback checks `gen === this.generation`. → probe lightly; expect PASS.
- **STT confidence gating: absent.** `stt.ts` fires `onFinal` on any committed transcript with text; the orchestrator acts on it directly. → garbled input under loss/noise gets acted on; probe network/noise/accent hard.
- **Idle / no-transcript timer: absent.** No timer on caller silence anywhere; if STT never emits a final, the agent sits silent. End-of-call hangup only fires when the *model* asks to end, which it can't if it never gets a turn. → all three boundary-silence probes expected to fail (dead air / hang).
- **Jitter buffer / STT reconnect: absent.** μ-law passthrough with no buffering; `onClose` just sets `sttReady=false` and never reopens, so a mid-call socket drop makes the agent permanently deaf. → network probes expected to fail hard.
- **Endpointing: fixed 0.6s VAD silence** (`config.ts`), no adaptation → a slow speaker pausing >0.6s mid-sentence gets committed early. → slow-speaker probe at risk.

That matrix told us, before spending a single call credit, that the network + boundary-silence + noise families are the real gaps (and where in the code to fix them), while barge-in is already hardened; turning the eventual run report from generic advice into file-grounded fixes.
