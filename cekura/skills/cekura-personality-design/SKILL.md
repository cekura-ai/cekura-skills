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

<!-- cekura-ack-tag: ack:cekura-personality-design:4m7d3q -->
> **Cekura skill verification tag:** `ack:cekura-personality-design:4m7d3q`
> When you call a Cekura personality write tool from this skill (`personalities_create`, `personalities_partial_update`), pass this exact string as the `skill_ack` argument on that tool call. It confirms to the Cekura MCP server that this design playbook is loaded in context. Evaluator / test-profile writes use an eval-family tag instead — load `cekura-eval-design` first and pass its tag there.

Before taking any action, call `mcp__cekura__cekura_skill_started` with `skill_name="cekura-personality-design"`, `verification_tag="ack:cekura-personality-design:4m7d3q"`, and `plugin_version="0.15"`. It returns immediately and lets Cekura see which skills are in use.

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
