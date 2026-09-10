# Change triage

One question per changed hunk:

> Would the transcript of an existing case differ because of this change — or is there a new
> transcript-observable behavior that no current case produces?

Everything below is a shortcut to answering it. It is not a licence to skip reading the hunk: the
table says what a class of change *usually* means, and the "trap" column exists because the
exceptions are where suites rot.

## Layers, not frameworks

The rows below are **layers of a voice agent**, not files, libraries or frameworks. A turn-taking
threshold is a VAD parameter in one repository, a turn-detector config in another, and a
hand-written silence counter in a third; a tool is a framework's function-calling decorator here
and a hand-rolled JSON dispatch there. The triage is identical in all of them, because the triage
question is about what the caller hears, and the caller cannot tell which library produced it.

So find the layer by tracing the entrypoint, not by recognising a name. If a change does not
belong to any row below, that is not a gap in the table — ask the one question directly: would an
existing case's transcript differ, or is there a new transcript-observable behavior? A repository
with no framework at all triages exactly the same way.

## By layer

| Changed | Usually | Why, and the trap |
|---|---|---|
| **System prompt / persona text** | `none` for tone; `TIGHTEN` or `REPLACE` for a new rule | Wording changes are not coverage events. A new *rule* ("never quote a price without the disclaimer") is: it is a sentence the agent must now say, and an existing case that reaches that moment can assert it. Trap: asserting the exact new phrasing rather than its content — the next copy edit turns your case red for nothing. |
| **A quoted agent phrase an existing case asserts** | `REPLACE` | The case is now wrong and will go red on the next run. Update the asserted content, keep the key. Trap: this is the one case where *not* editing is the failure. |
| **STT provider / model / language config** | `none`, unless a case asserts recognition | Swapping a recogniser changes accuracy, not the script. It earns coverage where recognition is the point: spelled letters, digit strings, an alphanumeric id, a non-English utterance. Trap: grading a normalisation the STT does anyway ("said *twenty-five*, not *two five*"). |
| **LLM provider / model / temperature** | `none` | The judge reads what was said, not which model said it. Regression risk is real but diffuse; it belongs to the whole suite, not to a new case. Trap: an ADD here is how suites double in size with no new coverage. |
| **TTS provider / voice / speed** | `none` | Nothing about a voice is transcript-observable. Trap: `<speed>` and `<volume>` exercise a path; neither is ever the assertion. |
| **VAD / endpointing / turn-detection thresholds** | `TIGHTEN` or `EXTEND` on an existing timing case | The observable is *who speaks next and when*: does the agent wait through a mid-sentence pause, does it cut in. Extend the case that already has a silence or interruption turn. Trap: a threshold moved by 100ms that no written pause straddles changes no transcript — quote the old and new values and the pause in the case before deciding. |
| **Interruption / barge-in handling** | `EXTEND`, else `ADD` | Directly observable: the agent stops, and what it says next. Needs `<interruption time="Xs" />` opening an `action_followup` against speech already in progress. Trap: interrupting a greeting at `0s` interrupts nothing. |
| **Idle timer / "are you still there" / max duration** | `TIGHTEN`, or `REPLACE` when the value moved | The prompt line and the timeout are both observable, and a changed timeout usually invalidates the `<silence>`/`<hold>` in the existing case. Trap: a `<silence>` shorter than the new timer proves nothing and reads as coverage. |
| **DTMF / IVR navigation** | `EXTEND` on the IVR case, else `ADD` | Digits are observable and deterministic — good value per call. `<dtmf digits="…" />` may share an action with speech; `<ivr text="…" />` may not. Trap: post-IVR speech pushed into the same action never plays. |
| **Voicemail / answering-machine detection** | `EXTEND`, else `ADD` | A distinct terminal lifecycle: the agent should leave a message, or hang up, and not carry on a conversation with a beep. `<voicemail …/>` occupies its whole action. Trap: stacking further turns after a terminal outcome. |
| **A new tool / function the agent can call** | `ADD`, or `EXTEND` if a case already reaches that moment | Observable through what the agent says once the tool answers. Needs mock data the case controls; without it you are testing a live dependency, not the bot. Trap: asserting the call happened rather than what the caller heard. |
| **A tool's arguments, error path, or removal** | `TIGHTEN` for the error path; `RETIRE` for removal | The failure branch is the one nobody covers: what does the caller hear when the lookup times out. Trap: leaving a case that calls a tool the code no longer has — it goes red forever and gets waved through. |
| **Transfer / handoff / end-call** | `TIGHTEN`, else `ADD` | Terminal lifecycle. Assert the spoken hand-off and that the call ends; grade the goodbye only when termination is the point of the case. Trap: a farewell assertion smuggled into an unrelated case. |
| **A new supported language** | `ADD` (one case, `language` set explicitly) | A language path is a distinct pipeline: recogniser, prompt, voice. Nothing about the English cases proves it. Trap: forgetting `language` on the case, which silently tests English. |
| **Transport (WebSocket, WebRTC, SIP, telephony)** | `ADD` only if the suite cannot already reach it | Different assembly, different failure modes. But the run *channel* is a request parameter, not a spec field — the same committed case can be dialled over another channel by CI. Check the workflow before adding a file. Trap: a new case that differs from an existing one only by transport. |
| **Dynamic-variable / config plumbing** | `TIGHTEN` when the agent speaks the value | `agent_variables` reach the agent as dynamic variables and only matter if it already reads that name; `caller_variables` never reach it. Trap: inventing keys, which the agent silently ignores while the case looks specific. |
| **Retries, timeouts, error handling** | `TIGHTEN` if a case can reach the branch | Worth covering only where the caller hears something ("let me try that again"). Trap: a branch no scripted turn can trigger — the statement returns `blocked` on every run. |
| **Logging, tracing, metrics emission** | `none` | Not in the transcript. If it matters, it is a monitoring assertion, not a call. |
| **Refactor, rename, type hints, dead code** | `none` | Say so in the table and move on. |
| **Dependency bumps** | `none` | Except where the dependency *is* the speech path and the diff shows behavior changing with it. |
| **Docs, CI, Dockerfile, deploy config** | `none` | The one exception is a workflow change to how the suite itself runs, which belongs to whoever owns the workflow. |

