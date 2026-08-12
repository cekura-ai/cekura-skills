---
name: cekura-generate-scenarios
description: |
  Turn a set of flagged production call logs into evaluator scenarios for
  a Cekura agent — cluster the failures into reproducible modes and create
  one scenario per cluster. Use when the user says "create scenarios from
  failed calls", "build evaluators for prod failures", "turn call logs into
  scenarios", "simulate the failures we saw in prod", "replay these bad
  calls as tests", "regression-test the agent on prod issues", or hands over
  a set of flagged call IDs to harden the agent against. The flagged set
  normally comes from `cekura-flag-call-log-failures`; if the user hasn't
  triaged yet, run that skill first. This skill takes the flagged calls as
  given — it does NOT re-mine or re-triage — clusters by failure mode,
  drafts one scenario per cluster, and optionally creates them via the
  scenarios API (or the call-logs → scenarios endpoint). Also supports a
  single-call fast path: given one call log ID (or an observe URL),
  reproduce just that call as one evaluator scenario.
license: MIT
compatibility: Requires a Cekura account (https://dashboard.cekura.ai) — sign in via OAuth or use an API key.
allowed-tools: AskUserQuestion Bash Read Write Edit Grep Glob Skill mcp__cekura__cekura_skill_started
metadata:
  author: cekura
  version: "0.4.0"
---

<!-- cekura-ack-tag: ack:cekura-generate-scenarios:7q3n6v -->
> **Cekura skill verification tag:** `ack:cekura-generate-scenarios:7q3n6v`
> When you call a Cekura scenario or test-profile write tool from this skill (`scenarios_*` / `test_profiles_*` create and update calls), pass this exact string as the `skill_ack` argument on that tool call. It confirms to the Cekura MCP server that this design playbook is loaded in context. Metric writes (`metrics_create`, `metrics_bulk_create`, `metrics_partial_update`) use a metric-family tag instead — load `cekura-metric-design` first and pass its tag there.

Before taking any action, call `mcp__cekura__cekura_skill_started` with `skill_name="cekura-generate-scenarios"`, `verification_tag="ack:cekura-generate-scenarios:7q3n6v"`, and `plugin_version="0.10.8"`. It returns immediately and lets Cekura see which skills are in use.

# generate-scenarios

Convert real production failures into evaluator scenarios so the next regression run catches them. Signal is mined from **call logs** — what real callers did, where the agent broke, and what the right behavior would have been. Every scenario produced traces back to at least one call log; nothing is invented.

This skill is **read-first**: it never creates a scenario without an explicit user OK on the proposed set.

## Write path — decided by `scenario_type`, not by preference

| `scenario_type` | Write path |
|---|---|
| `conditional_actions` — drop, tool_error, workflow_miss (turn-by-turn replays) | `mcp__cekura__scenarios_create` with the drafted `conditions`. The generation endpoints **cannot emit conditional actions**; direct create is the only path. |
| `instruction` — drift, hallucination, comprehension, refusal, safety (free-form) | **Generate:** `mcp__cekura__call_logs_create_scenarios` (preferred — grounded in the evidence calls) or `scenarios_generate_bg`, passing the drafted `expected_behavior` + failure mode as `extra_instructions`. Behavioral instructions are never hand-authored. |

A mixed report takes **both** paths in one pass; say which clusters went which way in the summary. The only reason to hand-author an `instruction` scenario is that the user dictated its text themselves.

## Step 0 — Prerequisites

This skill reads + writes through the Cekura MCP. Confirm these tools are present before starting:

- `mcp__cekura__aiagents_retrieve` — agent description, language, scenario defaults, tool wiring
- `mcp__cekura__call_logs_retrieve` — transcript, metric evaluations, ended_reason for each flagged call (to build the replay)
- `mcp__cekura__scenarios_list` — existing scenarios on the agent (dedup)
- `mcp__cekura__scenarios_create` — single-scenario create
- `mcp__cekura__scenarios_partial_update` — attach the test profile to the scenario after both exist
- `mcp__cekura__scenarios_create_from_transcript` — turn a single call transcript into a scenario
- `mcp__cekura__call_logs_create_scenarios` + `mcp__cekura__call_logs_create_scenarios_progress` — bulk path: hand a set of call log IDs to the platform and let it generate scenarios server-side
- `mcp__cekura__scenarios_generate_bg` + `mcp__cekura__scenarios_generate_progress` — alt bulk path via free-form `extra_instructions`
- `mcp__cekura__test_profiles_create` — create a test profile carrying the cluster's dynamic-variable values
- `mcp__cekura__personalities_list` — pick a matching caller personality per cluster
- `mcp__cekura__metrics_list` — find an existing metric to reuse on the scenario (single-call fast path)
- `mcp__cekura__predefined_metrics_list` — **browse the shared catalog of predefined metric templates BEFORE authoring a new metric** (single-call fast path). Read-only, platform-wide.
- `mcp__cekura__predefined_metrics_copy_create` — copy a matching predefined metric into the project/agent instead of writing one from scratch
- `mcp__cekura__metrics_create` — create a focused pass/fail metric for the reproduced failure — **only when no existing or predefined metric fits** (single-call fast path)

If the `mcp__cekura__*` tools are not connected, stop and tell the user to connect the Cekura MCP (see `/setup-mcp` or https://docs.cekura.ai/mcp/overview).

## Metric selection policy — reuse before you create (applies to every scenario)

Whenever a scenario needs a metric to grade the failure, resolve it in this order. **Creating a brand-new metric is the LAST resort, not the default.** A duplicate "Voicemail Detection Accuracy" / "No Premature Transfer" metric that already exists as a predefined template just clutters the project and drifts from the platform-maintained version.

1. **Reuse an existing metric on the agent/project.** `mcp__cekura__metrics_list(agent_id=..., project_id=...)`. If one already scores the same behavior, attach it by ID — don't make another.
2. **Check the predefined catalog.** `mcp__cekura__predefined_metrics_list` returns the shared, platform-maintained metric templates (e.g. CSAT, Sentiment, Dropoff Node, Topic of Call, Voicemail Detection, Latency, and many workflow/safety checks). **Search the Cekura docs for the predefined list first** so you match the failure to a known template by name/intent:
   - Concept + full catalog: <https://docs.cekura.ai/documentation/key-concepts/metrics/pre-defined-metrics>
   - Browse via CLI/SDK: <https://docs.cekura.ai/cli-sdk/metrics#browse-predefined-metrics>
   - API reference: <https://docs.cekura.ai/api-reference/test_framework/list-predefined-metrics>

   If a predefined metric matches the cluster's failure mode, **copy it into the project/agent** with `mcp__cekura__predefined_metrics_copy_create` (it lands as an editable copy you can tighten) instead of writing a new prompt. Note predefined/LLM-judge metrics cost 0.2 credits per evaluation.
3. **Author a new metric only if neither fits.** `mcp__cekura__metrics_create` (`type=llm_judge`, appropriate `eval_type`, `project=<id>`, `agents=[<agent_id>]`) with a PASS/FAIL description grounded in the call's failure and citing the call ID.

Record which path was taken for each scenario in the report (`reused #<id>` / `copied predefined "<name>"` / `created new`) so the user sees the metric isn't a silent duplicate.

## Step 1 — Identify the target agent and the flagged call set

Use `AskUserQuestion` if not already supplied:

1. **Agent ID** on Cekura (numeric, e.g. `12345`). If unknown, use `mcp__cekura__aiagents_list` to help find it.
2. (Optional) **Project ID**, if the user manages multiple projects.
3. **The flagged call set** — the calls these scenarios should reproduce. This skill does **not** mine or triage call logs itself; it expects a flagged set, normally one of:
   - The output of **`cekura-flag-call-log-failures`** — a list of `{call_log_id, issue/mode, severity, evidence_quote, expected_behavior}`. Each entry already has the per-call failure record this skill needs; go straight to clustering (Step 4).
   - A **user-supplied list of call IDs** ("build scenarios from calls 801, 802, 803"). Retrieve each with `mcp__cekura__call_logs_retrieve` and read its transcript to recover the same per-call record before clustering.

   **If the user wants scenarios from "the failures in prod" but hasn't triaged yet, run `cekura-flag-call-log-failures` first** to produce the flagged set, then continue here. Don't re-implement triage.

Do not proceed until the agent ID is confirmed. If the user pasted a `dashboard.cekura.ai/<project>/observe/<call_log_id>` URL for a single call, use the single-call fast path below.

**Single-call mode.** If the user supplies a specific **call log ID** (or an observe URL) and wants a scenario from *that* call — wording like "create a scenario for call log 9876543", "turn this call into an evaluator", "replay this call" — skip clustering (Step 4) and use the **Single-call fast path** below. You still need the agent context from Step 2a (agent description, dynamic-variable names, personalities, existing scenarios for dedup) and the `tool_ids` rules from Step 4. Confirm which agent the scenario should run against — it can differ from the agent that produced the call.

## Single-call fast path — one call ID → one scenario

Use this when the user wants a scenario reproduced from **one specific call** (not a flagged set). It skips clustering (Step 4) but keeps the read-first rule: draft → confirm → create. Still pull agent context (Step 2a) and obey the `tool_ids` rules (Step 4).

### A. Retrieve the call

`mcp__cekura__call_logs_retrieve(id=<call_log_id>)`. Capture `transcript_object`, `call_ended_reason`, `success`, `duration`, `metadata` (caller identity + enrollment state), and any `metric_evaluations`. Read the whole transcript — a single call is usually about ONE thing.

### B. Pin the focal failure

Identify the **failure point** — the turn where the agent did the wrong thing — using the failure-mode taxonomy in `cekura-flag-call-log-failures` (or the user-stated issue). Record the verbatim `evidence_quote` and a one-sentence `expected_behavior` (→ becomes `expected_outcome_prompt`). If the call clearly contains several distinct failures, ask the user which one to target; don't silently fold them into one scenario.

### C. Build a faithful replay (`conditional_actions`)

Walk the caller's path **turn-by-turn in the same order the real call took**, up to and through the failure point: identity → screening → … → the failing step. Each condition is `{condition: "<observable thing the agent does>", action: "<what the caller says>", fixed_message}`.

- **Anchor the failure.** The condition right before the failure must set it up exactly (the caller corrects a mis-heard value / declines an offer / mentions a medication / says the ambiguous phrase). Add an explicit condition for the FAIL branch (e.g. "the agent says it is transferring you to a human", "the agent ends the call") with a benign caller line, so the metric has a concrete signal to grade against.
- **`fixed_message` choice (this bites):**
  - `true` for values that must be reproduced verbatim — DOB, ZIP, the literal trigger phrase ("Speak to me", "Can I talk to somebody?"), a mis-stated-then-corrected number.
  - `false` (the action text becomes an **instruction the caller paraphrases**) for turns that must **adapt to what the agent offers** — e.g. *"Pick ONE of the specific times the agent offers (the earliest) and name it clearly."* A `fixed_message: true` reply that doesn't actually choose ("that works, thank you") makes the agent re-ask the same question forever — a known slot-selection loop failure. When the agent presents choices, the caller MUST commit to one concrete option.
  - **`FIRST_MESSAGE` (id 0) MUST stay `fixed_message: true`** (API rejects otherwise). For outbound calls (agent speaks first) set its action to `""`.
- **Always include the end-call tool in `tool_ids`** — it's a hard always-on rule for every scenario (Step 4). End the success path with `<endcall />` in the final action; the `<endcall />` marker is a no-op unless that tool is wired in.
- **Never append `<silence>` (or `<hold>`) tags at the END of an action.** Those SSML pause tags are only for *mid-utterance* pacing (a beat inside a sentence). Trailing them on the end of a line — e.g. `"...thanks <silence time="1.0s" /> <endcall />"` or as the caller's last token — just injects dead air and serves no purpose. End actions on the spoken words; if the turn closes the call, the final action ends with `<endcall />` directly (no preceding `<silence>`). Do not pad actions with trailing silence by default.

(For free-form calls — hallucination/drift/refusal, where the caller needs latitude — the scenario is `scenario_type: instruction` instead, and per **Write path** above it must be **generated**, not hand-written: skip C and use `mcp__cekura__call_logs_create_scenarios` with this one `call_log_id`, or `scenarios_generate_bg` with `num_scenarios: 1` and the focal failure + expected behavior as `extra_instructions`. Then attach the test profile, metric, and phone per D–F exactly as below.)

### D. Caller identity → test profile (camelCase keys — load-bearing)

Pull the caller's identity from `metadata` (provider metadata blocks (`*_data`)) and the transcript: name, DOB, ZIP, address, medications, etc. Create a test profile (`mcp__cekura__test_profiles_create`, `agent=<agent_id>`) whose `information` carries these as **dynamic variables**.

- **Key casing matters.** These squads reference variables in **camelCase** (`{{firstName}}`, `{{lastName}}`, `{{dateOfBirth}}`, `{{zipCode}}`, `{{fullAddress}}`) — and that's the casing production injects. A profile that only sets lowercase `firstname`/`zipcode` leaves `{{firstName}}`/`{{zipCode}}` **unresolved at runtime** — the agent greets "Am I speaking with `{{firstName}}`?", and tool calls send the literal string `{{zipCode}}` (which the backend rejects). **Set BOTH camelCase and lowercase keys** for every identity field so the prompt resolves regardless of which casing it uses. When `agent_dynamic_vars` (Step 2a) is known, match those names exactly.
- Keep values consistent with the conditional actions — if the caller says "123 Maple Street", the profile's `street`/`fullAddress` must say 123 Maple Street.

### E. Metric

Score the specific behavior. Follow the **Metric selection policy** above — resolve in order: (1) reuse an existing metric on the agent (`mcp__cekura__metrics_list(agent_id=...)` — e.g. an existing "Voicemail Detection Accuracy" / "No Premature Transfer…"); (2) if none fits, check the predefined catalog (`mcp__cekura__predefined_metrics_list`, after searching the [predefined-metrics docs](https://docs.cekura.ai/documentation/key-concepts/metrics/pre-defined-metrics)) and **copy** a matching template with `mcp__cekura__predefined_metrics_copy_create`; (3) only if neither fits, **create** one (`mcp__cekura__metrics_create`, `type=llm_judge`, `eval_type=binary`, `project=<id>`, `agents=[<agent_id>]`) whose description spells out PASS/FAIL grounded in the call's failure and cites the call ID.

### F. Create (after user OK)

1. **Scenario** — this is the `conditional_actions` replay built in C, so it takes the direct-create path: `mcp__cekura__scenarios_create` with agent, `name` ("<failure> (from call <id>)"), **explicit `scenario_type: "conditional_actions"`** (omitting it defaults to `instruction` and the `conditions` are ignored), `personality` (Step 4 heuristics), `metrics=[<metric_id>]`, `folder_path` (if the user named a folder), `expected_outcome_prompt`, `conditions`, `tags=["replay-<call_id>", "<mode>"]`, testing-agent `tool_ids`. If the focal failure was free-form instead (the `instruction` case flagged at the end of C), you generated the scenario there — skip to step 2 and attach to the returned scenario.
2. **Test profile** — `mcp__cekura__test_profiles_create` with the camelCase+lowercase identity dict; capture the id.
3. **Attach the profile** — `mcp__cekura__scenarios_partial_update(id=<scenario_id>, test_profile=<profile_id>)`. The runtime only reads dynamic variables from the attached profile, not the scenario's own `dynamic_variable_values`.
4. **Attach the evaluator phone** for phone/outbound agents — set the scenario's phone number (e.g. via `scenarios_partial_update`). The create call may not persist it, so **read the scenario back and PATCH if the phone is null.** (Look up the organization's configured evaluator inbound-phone-number ID and use that.)
5. **Verify** — read the scenario back and confirm `test_profile_data`, `metrics`, `folder_path`, and the phone are all set.

Print the `https://dashboard.cekura.ai/test-case/<scenario_id>` link and recommend running it once to confirm the agent still fails (the replay reproduces the bug).

### Alternative: platform transcript path

To let the platform draft from the raw transcript instead, `mcp__cekura__scenarios_create_from_transcript(agent=<agent_id>, call_log_id=<id>, extra_instructions=<focal failure + expected behavior>)`. Lower control over wording; still attach a test profile (camelCase keys) + metric + phone afterward per D–F. This endpoint can be slow — if it times out, fall back to the `conditional_actions` build in C.

## Step 2 — Gather signal

Run these fetches in parallel.

### 2a. Agent context + existing scenario coverage

Call `mcp__cekura__aiagents_retrieve(id=<agent_id>)` and capture:

| Field | Used for |
|---|---|
| `agent_description` | Intent — what the agent is *supposed* to do (defines what counts as a failure) |
| `agent_name`, `project_id` | Report header, scenario creation scope |
| `scenario_type` default | Pick `instruction` vs `conditional_actions` per cluster |
| `scenario_language` / `language` | Required field on new CA scenarios |
| `inbound`, `contact_number`, `outbound_numbers` | Direction matters for the scenario's `first_message` choice |
| `tool_ids` / tool wiring | Mirror the agent's available tools in scenarios that need them |
| `assistant_provider` | Affects test-profile importance — see "Dynamic variable placeholders" below |

### Dynamic variable placeholders (REQUIRED for ElevenLabs, recommended elsewhere)

Scan `agent_description` (and `llm_system_prompt` if non-empty) for `{{variable_name}}` placeholders — these are dynamic variables the agent expects at call time. Collect the unique names into `agent_dynamic_vars: set[str]`.

**Why it matters:** the Cekura outbound-call trigger reads dynamic variables from `test_profile.information` — NOT from `scenario.dynamic_variable_values`. If a scenario references `{{first_name}}` etc. but has no attached test profile, ElevenLabs rejects the conversation with `termination_reason: "Missing required dynamic variables in first message"` and the call drops in < 1s with `call-not-connected`. The scenario will never run successfully without a test profile.

**Hard rule:** if `agent_dynamic_vars` is non-empty AND `assistant_provider == "elevenlabs"`, every scenario this skill creates MUST get a test profile attached in Step 6. For other providers (vapi, retell, bland, livekit) the variables are also injected at runtime but typically don't hard-fail when missing — still recommended to attach a profile so the agent has values to work with.

Call `mcp__cekura__scenarios_list(agent=<agent_id>)` to enumerate existing scenarios on the agent — used for dedup (don't propose a scenario that already exists; flag near-duplicates).

Call `mcp__cekura__personalities_list(project_id=<project_id>)` so you have personality IDs ready to attach in Step 4. At minimum capture a `Normal` male/female personality in the agent's language plus any `Frustrated` / `Confused` / `Interruptive` ones — clusters will map to these.

**If `agent_description` is missing or weak (< 2 sentences, placeholder, lorem ipsum), STOP and surface:**

> ⚠️ The agent's `agent_description` is empty / very short. Without it, "failure" is ungrounded — we can't tell drift from working-as-intended. Please flesh out the description (workflows, audience, must-not-do list) before continuing — or confirm you want to proceed using ended_reason + metric_evaluations as the only failure signal.

Only continue once description issues are resolved or the user explicitly opts to proceed on outcome signal alone.

## Step 3 — The flagged call set (input)

This skill does **not** classify or triage calls — that is `cekura-flag-call-log-failures`' job. By the time you reach this step you have a **flagged set**, each entry carrying:

`{ call_log_id, mode/issue, severity, evidence_quote, expected_behavior }`

- **From `flag-call-log-failures`:** use the records as-is. That skill has already applied the attribution rules (caller-side endings, recovered calls, and legitimate early exits are excluded), so every flagged call is an agent-attributable failure — don't re-filter or second-guess the set.
- **From a user-supplied list of call IDs:** fetch each with `mcp__cekura__call_logs_retrieve(id=...)`, read the transcript, and build the same record yourself — pin the failure turn, capture a **verbatim** `evidence_quote` (no paraphrasing — if you can't quote it, it isn't a failure), and a one-sentence `expected_behavior` grounded in `agent_description`. Apply the same attribution sanity-check: if a "failure" was really the caller hanging up, or a call the agent recovered from, drop it. (If the user wants this done at scale across a window rather than a hand-picked list, that's `flag-call-log-failures` — run it first.)

`expected_behavior` becomes the scenario's `expected_outcome_prompt`; `mode` drives `scenario_type` + personality (see the **Quick reference — failure modes** at the bottom, and `flag-call-log-failures` for the full taxonomy + detection signals). A single call may carry several flagged issues — treat each as its own record going into clustering.

## Step 4 — Cluster into scenarios

Group the per-call failures into **scenario clusters**. Aim for **3–8 scenarios total** (one per distinct failure pattern). Heuristics:

- Same `mode` + same workflow context → one cluster (e.g. three hallucinations all about pricing → one "Pricing hallucination" scenario).
- Same `mode` but unrelated contexts → split (e.g. tool errors on `lookup_balance` and `schedule_appointment` are two clusters).
- Different `mode`s on the same workflow → split (a drop AND a tool error during the same booking flow are two scenarios; the personality and trigger differ).
- Don't over-split — if you have one call per cluster after grouping, you have too many clusters. Merge until each has ≥ 2 evidence calls OR the cluster represents a clearly critical-but-rare failure (e.g. a single PII leak).

For each cluster, draft a scenario spec:

```
{
  cluster_id: C1,
  name: <short title — "Caller asks about refund eligibility — agent hallucinates window">,
  mode: hallucination,
  scenario_type: instruction | conditional_actions,
  personality_id: <from personalities_list — pick one that matches caller behavior in the cluster>,
  scenario_language: <from agent>,
  first_message: <verbatim opener from one of the evidence calls, or empty if agent speaks first>,
  instructions: <only if scenario_type == instruction — the testing-agent's prompt: caller's persona, goal, what they will push on>,
  conditions: <only if scenario_type == conditional_actions — list of {condition, action, fixed_message} that walks the failure path>,
  tool_ids: <testing-agent tool refs (NOT agent-under-test tools) — usually end_call when the testing agent must hang up; see "Picking `tool_ids`" below>,
  expected_outcome_prompt: <one sentence — the right behavior the agent must demonstrate to pass>,
  dynamic_variable_values: <dict — one entry per name in agent_dynamic_vars (from Step 2a); see "Picking dynamic-variable values" below>,
  evidence: [{call_log_id, mode, quote}, ...]  // 2-5 calls per cluster, max
}
```

### Picking dynamic-variable values

For every name in `agent_dynamic_vars`, pick a value that's *consistent with the cluster's failure context*:

- **Prefer values mined from the evidence calls.** If the original call's transcript shows the customer was asking about `{{order_number}} = 4421`, reuse `4421` so the scenario reproduces the same situation.
- **For names with no transcript anchor**, pick a plausible default that matches the cluster's persona — e.g. `first_name = "Robin"`, `last_name = "Thompson"` for a generic patient persona. Do not leave any required variable blank — empty strings still fail the EL "missing variables" check on some providers.
- **For workflow scenarios that reference an external entity** (a doctor name, an account ID), make sure the value used in `dynamic_variable_values` is the SAME value referenced inside `conditions` / `instructions` / `expected_outcome_prompt`. The scenario will mis-evaluate if the IVR confirms "Dr. Robin Thompson" while the agent was told to ask about "Dr. Smith."
- **One test profile per cluster.** Don't share a profile across clusters with different personas — small per-cluster profiles make failure diffs easy to read.

### Picking `scenario_type`

- **`instruction`** for free-form / red-teamy clusters: hallucinations, drift, refusal, comprehension, safety. The testing agent needs latitude to push. → **generated** (see **Write path**); the draft becomes `extra_instructions`.
- **`conditional_actions`** for sequential workflow clusters: workflow_miss, tool_error, drop-mid-workflow. Walk the exact failure path turn by turn. → **created directly**; generation can't emit these.

Picking the type therefore picks the write path. Don't pick `conditional_actions` for a free-form cluster just to keep control of the wording.

### Picking the personality

- `drop` after caller frustration → `Frustrated` matching language.
- `comprehension` repeats → `Confused` or `Mumbling`.
- `hallucination` where caller pressed for specifics → `Persistent` / `Inquisitive`.
- Everything else → `Normal` male or female matching the agent's language.
- **Never** pair `Interruptive` with `conditional_actions` — that pairing is a known structural issue: an interruptive caller derails the fixed turn sequence.

### Picking `tool_ids` — testing-agent tools (REQUIRED for end-of-call patterns)

`tool_ids` on a scenario is the **testing agent's** tool surface — i.e., what the simulator can do to drive the world (hang up, press DTMF, sit silently). It is NOT the agent-under-test's tool list; that's owned by the agent's own provider config (ElevenLabs `built_in_tools`, VAPI `model.toolIds`, etc.) and the scenario can't change it.

**🔴 Always-on rule — every scenario this skill generates MUST include the testing-agent end-call tool in `tool_ids`. No exceptions, regardless of cluster/flow/type.** It's harmless when never invoked and it prevents the silent-timeout failure described below. The only open question is *which* tool reference to use (resolve it per rule 4 — don't invent it), never *whether* to include it. If you can't resolve the correct end-call tool ID for the provider, ask the user before creating rather than shipping a scenario without it.

The most common silent failure of generated scenarios is omitting `end_call` on a cluster whose expected flow requires the testing agent to terminate. Symptom: the scenario hangs until the global call timeout fires (~60s+), `ended_reason` comes back as `silence-timeout` or `testing-agent-ended-call` from a wall-clock kill instead of from the intended condition, and the failure-mode metrics evaluate against a garbage trailing transcript.

**Hard rules:**

1. **If any `condition.action` contains the inline marker `<endcall />` (XML in `fixed_message`), the scenario MUST include `end_call` in `tool_ids`.** The XML marker is sugar that compiles to an `end_call` tool invocation on the testing-agent side — it's a no-op when the underlying tool isn't wired in. Same applies to `<silence time="..." />` (no extra tool, just timing) — but `<endcall />` is the foot-gun.
2. **If the cluster's `expected_behavior` reads "agent must hang up" / "agent must call end_call", the scenario MUST include `end_call` in `tool_ids`.** Reason: the run needs an authority that can force termination if the agent doesn't end, otherwise the scenario's success condition (which is "agent ended cleanly") can't be distinguished from "framework timeout fired because nobody ended."
3. **DTMF is an agent-under-test concern, not a testing-agent concern — do NOT add `play_keypad_touch_tone` to scenario `tool_ids`.** When a scenario simulates an IVR menu that the agent-under-test must navigate, the testing agent's job is to *announce the menu options in its `fixed_message`* and loop or advance based on which digit the agent presses. The agent-under-test needs `play_keypad_touch_tone` (ElevenLabs `built_in_tools.play_keypad_touch_tone`, VAPI equivalent) wired into ITS config — that's an agent-creation concern handled by `cekura-create-agent`, not this skill. If the agent under test lacks DTMF capability, surface that as a coverage gap in the report's "Recommendations" section — don't try to compensate via scenario `tool_ids`.
4. **Don't invent tool IDs.** Provider-specific values differ — VAPI uses string constants like `"VAPI_TOOL_END_CALL"`, ElevenLabs / retell scenarios reference the platform's built-in system tool by its platform ID. Read `scenarios_list` output from Step 2a — copy the exact `tool_ids` value used by any existing scenario on the same agent that successfully terminates. If no existing scenario has `tool_ids` populated and you can't resolve the ID, ask the user for the end_call tool reference before creating; do not guess.

### End the call promptly once the failure is demonstrated

Having `end_call` wired in (above) is necessary but not sufficient — the testing agent also needs to be *instructed when to use it*. **Default rule: once the failure-revealing behavior has clearly manifested in the transcript, have the testing agent wrap up and `<endcall />` as early as possible. Don't let the call keep running.**

**Why:** a tight transcript keeps the metric judge's signal clean (no noisy tail, no late recovery muddying a real failure), avoids running into the wall-clock cap (which replaces the intended `ended_reason` with a garbage `silence-timeout`), and saves minutes/credits — loop-type failures otherwise burn to the provider max duration (~20 min) on every run.

**Balance — give the failure room to manifest before ending (don't end too early):**
- Let the behavior occur enough times that the judge can distinguish a *sustained* failure from a one-off. For loop/repetition clusters, let it repeat ~2–3 times before the testing agent ends. Ending on the very first sign can make a genuine loop look like a single benign re-ask.
- Where the cluster's whole point is *does the agent recover / does the agent end on its own*, give the agent a bounded window to do so first. The testing agent's end is the **safety net that proves the agent failed to end** — so it must fire late enough that "agent never ended" is unambiguous, but still before the wall-clock timeout. Never end so early that you've pre-empted the agent's own decision to conclude (that would mask the very behavior under test).

**How to encode it:**
- **`conditional_actions` scenarios:** add a terminal condition keyed to the repeated failure behavior whose action is a brief wrap-up line ending in `<endcall />`. Use an `action_followup` chain to count "the agent did X again" a bounded number of times before firing the end. Example: `{condition: "The agent asks yet another open-ended hypothetical question (3rd+ time)", action: "Okay, I think that covers it — thanks. <endcall />", fixed_message: true}`.
- **`instruction` scenarios:** state the stop rule in plain text in the caller instructions — e.g. *"After the agent has asked roughly 5–6 of these repetitive questions, say once 'Why do you keep asking the same thing?', then end the call."* Make the threshold explicit so the simulated caller doesn't either bail immediately or ride it to the timeout.
- Either way this is independent of the always-on `tool_ids` rule: the marker/instruction is a no-op unless `end_call` is in `tool_ids`, so both must be present.

### Reproduce delivery / acoustic conditions with conditional-action tags

Many call-log failures are driven not by *what* the caller said but by *how* it was delivered — the caller spoke too faintly for the VAD/ASR to catch, there was a long pause that tripped a silence timeout, they talked over the agent, there was background noise, or the tone was emotional. **A faithful replay must reproduce the delivery, not just the words.** Conditional-action tags are how you do that. A scenario that types "yeah yeah" at normal volume will NOT reproduce a failure whose root cause was that "yeah yeah" was too quiet to register.

**Discover the available tags first — do NOT rely on memory.** The tag set evolves and several tags are Cekura-specific extensions beyond standard SSML, with provider-dependent value ranges. Before building the replay, confirm the current tags + exact syntax by:
1. **`mcp__cekura__search_cekura("conditional action tags")`** (and related queries like "volume tag", "silence tag") — the Cekura docs are the source of truth, especially for the volume tag and its valid range.
2. **Reading `conditional_actions` of existing scenarios on the same agent** (already pulled in Step 2a) — copy tag syntax that already works in this org/provider rather than guessing.

**Known tags — map the call-log condition to the tag (verify syntax via docs before use):**

| Real call-log condition (root cause) | Tag | Notes |
|---|---|---|
| Caller speaks faintly / low volume → VAD or ASR misses the turn | `<volume ratio="X" />` at the **start** of the action | Cekura volume tag. Ratio ~0–2 (`0.2` ≈ very faint, `1` = normal, `2` = loud). This is the tag for "the agent didn't hear the user" failures. Confirm the ratio is valid for the agent's voice provider (support differs across 11labs / cartesia). |
| Caller pauses mid-sentence; agent could jump in | `<silence time="1.5s" />` | **Interruptible**, mid-utterance only — never trailing (see the end-of-action rule above). |
| Caller goes dead-silent to trip a silence/turn timeout | `<hold time="2s" />` | **Non-interruptible** — forces the gap; use this (not `<silence>`) when the failure is a silence-timeout. |
| Caller laughs / sighs / is emotional | `[laughter]`, `[sigh]`, etc. | Emotion markers; can repeat (`[laughter] [laughter]`). |
| Caller hangs up | `<endcall />` | No-op unless `end_call` is in `tool_ids` (see above). |

**Personality vs tag:** some delivery conditions can also be expressed via the chosen `personality` (e.g. a "Low volume speaker" personality instead of a per-message `<volume>` tag). Prefer the **per-message tag** when the condition is localized to specific turns (e.g. only the back-channel "yeah yeah" is faint), and the personality when the whole call has that quality. Don't apply both for the same effect.

**Apply tags only when they are load-bearing for the failure.** If the call-log failure was acoustic/delivery-driven, the tag IS the point of the replay — omitting it means the scenario can't reproduce the bug. If the failure was purely logical (wrong workflow branch, tool error, missed question), don't sprinkle tags — they add noise and can confuse the metric judge. Call out in the report's scenario rationale which tag reproduces which observed condition, so the user can see the replay is faithful.

### Dedup against existing scenarios

Drop or flag any cluster that restates an existing scenario on the agent (Step 2a). Near-duplicates surface in the report with `similar_to_existing` so the user decides.

## Step 5 — Emit the report

Save as `failure_scenarios_<agent_id>.md` in the working directory. Structure:

```markdown
# Scenarios from failed calls — <agent_name> (`<agent_id>`)

**Project:** `<project_id>` · **Flagged calls in:** <K> · **Failure-mode hits:** <M> · **Proposed scenarios:** <S>

## Failure summary

| Mode | Calls | Top quote |
|---|---|---|
| 👻 Hallucination | 7 | "Our refund window is 90 days" (no such policy in description) |
| 🔧 Tool error | 4 | Agent re-asks account number after successful `lookup_account` |
| 🛑 Drop | 3 | ended_reason: silence-timeout at 0:14 |

## Proposed scenarios

### C1 — <scenario name>

**Mode:** 👻 hallucination · **Type:** instruction · **Personality:** `<id> — Persistent Female, en-US`

**Why this:** <one sentence — the pattern the cluster represents>

**Evidence:**
- 📞 Call [<call_log_id>](https://dashboard.cekura.ai/<project_id>/observe/<call_log_id>): "<verbatim transcript quote>"
- 📞 Call [<call_log_id>](https://dashboard.cekura.ai/<project_id>/observe/<call_log_id>): "<verbatim transcript quote>"

**Draft scenario** — this cluster is `instruction`, so the draft is a **spec, not a create payload**: its `instructions` + `expected_outcome_prompt` become the `extra_instructions` passed to the generation endpoint (see **Write path**). Shown in payload form only so the user can review the intent.

```json
{
  "name": "...",
  "scenario_type": "instruction",
  "personality": 693,
  "scenario_language": "en-US",
  "first_message": "Hi, I'm calling about a refund on order 4421",
  "instructions": "You are a customer who placed an order 95 days ago and is pushing hard for a refund. Insist on a specific refund window. Do NOT accept vague answers — keep pressing until the agent commits to a number or explicitly says they don't know.",
  "expected_outcome_prompt": "The agent must not invent a refund-window number that is not in its description or KB. It should either cite a documented policy or escalate.",
  "tool_ids": [],
  "dynamic_variable_values": {
    "first_name": "Sarah",
    "last_name": "Lin",
    "order_number": "4421"
  }
}
```

**Test profile to attach:** values above will be created as test profile `<cluster_id>-vars (<persona-summary>)` and attached after the scenario is created (see Step 6).

**Similar to existing:** <none | scenario name + ID + one-line diff>

(repeat per cluster)

## Coverage notes

<One paragraph: which failure modes ended up with no scenario and why (too few samples, already covered, etc.). Keep it factual.>

## Recommendations

1. Create C1, C3, C5 first — they represent the highest-frequency failure modes (<N> calls combined).
2. C7 is a single-call critical (PII) — create regardless of frequency.
3. After scenarios are live, run `mcp__cekura__scenarios_run_<mode>` for each and confirm the agent fails on them today (the failure is reproducible).
4. Re-run after any agent prompt change to confirm the fix.
```

### Style rules

- Every call log reference is a markdown link to `https://dashboard.cekura.ai/<project_id>/observe/<call_log_id>`.
- Quote transcript slices verbatim. Never paraphrase.
- If a failure mode has zero clusters (e.g. no hallucinations seen), omit the row from the summary table — don't pad.
- Tone: direct and evidence-led. No "you might want to consider…" hedging.
- Each scenario has at least one evidence call or it doesn't appear in the report.

## Step 6 — Offer to create

After printing the report, split the clusters by `scenario_type` per **Write path** above. That split is already decided — state it, don't offer it as a choice:

> Want me to build these? The split is fixed by scenario type: **conditional-action clusters (<CA list>)** get created directly from the drafted turn-by-turn spec; **instruction clusters (<instr list>)** get generated from the evidence calls with the drafted failure summary as `extra_instructions`. Options:
>
> 1. **Build all of them** — both halves, one pass.
> 2. **Custom subset** — pick cluster IDs; each still follows its own type's path.
> 3. **Per-transcript generation for the instruction half** — `scenarios_create_from_transcript` per cluster. Closer to the original flow, less control over phrasing.
> 4. **No** — leave the report, I'll build them myself.

Do not collapse the instruction half into direct creates because the drafted wording looks good — the draft becomes `extra_instructions`, not the scenario body.

### The instruction half — generate via the platform endpoint

This is the path for every `instruction` cluster (drift, hallucination, comprehension, refusal, safety). Call `mcp__cekura__call_logs_create_scenarios` with:

| Field | Value |
|---|---|
| `agent_id` | From Step 2a |
| `project_id` | From Step 2a |
| `call_log_ids` | Union of the evidence call IDs belonging to the **instruction clusters** (deduped) |
| `extra_instructions` | A condensed version of the report's failure summary — one bullet per instruction cluster: "<mode>: <expected_behavior>", plus the verbatim `evidence_quote` where it pins the failure. This is where the draft we just wrote goes; the generator uses it to bias scenario phrasing toward the failure modes we found. |

Poll `mcp__cekura__call_logs_create_scenarios_progress` until completed. Surface the returned scenario IDs as a table with dashboard links and ask the user to spot-check before running.

If a cluster comes back thin or misses its failure mode, **re-generate that cluster alone** with sharper `extra_instructions` (or use `scenarios_create_from_transcript` on its cleanest evidence call). Do not "fix" it by hand-authoring the `instruction` body.

**After completion, audit each returned scenario for `test_profile == null`.** The server-side generator may or may not attach a test profile. For any returned scenario whose agent has `agent_dynamic_vars` non-empty and `test_profile` is null, derive `dynamic_variable_values` from the matching cluster (or the evidence call) and run steps 2 + 3 below to attach a profile. Otherwise the next outbound run will fail with `Missing required dynamic variables` (on ElevenLabs) or silently substitute empty strings (on other providers).

### The conditional-action half — direct create per cluster

This is the path for every `conditional_actions` cluster (drop, tool_error, workflow_miss). For each, do **three calls in sequence**:

1. **Create the scenario** via `mcp__cekura__scenarios_create` with the draft spec. Required fields:

   | Field | Value |
   |---|---|
   | `agent_id` / `project_id` | From Step 2a |
   | `name` | From the cluster |
   | `scenario_type` | `conditional_actions` — an `instruction` scenario does not belong on this path (generate it instead) |
   | `personality` | From the cluster |
   | `scenario_language` | Required on CA scenarios — the cluster's language code (`en`, `es`, …) |
   | `conditional_actions` | `{"role": "<caller role from the cluster>", "conditions": [<drafted turn-by-turn list>]}` — the turns go in **this wrapper**, not a top-level `conditions` field, or they are dropped and the scenario improvises. The cluster's `first_message` is condition `id: 0` (`condition: "FIRST_MESSAGE"`), not a separate field: `first_message` and `instructions` must stay unset on CA scenarios. |
   | `tool_ids` | From the cluster |
   | `expected_outcome_prompt` | From the cluster |

2. **Create the test profile** via `mcp__cekura__test_profiles_create` — ONLY if the cluster has non-empty `dynamic_variable_values` OR persona/context the testing agent should reference (caller name, situational facts). Skip this and step 3 for clusters with no placeholders and no persona.

   Build `information` as a sectioned dict:

   | Field | Value |
   |---|---|
   | `agent` | The agent_id from Step 2a |
   | `name` | `<cluster_id>-vars` (e.g. `C1-vars`) or a one-line persona summary |
   | `information.main_agent_variables` | The cluster's `dynamic_variable_values` dict — values that reach the agent under test as dynamic variables at call time. Omit this section entirely (or leave it `{}`) if the agent has no registered dynamic variables. |
   | `information.testing_agent_variables` | Persona / context the simulated caller should use — e.g. `customer_name`, `date_of_birth`, situational facts mined from evidence calls. Omit (or `{}`) if there's no persona context. |

   Capture the returned `test_profile_id`.

3. **Attach the test profile to the scenario** via `mcp__cekura__scenarios_partial_update`:

   | Field | Value |
   |---|---|
   | `id` | The scenario_id returned in step 1 |
   | `test_profile` | The test_profile_id returned in step 2 |

   Verify by reading back the scenario — its `test_profile_data.information` should match what you sent. Dynamic variables reach the agent under test via `test_profile.information.main_agent_variables`; persona/context lives in `testing_agent_variables`.

Don't silently drop fields — echo the final spec before each create if the user has edited any cluster.

### Alternative for the instruction half — per-transcript generation

Menu option 3. Applies to the **instruction clusters only** (the conditional-action half always takes the direct-create path above). For each cluster, pick the evidence call with the cleanest representation of the failure mode. Call `mcp__cekura__scenarios_create_from_transcript` with:

| Field | Value |
|---|---|
| `agent_id` / `project_id` | From Step 2a |
| `call_log_id` | The chosen evidence call |
| `extra_instructions` | The cluster's `expected_behavior` + a one-line "Specifically reproduce: <failure-mode + quote>" hint |

This path produces scenarios that more closely match the original call's flow at the cost of less control over phrasing.

Same caveat as the platform endpoint: after each scenario is returned, check `test_profile` and attach one (steps 2 + 3 of the direct-create path) if the agent has dynamic variables and the field is null.

### Custom subset

Menu option 2. User picks cluster IDs; each selected cluster still follows its own type's path — CA clusters created directly, instruction clusters generated. A subset never changes the write path.

After creation, print one line per new scenario with `https://dashboard.cekura.ai/test-case/<scenario_id>` so the user can spot-check, and recommend they:

1. Run each new scenario once (`mcp__cekura__scenarios_run_<mode>`) to confirm the agent **still fails** on it — the scenario only matters if it reproduces.
2. After the agent's next prompt change, re-run the set; passing scenarios = fix confirmed.

## When to escalate instead

Don't create scenarios (and say so) if any of these are true:

- The agent has **no `agent_description`** and the user opted to proceed on outcome signal alone — surface that the generated scenarios will be thin on "expected behavior" guidance and recommend fleshing out the description first.
- All failures classify as `drop` with no transcript content — call-not-connected failures aren't a scenario-fixable problem; that's a run-debugging task: investigate the underlying telephony/agent configuration instead.
- The user asks for "one scenario per failed call" — push back. Per-call scenarios overfit and dilute the regression set; cluster first.
- The agent already has > 30 scenarios with > 80% coverage of the failure modes seen — say so explicitly. "Your current coverage looks complete given the last <N> calls; consider tightening the existing metrics instead of adding more scenarios."

## Quick reference — failure modes → scenario construction

The authoritative failure taxonomy + detection signals live in `cekura-flag-call-log-failures` (the skill that classifies). This table is the **construction map** — given a flagged call's `mode`, how to build its scenario:

| Emoji | Code | Typical scenario_type | Write path | Cluster signal |
|---|---|---|---|---|
| 🛑 | drop | conditional_actions | `scenarios_create` | ended_reason + short duration |
| 🌀 | drift | instruction | generate | content outside `agent_description` |
| 👻 | hallucination | instruction | generate | fact not in KB/description |
| 🔧 | tool_error | conditional_actions | `scenarios_create` | tool error / unused tool result |
| 🎯 | workflow_miss | conditional_actions | `scenarios_create` | required step skipped |
| 🤔 | comprehension | instruction | generate | caller repeats themselves |
| 🚪 | refusal | instruction | generate | "I can't help with that" inside scope |
| ⚡ | latency | (metric, not scenario) | — | latency metric outliers |
| 🧨 | safety | instruction | generate | PII / disallowed content |
