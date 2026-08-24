# Repository discovery

What to read before authoring a single case, and — the part that matters — **what each answer buys
you in the spec**. A question whose answer changes no assertion is not worth asking.

Find what you can from the code first. Surface only the gaps you genuinely cannot resolve, in one
batch, at the end. Do not interview the user through the whole list.

Write the findings to `/tmp/cekura-suite-discovery.md`. Every numeric value and every quoted phrase
must carry a `file:line`, because those are what turn a sequence assertion into a threshold
assertion, and an unsourced number is a guess.

---

## Step 0 — Which bot is deployed?

Many repos hold several entry points: one per transport, one per use case, a legacy variant beside
the current one. Answering the rest for the wrong one produces a suite that tests nothing shipped.

- List every entry point (`bot.py`, server mains, agent classes, worker entrypoints).
- Check Dockerfiles, deploy configs (`pcc-deploy.toml`, `fly.toml`, `livekit.toml`, k8s manifests),
  CI workflows, `README`, `CLAUDE.md`/`AGENTS.md` to see which one production runs.
- If two variants share a processor, note it: **a change there is two coverage considerations, not
  one.** The simulated caller and the agent under test can run different assemblies, and a
  regression can exist in one seat and not the other.

If the code cannot settle it, ask — before Q1, not after.

## Step 0b — Is there already a suite?

```bash
grep -rl 'schemas/test-suite' --include='*.json' .       # definitive: a spec's $schema line
git ls-files | grep -Ei '(cekura|tests?).*\.json$'       # candidates
git ls-files '.github/workflows/*' '.gitlab-ci.yml' 'Jenkinsfile' | xargs grep -ln 'cekura' 2>/dev/null
```

Found one → this is an **update**, not a create. Read it fully, keep every `key`, and go to the
merge-base diff review. Found a workflow that already calls Cekura → extend that file rather than
adding a second one.

---

## Q1 — How does a call reach the bot?

Transport (SIP, WebRTC, raw WebSocket, a vendor SDK), inbound or outbound or both, and where the
destination is configured.

**Buys you:** the run channel. `voice` needs the agent to have a phone number; `text` a chat
provider; `elevenlabs`, `livekit_v2` and `pipecat_v2` their respective sessions. It also decides
whether case 6 (IVR/voicemail) is real or dead — an inbound-only agent never meets a menu.

## Q2 — How does it hear?

The STT service, whether a VAD sits in front, and whether anything custom decides turn boundaries —
`UserTurnStrategy`, `TurnStartStrategy`, endpointing config. Record the actual numbers: minimum word
count to start a turn, speech timeout to end one, what happens on an empty or failed transcript.

**Buys you:** case 2's pause length and case 1's interrupt word counts, at threshold rather than at
a safe distance from it. The STT provider also predicts the failure class worth probing in case 7 —
providers differ in how they race partial transcripts.

## Q3 — How does it decide what to say?

The model, retry count and delay, any deadline, any validity check on the response, any secondary
provider.

**Buys you:** whether a fallback path is transcript-visible at all. If the fallback says something
specific, it is assertable; if it is silent, it is not a test.

## Q4 — How does it speak?

TTS service, whether the caller can interrupt playback, what stops audio and resets state, and any
fallback voice.

**Buys you:** whether case 1 can exist. If audio cannot be interrupted, half that case is dead.

## Q5 — What happens when the caller goes quiet?

Is there an idle timer; what fires; **the exact prompt strings**; how many escalations; whether it
ends the call.

**Buys you:** case 3 entirely — its silence length, its expected count, and the strings the judge
matches. No idle timer, no case 3.

## Q6 — What side channels exist?

For each of DTMF in, DTMF out, SMS in, SMS out, voicemail detection, pre-recorded playback,
call transfer, call hold: does it exist, what triggers it, which direction.

Check the **deployed variant's** pipeline, not just that the class exists somewhere in the repo. A
DTMF aggregator present in one assembly and absent in the deployed one means DTMF is absent.

**Buys you:** the `tools` array on each case, and whether cases 6 and 8 survive.

## Q7 — Can the agent end a call itself?

Tool-driven hangup, task-completion hangup, or never.

**Buys you:** case 5, and every terminal assertion in the suite.

## Q8 — Does it speak first, and what does it say?

**Buys you:** the shape of condition `id: 0`. If the agent speaks first, `action` is `""` and the
caller waits. Getting this backwards desynchronises every following turn.

## Q9 — Which languages?

Primary, all configured ones, how the language is chosen per call, whether it can switch mid-call,
and whether any configured language lacks a voice or STT model (configured but not production).

**Buys you:** case 9, the `language` field on every case, and the personality choice.

## Q10 — How is the bot deployed, and how would CI reach it?

The build and deploy commands, whether a PR gets an ephemeral deployment and under what name, the
existing CI structure, and where secrets already live.

**Buys you:** the whole CI wiring — which channel, whether a per-run agent-name override is needed,
which workflow file to extend, and what the secret is already called.

---

## Turning discovery into candidates

For each behavior found, write one line:

```
[C-07] Idle escalation fires 3 prompts then hangs up   bot/idle.py:88   seat: under-test   transcript: yes
```

Then score it, and keep the top 10–12:

| Axis | Scores high when |
|---|---|
| **Regresses** | those files changed often in recent history, or the behavior is central to the agent's job |
| **Blast radius** | failure breaks the call, rather than degrading one turn |
| **Transcript-detectable** | the judge can actually see it. **If not, it scores zero — it is not a test** |

Everything not selected gets one line in a parked list with the reason. Not silently dropped, and
not promoted into a case to avoid the decision.