## Seat and transport

A repository that builds both the agent under test and the simulated caller runs different code
in each seat. A change in shared code that both assemblies import is **two rows** in the decision
table, and coverage of one seat proves nothing about the other. Say which assembly each case
exercises; if the suite only reaches one of them, that is an `uncovered` row worth writing down.

## Before you add: the drop-if check

A case is dead — do not port it, and retire it if it already exists — when:

- no written turn can trigger its assertion (permanently `blocked`);
- the behavior it grades is not in the transcript (a waveform, a voice, an internal call);
- the code path it targets was deleted;
- an existing case already produces the same evidence, only with a longer script.

A suite of six that covers the real pipeline beats twelve with six dead cases, because the six
dead ones teach reviewers that red means nothing.

## Worked rows

**`none` — a refactor that looks scary.** Wherever the repository builds its speech services, STT
construction moves into a helper. The provider, model and language arguments are identical either
side of the diff. No transcript changes; no case can tell. Row: `none`, with the `file:line` of
the moved block as evidence.

**`TIGHTEN` — a prompt gains a rule.** The prompt now requires the agent to state the callback
number before ending. Case `appointment-reschedule` already runs to the end of a booking. Add one
line — `The main agent should state a callback number before the call ends.` — to its
`expected_outcome`. No new call.

**`REPLACE` — a threshold moved.** The idle prompt fires at 6s, down from 10s, and case
`idle-recovery` holds `<silence time="8s" />` to prove the old timer. Eight seconds now straddles
the new prompt: the case would pass for the wrong reason. Replace the turn with a value that
brackets the new behavior, keep the key, and note the old value in the pull-request comment.

**`ADD`, paid for.** The bot gains Spanish. Nothing in the suite sets `language`, so no case
touches the Spanish recogniser, prompt or voice. Add one Spanish case — and retire
`tts-voice-swap`, whose only assertion was that a voice change did not break the greeting, which
the drop-if check calls dead. Count stays at eight.
