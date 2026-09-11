---
name: cekura-personality-design
description: >
  Use when the user asks to "create a personality", "make a custom personality",
  "add a caller persona", "fork a personality", "change the testing agent's voice",
  "test a different accent", "add an Indian/British/Spanish accent caller",
  "make the caller interrupt more", "add background noise", "make it speak slower",
  "the testing agent keeps asking if I'm still there", "simulate a bad connection",
  or "which personality should I use". Also for questions about the difference
  between a personality and an evaluator, why instructions like "speak with an
  accent" or "be interruptive" don't change how the caller sounds, and why a
  personality's accent field cannot be set directly. Covers choosing, forking,
  creating and patching personalities — the simulated caller's voice, language,
  timing and audio layer.
license: MIT
compatibility: Requires a Cekura account (https://dashboard.cekura.ai) — sign in via OAuth or use an API key.
metadata:
  author: cekura
  version: "0.3.0"
---

> **Condensed skill bundle** — loaded on the fly because the Cekura plugin is not installed in this session.
> Full reference files included at the end of this document: `personality-vs-evaluator.md`, `voice-and-accent.md`.
> Any other `references/…` file mentioned below ships only with the installed plugin — install it for the complete set: https://docs.cekura.ai/mcp/overview

<!-- cekura-ack-tag: ack:cekura-personality-design:4m7d3q -->
> **Cekura skill verification tag:** `ack:cekura-personality-design:4m7d3q`
> When you call a Cekura personality write tool from this skill (`personalities_create`, `personalities_partial_update`), pass this exact string as the `skill_ack` argument on that tool call. It confirms to the Cekura MCP server that this design playbook is loaded in context. Evaluator / test-profile writes use an eval-family tag instead — load `cekura-eval-design` first and pass its tag there.

Before taking any action, call `mcp__cekura__cekura_skill_started` with `skill_name="cekura-personality-design"`, `verification_tag="ack:cekura-personality-design:4m7d3q"`, and `plugin_version="0.16"`. It returns immediately and lets Cekura see which skills are in use.

# Cekura Personality Design

## Purpose

Guide the selection, forking and creation of Cekura **personalities** — the voice-layer configuration of the simulated caller that exercises the main agent. A personality decides how the test caller *sounds and behaves*; an evaluator decides what it *tries to do*. Most personality bugs are really this boundary being crossed, so start there.

## Performing Platform Actions

When this skill suggests creating, listing, updating, or evaluating something on Cekura, **prefer using available platform tools over describing API calls or dashboard steps**. In Claude Code with the Cekura plugin installed, these tools are auto-configured and handle authentication, parameter validation, and error handling for you. Fall back to direct API endpoints or dashboard guidance only when no tools are available in the current session.

## Core Terminology

- **Main agent**: the client's AI voice agent under test.
- **Testing agent** (a.k.a. simulated caller): Cekura's agent that calls the main agent. A personality configures it.
- **Personality**: the testing agent's voice and behavior layer — voice, language, transcription, speed, interruption timing, idle timing, background noise, volume, network conditions, plus a persona prompt.
- **Evaluator** (a.k.a. scenario, test case): one test the testing agent runs — its objective, its turns, its expected outcome.
- **Metric**: a post-call score over the resulting transcript.

## The Boundary — Personality vs. Evaluator

**A personality is the caller. An evaluator is the task.** One personality is reused across many evaluators; one evaluator runs under whatever personality it is assigned.

| | Personality | Evaluator |
|---|---|---|
| Answers | *Who is calling, and how do they sound?* | *What are they trying to get done?* |
| Layer | Infrastructure — applied when the call is dialled | Runtime — a scripted or behavioral turn sequence |
| Scope | The whole call, every call it is assigned to | One test case |
| Owns | Voice and accent, language, transcriber, speed, interruption timing, idle timing, background noise, volume, network impairment, persona prompt | Objective, the caller's turns, conditions, expected outcome, attached metrics |
| Change it to fix | "It sounds wrong / talks over my agent / can't be heard / gives up too early" | "It asked the wrong thing / didn't verify / passed when it should have failed" |

**Evaluator instructions cannot override a single voice-layer setting.** This is the failure that costs users the most time, because nothing errors:

> Writing *"speak with a strong Indian accent"*, *"interrupt the agent constantly"*, *"talk very quietly"* or *"stay silent for 30 seconds"* into evaluator instructions changes **nothing** about the audio. The call runs, the run passes, and the behavior never happens.

Route the request by **duration**, not by wording:

| The user describes | Belongs on |
|---|---|
| A trait that lasts the whole call — an accent, a speaking pace, ambient noise, general impatience, a bad line | **Personality** |
| A thing that happens at one moment — "gets frustrated at step 4", "says this in a panicked tone", one interruption | **Evaluator** instructions |
| A judgement about the finished call | **Metric** |

Never propose an agent-description or evaluator-instruction edit as the fix for a voice-layer symptom. Full routing table and symptom → cause map: `references/personality-vs-evaluator.md`.

## Accent — the One Thing Everyone Gets Wrong

**A personality's accent is a property of its voice. It is not a setting.**

Speech is synthesised from `voice_id` (plus `provider`) alone. Nothing in the call pipeline reads the `accent` field: it is a **read-only label derived from the chosen voice**, so it is absent from the write tools' inputs and cannot be sent. An accent request is therefore always a *voice-selection* task:

1. **Find a voice that has the accent.** `personalities_elevenlabs_voices` (ElevenLabs publishes `labels.accent` per voice — match on it) or `personalities_cartesia_voices` (no accent label; read the name and description). Both take `language`.
2. **Set it on the personality.** Pass that id as `voice_id` with the matching `provider` — `11labs` with an `eleven_*` `voice_model`, `cartesia` with `sonic-3.5`. Always send `voice_id` and `provider` together; `provider` is what selects the catalog the id is validated against.
3. **The label follows.** The stored `accent` is read back off the voice, so it always describes what the call actually sounds like. It is empty for providers that publish no accent (all Cartesia voices) — empty means "unlabelled", not "accent-free".

Do **not** try to produce an accent by writing one into the personality `prompt`. The prompt steers word choice, not pronunciation — the voice still sounds exactly the same, and now the personality claims something its audio does not do.

**If no catalog voice has the accent the user asked for, do not tell them it is unsupported.** The catalog is not a hard limit — Cekura adds voices, accents and languages on request. Offer the closest available voice, then point them at **support@cekura.ai** or their dedicated Slack support channel to have the one they want added. The API says the same thing when a `voice_id` is not on the account, so echo it rather than contradicting it.

Sweeping one evaluator across several accents does not need duplicate evaluators: pass `personality_ids` on the run call instead. Details, provider pairing rules and fallback behavior: `references/voice-and-accent.md`.

## Choose → Fork → Create

Work down this list and stop at the first that fits. Creating from scratch is the last resort, not the default.

**1. Choose an existing one.** `personalities_list` with `language=<code>` (add `project_id` to scope to a project's own plus the globally available ones). Default to the plain **Normal** variant for the scenario's language — no background noise unless noise is the thing being tested. Read the candidate's `prompt` before assigning it: the name alone does not tell you how it behaves. Only assign personalities enabled for the project; if the best fit is disabled, say so and ask before enabling.

**2. Fork and patch.** When a predefined personality is close but one thing is wrong. Globally available personalities (no `project`/`organization` owner — every predefined one) are shared and **cannot be patched**; fork first.

```
personalities_fork_create   {id, project_id}     → inherits every setting, auto-enabled
personalities_partial_update {fork_id, ...}      → change only the difference
```

A fork also gives you a readable voice: a globally available personality reports its `voice_id` as the placeholder `vocera_voice_id`, so forking is how you get a predefined voice you can inspect and modify. `personalities_fork_create` accepts no overrides beyond `prompt` — always follow it with a patch.

**3. Create from scratch.** Only when nothing is close, or the language has no personality at all. Required: `name`, `prompt`, `voice_id`, `voice_model`, `background_noise`, `language`, and a `project` you can write to. Send `provider` alongside `voice_id`.

**Patching fans out.** Every evaluator already pointing at a personality picks up the change on its next run — there is no per-evaluator override. When the change should reach only some evaluators, fork first. Confirm before creating a fork the user did not ask for; it is a new resource in their workspace.

## What a Personality Controls

Everything here is call-wide and unreachable from evaluator instructions.

| Setting | Controls | Notes |
|---|---|---|
| `voice_id` + `provider` | How the caller sounds, including its accent | The only accent lever. `11labs` or `cartesia` |
| `voice_model` | Synthesis model | Must match the provider |
| `language` | What the caller speaks, and which transcriber runs | Pick this **first**; it is coupled to the evaluator's `scenario_language` and the API rejects a mismatch. `multi` for code-switching |
| `speed` | Speaking rate, `0.8`–`1.2` | |
| `interruption_level` | `off` / `low` / `medium` / `high` | A preset that **overwrites** manual start/stop speaking plans in the same request |
| `start_speaking_plan`, `stop_speaking_plan` | Fine-grained turn timing | Use instead of a preset, not alongside one |
| `message_plan` | Idle behavior — `idle_timeout_seconds` (default 10), `idle_message_max_spoken_count` (default 3) | Cannot be switched off; raise the timeout past the expected silence |
| `background_noise` | `off`, `office`, or any public audio URL | Noise is a deliberate test condition, never a default |
| `background_sound_volume` | Noise level, base and reduced-during-speech | |
| `voice_volume` | Caller speech volume, provider-independent | Reach for this for "quiet caller" tests |
| `network_simulation` | Packet loss, jitter, latency | Degraded-line testing |
| `prompt` | The caller's persona and tone for the whole call | Word choice and attitude — **not** pronunciation |

`gender` is also derived from the chosen voice, like `accent` — it is not an input.

## Creation Workflow

1. **Establish the language first.** Personalities are language-specific and the evaluator's `scenario_language` must match. Wrong language ⇒ wrong pronunciation, or a rejected evaluator.
2. **Decide whether a personality is even the answer.** Re-read the boundary table. A one-moment behavior belongs in the evaluator.
3. **List what already exists** — `personalities_list` with `language`. Prefer choosing, then forking.
4. **Resolve the voice** — for any accent, gender or timbre requirement, look it up in a voice catalog and take the id. Never invent a `voice_id`.
5. **Write the persona `prompt`** — who the caller is and how they behave. Keep voice mechanics out of it; those are fields.
6. **Create or patch**, sending `voice_id` with `provider`.
7. **Verify by reading back** — `personalities_retrieve` on the new id. Confirm `accent` and `gender` came out as expected; a blank `accent` on an ElevenLabs voice means the label was not published, and on Cartesia it is always blank.
8. **Assign and run.** Attach the id to evaluators, or pass `personality_ids` on the run to sweep without editing them.
9. **Report the id and link** — `https://dashboard.cekura.ai/personality/edit/<id>`.

## Common Pitfalls

- **Writing voice behavior into instructions.** Accent, interruption, volume, silence, noise: instructions cannot touch any of them, and the run still passes. Always the personality.
- **Trying to set `accent`.** It is derived and read-only. Change the voice instead.
- **Faking an accent in the `prompt`.** Changes word choice, not pronunciation; leaves the personality mislabelled.
- **Sending `voice_id` without `provider`.** The id is not validated against a catalog and the derived `accent`/`gender` come back blank.
- **Mismatching provider and `voice_model`.** `eleven_*` needs `11labs`; `sonic-3.5` needs `cartesia`.
- **Patching a shared personality to fix one evaluator.** It fans out to every evaluator using it. Fork.
- **Trying to patch a predefined personality.** Globally available ones are read-only. Fork, then patch the copy.
- **Inventing a personality name.** Use ids returned by `personalities_list`. If nothing fits, fork or create — but never assign a name the API never gave you.
- **Picking a noisy or interruptive variant as the default.** Both are deliberate test conditions. Baseline is plain Normal for the language.
- **Setting `interruption_level` and a manual speaking plan in one request.** The preset wins and silently discards the manual values.
- **Reaching for a personality for a single interruption.** One interruption is an evaluator condition; a call-wide habit is a personality.

## Next Steps

After this skill, the user typically needs:

- `cekura-eval-design` — write the evaluators this personality will run, and assign it
- `references/voice-and-accent.md` — voice catalogs, provider pairing, accent sweeps, language/transcriber coupling
- `references/personality-vs-evaluator.md` — the full symptom → cause → fix routing table



---

## Appended reference — personality-vs-evaluator.md

# Personality vs. Evaluator vs. Metric

## Why this matters

These three are the only places test behavior can live, and they do not overlap. Putting a request in the wrong one is the most expensive mistake in Cekura, because **it does not error**. The evaluator runs, the report comes back green, and the thing the user asked for never happened. They then debug their agent's prompt for a behavior the test never exercised.

| | Personality | Evaluator | Metric |
|---|---|---|---|
| Question | Who is calling, and how do they sound? | What are they trying to do? | Did the call go well? |
| When it applies | As the call is dialled | Turn by turn during the call | After the call ends |
| Reusable across | Many evaluators | Many runs | Many calls |
| Tools | `personalities_*` | `scenarios_*`, `test_profiles_*` | `metrics_*` |

## Routing by duration, not by wording

The deciding question is never *how the user phrased it* — it is **how long the behavior lasts**.

| Request | Goes to | Why |
|---|---|---|
| "Caller has a thick Scottish accent" | Personality (`voice_id`) | Every syllable of the call |
| "Caller is impatient and cuts in constantly" | Personality (`interruption_level`) | A habit, not an event |
| "There's constant street noise" | Personality (`background_noise`) | Environmental, call-wide |
| "Caller speaks slowly and simply" | Personality (`speed` + `prompt`) | Consistent speech pattern |
| "Caller is on a terrible connection" | Personality (`network_simulation`) | Line condition |
| "Caller is barely audible" | Personality (`voice_volume`) | Not a thing they say |
| "Caller goes quiet for 30s waiting for the agent" | Personality (`message_plan.idle_timeout_seconds`) or a `<hold>` step | The idle prompt fires regardless of instructions |
| "At step 4 the caller gets frustrated" | Evaluator instructions | One moment |
| "Caller interrupts once to ask about the wait" | Evaluator condition | A single event |
| "Caller says this in a panicked tone" | Evaluator instructions | One utterance |
| "Caller refuses to give their DOB until pushed" | Evaluator instructions | Task logic |
| "Agent must never quote a price" | Metric | A judgement on the finished call |
| "Score how natural the agent sounded" | Metric | Post-call scoring |

Rule of thumb: **if removing it would change how the caller sounds on every single turn, it is a personality.** Otherwise it is an evaluator step or a metric.

## Symptom → cause → fix

Users report all of these as agent problems or evaluator problems. Every one is a personality setting.

| Reported | Actual cause | Fix |
|---|---|---|
| "The testing agent keeps asking 'are you still there?' mid-test" | Idle timeout (default 10s) | Raise `message_plan.idle_timeout_seconds` on a personality the org owns |
| "I told it to stay silent and it talks anyway" | Idle prompt fires regardless of instructions | Same — or a `<hold time="Xs" />` step for a bounded, scripted pause |
| "It talks over my agent" | Interruption preset | Lower `interruption_level` |
| "It never lets my agent finish a sentence" | Interruption preset | Same |
| "It speaks too fast" | `speed` | Patch `speed` |
| "Wrong accent" / "it sounds American, I need Indian" | `voice_id` | Different voice — see `voice-and-accent.md` |
| "The accent field says British but it sounds American" | `accent` was set by hand before it became derived | Re-patch `voice_id`; the label re-derives from the voice |
| "I set accent to Indian and nothing changed" | `accent` is a derived label, not a knob | Pick an Indian-accented voice |
| "There's no background noise" | `background_noise` is `off` | Set it, or pick a Bg Noise variant |
| "My agent can hear it fine — I wanted a hard-to-hear caller" | `voice_volume` | Lower it |
| "The call sounds too clean for a mobile test" | No `network_simulation` | Enable packet loss / jitter / latency |
| "It read the phone number as words" | Language / voice model mismatch | Fix `language`, then the voice |
| "My multilingual test only speaks English" | Personality is single-language | Use a `language=multi` personality |

**Never** propose an Agent Description or evaluator-instruction edit as the fix for any row in this table. Those surfaces cannot reach the voice layer, so the attempt always fails silently — and it teaches the user that the platform is unreliable rather than that the setting lives elsewhere.

## When the fix is an evaluator change after all

Not everything that *sounds* like a voice problem is one:

- "It asked for the account number before verifying identity" — evaluator turn order.
- "It hung up before the transfer completed" — the evaluator's end-call tool choice (`TOOL_END_CALL_ONLY_ON_TRANSFER`).
- "It gave up after one rejection" — evaluator instructions; persistence is task logic.
- "It said it was a new patient but the profile says established" — test profile data.

The tell: these are all about *content and sequence*. If you can describe the fix as words the caller should or shouldn't say, it is an evaluator.

## Ownership and blast radius

- A personality with no `project`/`organization` owner is **globally available** — shared across all organizations and not editable. Fork it into the project first.
- Patching a personality the org owns affects **every evaluator already using it**, on the next run. There is no per-evaluator override. Fork when the change should be narrow.
- A per-run override exists for sweeps only: `personality_ids` on the run call swaps the personality for that run without touching any evaluator.
- Confirm before creating a fork the user did not ask for — it is a new resource in their workspace.



---

## Appended reference — voice-and-accent.md

# Voice, Accent and Language

## The rule

The testing agent's speech is synthesised from `voice_id` + `provider`. That pair decides the accent, the timbre and the gender. Everything else — `speed`, `voice_volume`, `background_noise` — modifies audio that has already been generated by that voice.

`accent` and `gender` are **read-only labels derived from the chosen voice**. They are absent from the write tools' inputs. There is no field, prompt, instruction or metric that can give a voice an accent it does not have.

## Resolving an accent to a voice

```
1. personalities_elevenlabs_voices  {language: "en"}     # or personalities_cartesia_voices
2. pick the voice whose accent matches                    # ElevenLabs: labels.accent
3. personalities_create / personalities_partial_update
   { voice_id: "<id from step 2>", provider: "11labs", voice_model: "eleven_turbo_v2_5", ... }
4. personalities_retrieve {id}                            # confirm the derived accent label
```

### What each catalog gives you

| | `personalities_elevenlabs_voices` | `personalities_cartesia_voices` |
|---|---|---|
| Accent | `labels.accent` — an explicit label to match on | Not published; infer from `name` + `description` |
| Gender | `labels.gender` | `gender` |
| Also carries | `labels.age`, `labels.use_case`, `preview_url` | `language`, `description`, `preview_file_url` |
| Filter | `language` | `language` |

**When a test targets a *named* accent, prefer ElevenLabs** — it is the only provider here that labels one, so it is the only one whose derived `accent` will be populated. A Cartesia voice still speaks with an accent; the platform just has no label for it, which is why `accent` comes back empty. Empty never means "neutral".

Never invent or guess a `voice_id`. An id absent from the provider's catalog is rejected at create time when `provider` is present — and silently stored when it is not.

## When the catalog has nothing suitable

**Never report an accent, language or voice as unsupported.** The catalog is what is wired up today, not a product limit: Cekura adds voices on request. When nothing matches what the user asked for:

1. Say which available voice is closest, and offer to use it meanwhile.
2. Point them at **support@cekura.ai** or their dedicated Slack support channel to get the voice they want added, naming the accent/language/timbre so support has something actionable.

The API is already worded this way — a `voice_id` that is not on the account is rejected with a message inviting the user to contact support — so telling them it cannot be done contradicts the platform.

## Provider pairing

| `provider` | Valid `voice_model` | Notes |
|---|---|---|
| `11labs` | `eleven_multilingual_v2`, `eleven_turbo_v2_5`, `eleven_flash_v2_5`, `eleven_v3_conversational` | Multilingual models handle any supported language |
| `cartesia` | `sonic-3.5` | Only provider that supports `generation_config` (emotion, native volume) and `<break time="…"/>` in the persona prompt |

Send `voice_id` and `provider` in the same request, always. `provider` selects the catalog the id is validated against; without it, the id is not checked and the derived `accent` and `gender` are left blank. Mismatching the pair (an `eleven_*` model with `cartesia`) produces a broken voice config.

A cross-provider fallback voice is attached automatically, so a provider outage degrades the voice rather than failing the call — which also means the accent under fallback is not the one you chose. Judge accent results from clean runs.

## Language comes first

`language` is not cosmetic — it selects the transcriber that will read the main agent's speech, and it is **coupled to the evaluator's `scenario_language`**. The API rejects a mismatch; do not try to work around it.

- Pick the language, then pick the voice within that language, then the tone.
- Dialects are distinct. Brazilian vs. European Portuguese, Latin American vs. Castilian Spanish — match the region the agent serves.
- Code-switching in one call → a `language=multi` personality. Semantic matches count: "Hinglish" → Hindi + English, "Spanglish" → Spanish + English.
- No `multi` personality available → fall back to the dominant non-English language's Normal personality (its voice model usually carries the English parts) and say so in the summary.
- If no personality exists for the language at all, create one — a multilingual voice model covers any supported language.

## Accent sweeps

To measure the same workflow across several accents, do **not** duplicate evaluators. Create one personality per accent variant, then pass `personality_ids` on the run call: every selected evaluator runs once per personality, and the results land in one report.

Keep the evaluator instructions and expected outcomes byte-identical across the sweep — otherwise you are comparing prompts, not accents.

Pair the sweep with the **Transcription Accuracy** predefined metric. It scores how badly the testing agent's speech was transcribed, weighting names, nouns and numbers most heavily, so a low score under one accent personality points straight at an STT weakness for that accent rather than a logic bug.

## Audio conditions layered on top of the voice

| Setting | Use for | Notes |
|---|---|---|
| `speed` | Slow, deliberate or hurried callers | `0.8`–`1.2` |
| `voice_volume` | "The agent can't hear me" tests | Provider-independent scaling applied after synthesis, so it reaches far quieter levels than Cartesia's native volume. Setting it clears any native `generation_config.volume` so the ratio is never applied twice |
| `background_noise` | Ambient realism | `off`, `office`, or a direct public audio URL for anything else — including recordings with voices in them |
| `background_sound_volume` | How loud that noise sits | `base` (also sets the normal level) and `reduced` (during caller speech), `0.0`–`1.0` |
| `network_simulation` | Poor mobile / VoIP lines | Packet loss, jitter, latency |
| `generation_config` | Cartesia emotion and native volume | Cartesia + `sonic-3.5` only |

Noise, quiet speech and network impairment are deliberate test conditions. None of them belong on a baseline personality — a suite whose happy path runs under café noise cannot tell a real regression from a bad line.
