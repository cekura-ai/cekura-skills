---
name: cekura-generate-scenarios
description: |
  Fetch recent production call logs for a Cekura agent, find the calls
  where the agent actually failed (failing metrics, drops, hallucinations,
  tool errors, missed workflows), cluster the failures into reproducible
  modes, and create evaluator scenarios that simulate each mode against
  the agent. Use when the user says "create scenarios from failed calls",
  "build evaluators for prod failures", "turn call logs into scenarios",
  "simulate the failures we saw in prod", "replay these bad calls as
  tests", "regression-test the agent on prod issues", or pastes an agent
  ID and asks to harden the agent against real failures. Pulls call logs,
  extracts failure evidence per call, clusters by failure mode, drafts
  one scenario per cluster, and optionally creates them via the scenarios
  API (or the dedicated call-logs → scenarios endpoint). Also supports a
  single-call fast path: given one specific call log ID (or an observe
  URL), reproduce just that call as one evaluator scenario.
argument-hint: "<agent_id | dashboard URL | call_log_id>"
allowed-tools:
  - AskUserQuestion
  - Bash
  - Read
  - Write
  - Edit
  - Grep
  - Glob
  - Skill
version: 0.2.0
---

# generate-scenarios

Convert real production failures into evaluator scenarios so the next regression run catches them. Signal is mined from **call logs** — what real callers did, where the agent broke, and what the right behavior would have been. Every scenario produced traces back to at least one call log; nothing is invented.

This skill is **read-first**: it never creates a scenario without an explicit user OK on the proposed set.

---

## Step 0 — Prerequisites

This skill reads + writes through the Cekura MCP. Confirm these tools are present before starting:

- `mcp__cekura__aiagents_retrieve` — agent description, language, scenario defaults, tool wiring
- `mcp__cekura__call_logs_list` — paginated production call list filtered to the agent
- `mcp__cekura__call_logs_retrieve` — transcript, metric evaluations, ended_reason per call
- `mcp__cekura__scenarios_list` — existing scenarios on the agent (dedup)
- `mcp__cekura__scenarios_create` — single-scenario create
- `mcp__cekura__scenarios_partial_update` — attach the test profile to the scenario after both exist
- `mcp__cekura__scenarios_create_from_transcript` — turn a single call transcript into a scenario
- `mcp__cekura__call_logs_create_scenarios` + `mcp__cekura__call_logs_create_scenarios_progress` — bulk path: hand a set of call log IDs to the platform and let it generate scenarios server-side
- `mcp__cekura__scenarios_generate_bg` + `mcp__cekura__scenarios_generate_progress` — alt bulk path via free-form `extra_instructions`
- `mcp__cekura__test_profiles_create` — create a test profile carrying the cluster's dynamic-variable values
- `mcp__cekura__personalities_list` — pick a matching caller personality per cluster
- `mcp__cekura__metrics_list` — find an existing metric to reuse on the scenario (single-call fast path)
- `mcp__cekura__metrics_create` — create a focused pass/fail metric for the reproduced failure (single-call fast path)

If the `mcp__cekura__*` tools are not connected, stop and tell the user to connect the Cekura MCP — don't fall back to DB queries.

---

## Step 1 — Identify the target agent and window

Use `AskUserQuestion` if not already supplied:

1. **Agent ID** on Cekura (numeric, e.g. `16937`). If unknown, use `mcp__cekura__aiagents_list` to help find it.
2. (Optional) **Project ID**, if the user manages multiple projects.
3. (Optional) **Window** — default to the last 50 call logs or the last 14 days, whichever is smaller. Override if the user has a specific date range or incident window.
4. (Optional) **Focus mode** — e.g. "only hallucinations" or "only tool failures". Used to weight the final scenario set; not a hard filter unless the user is explicit.

Do not proceed until the agent ID is confirmed. If the user pasted a `dashboard.cekura.ai/<project>/observe/<call_log_id>` URL, treat it as a seed call and ask whether to expand to nearby calls on the same agent, or only generate from that one call.

**Single-call mode.** If the user supplies a specific **call log ID** (or an observe URL) and wants a scenario from *that* call — wording like "create a scenario for call log 7159402", "turn this call into an evaluator", "replay this call" — skip the mining/clustering (Steps 2b–4) and use the **Single-call fast path** below. You still need the agent context from Step 2a (agent description, dynamic-variable names, personalities, existing scenarios for dedup) and the `tool_ids` rules from Step 4. Confirm which agent the scenario should run against — it can differ from the agent that produced the call.

---

## Single-call fast path — one call ID → one scenario

Use this when the user wants a scenario reproduced from **one specific call** (not a mined set). It skips Steps 2b–4 (mining/clustering) but keeps the read-first rule: draft → confirm → create. Still pull agent context (Step 2a) and obey the `tool_ids` rules (Step 4).

### A. Retrieve the call

`mcp__cekura__call_logs_retrieve(id=<call_log_id>)`. Capture `transcript_object`, `call_ended_reason`, `success`, `duration`, `metadata` (caller identity + enrollment state), and any `metric_evaluations`. Read the whole transcript — a single call is usually about ONE thing.

### B. Pin the focal failure

Identify the **failure point** — the turn where the agent did the wrong thing — using the Step 3 failure modes. Record the verbatim `evidence_quote` and a one-sentence `expected_behavior` (→ becomes `expected_outcome_prompt`). If the call clearly contains several distinct failures, ask the user which one to target; don't silently fold them into one scenario.

### C. Build a faithful replay (`conditional_actions`)

Walk the caller's path **turn-by-turn in the same order the real call took**, up to and through the failure point: identity → screening → … → the failing step. Each condition is `{condition: "<observable thing the agent does>", action: "<what the caller says>", fixed_message}`.

- **Anchor the failure.** The condition right before the failure must set it up exactly (the caller corrects a mis-heard value / declines an offer / mentions a medication / says the ambiguous phrase). Add an explicit condition for the FAIL branch (e.g. "the agent says it is transferring you to a human", "the agent ends the call") with a benign caller line, so the metric has a concrete signal to grade against.
- **`fixed_message` choice (this bites):**
  - `true` for values that must be reproduced verbatim — DOB, ZIP, the literal trigger phrase ("Speak to me", "Can I talk to somebody?"), a mis-stated-then-corrected number.
  - `false` (the action text becomes an **instruction the caller paraphrases**) for turns that must **adapt to what the agent offers** — e.g. *"Pick ONE of the specific times the agent offers (the earliest) and name it clearly."* A `fixed_message: true` reply that doesn't actually choose ("that works, thank you") makes the agent re-ask the same question forever — a real loop we hit on slot selection. When the agent presents choices, the caller MUST commit to one concrete option.
  - **`FIRST_MESSAGE` (id 0) MUST stay `fixed_message: true`** (API rejects otherwise). For outbound calls (agent speaks first) set its action to `""`.
- **Always include the end-call tool in `tool_ids`** — it's a hard always-on rule for every scenario (Step 4). End the success path with `<endcall />` in the final action; the `<endcall />` marker is a no-op unless that tool is wired in.
- **Never append `<silence>` (or `<hold>`) tags at the END of an action.** Those SSML pause tags are only for *mid-utterance* pacing (a beat inside a sentence). Trailing them on the end of a line — e.g. `"...thanks <silence time="1.0s" /> <endcall />"` or as the caller's last token — just injects dead air and serves no purpose. End actions on the spoken words; if the turn closes the call, the final action ends with `<endcall />` directly (no preceding `<silence>`). Do not pad actions with trailing silence by default.

(Use `scenario_type: instruction` instead only for free-form red-team calls — hallucination/drift/refusal — where the caller needs latitude.)

### D. Caller identity → test profile (camelCase keys — load-bearing)

Pull the caller's identity from `metadata` (`enrollment_hello_data`, `*_data` blocks) and the transcript: name, DOB, ZIP, address, medications, etc. Create a test profile (`mcp__cekura__test_profiles_create`, `agent=<agent_id>`) whose `information` carries these as **dynamic variables**.

- **Key casing matters.** These squads reference variables in **camelCase** (`{{firstName}}`, `{{lastName}}`, `{{dateOfBirth}}`, `{{zipCode}}`, `{{fullAddress}}`) — and that's the casing production injects. A profile that only sets lowercase `firstname`/`zipcode` leaves `{{firstName}}`/`{{zipCode}}` **unresolved at runtime** — the agent greets "Am I speaking with `{{firstName}}`?", and tool calls send the literal string `{{zipCode}}` (which the backend rejects). **Set BOTH camelCase and lowercase keys** for every identity field so the prompt resolves regardless of which casing it uses. When `agent_dynamic_vars` (Step 2a) is known, match those names exactly.
- Keep values consistent with the conditional actions — if the caller says "986 Old Collard Valley Road", the profile's `street`/`fullAddress` must say 986.

### E. Metric

Score the specific behavior. **Reuse** an existing metric if one fits (`mcp__cekura__metrics_list(agent_id=...)` — e.g. an existing "Voicemail Detection Accuracy" / "No Premature Transfer…" on the agent). Otherwise **create** one (`mcp__cekura__metrics_create`, `type=llm_judge`, `eval_type=binary_workflow_adherence`, `project=<id>`, `agents=[<agent_id>]`) whose description spells out PASS/FAIL grounded in the call's failure and cites the call ID.

### F. Create (after user OK)

1. **Scenario** — `mcp__cekura__scenarios_create`: agent, `name` ("<failure> (from call <id>)"), `scenario_type`, `personality` (Step 4 heuristics), `metrics=[<metric_id>]`, `folder_path` (if the user named a folder), `expected_outcome_prompt`, `instructions`/`conditional_actions`, `tags=["replay-<call_id>", "<mode>"]`, testing-agent `tool_ids`.
2. **Test profile** — `mcp__cekura__test_profiles_create` with the camelCase+lowercase identity dict; capture the id.
3. **Attach the profile** — `mcp__cekura__scenarios_partial_update(id=<scenario_id>, test_profile=<profile_id>)`. The runtime only reads dynamic variables from the attached profile, not the scenario's own `dynamic_variable_values`.
4. **Attach the evaluator phone** for phone/outbound agents — set the scenario's phone number (e.g. via `scenarios_partial_update`). The create call may not persist it, so **read the scenario back and PATCH if the phone is null.** (For this internal Twin-Health setup the shared evaluator number is **+18647326888** — look up its inbound-phone-number ID; other orgs use their own configured number.)
5. **Verify** — read the scenario back and confirm `test_profile_data`, `metrics`, `folder_path`, and the phone are all set.

Print the `https://dashboard.cekura.ai/test-case/<scenario_id>` link and recommend running it once to confirm the agent still fails (the replay reproduces the bug).

### Alternative: platform transcript path

To let the platform draft from the raw transcript instead, `mcp__cekura__scenarios_create_from_transcript(agent=<agent_id>, call_log_id=<id>, extra_instructions=<focal failure + expected behavior>)`. Lower control over wording; still attach a test profile (camelCase keys) + metric + phone afterward per D–F. This endpoint can be slow — if it times out, fall back to the `conditional_actions` build in C.

---

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

**Why it matters:** the Cekura outbound trigger (`vocera.backend/app/helper/provider_outbound_call.py:148`) reads dynamic variables from `test_profile.information` — NOT from `scenario.dynamic_variable_values`. If a scenario references `{{first_name}}` etc. but has no attached test profile, ElevenLabs rejects the conversation with `termination_reason: "Missing required dynamic variables in first message"` and the call drops in < 1s with `call-not-connected`. The scenario will never run successfully without a test profile.

**Hard rule:** if `agent_dynamic_vars` is non-empty AND `assistant_provider == "elevenlabs"`, every scenario this skill creates MUST get a test profile attached in Step 6. For other providers (vapi, retell, bland, livekit) the variables are also injected at runtime but typically don't hard-fail when missing — still recommended to attach a profile so the agent has values to work with.

Call `mcp__cekura__scenarios_list(agent=<agent_id>)` to enumerate existing scenarios on the agent — used for dedup (don't propose a scenario that already exists; flag near-duplicates).

Call `mcp__cekura__personalities_list(project_id=<project_id>)` so you have personality IDs ready to attach in Step 4. At minimum capture a `Normal` male/female personality in the agent's language plus any `Frustrated` / `Confused` / `Interruptive` ones — clusters will map to these.

**If `agent_description` is missing or weak (< 2 sentences, placeholder, lorem ipsum), STOP and surface:**

> ⚠️ The agent's `agent_description` is empty / very short. Without it, "failure" is ungrounded — we can't tell drift from working-as-intended. Please flesh out the description (workflows, audience, must-not-do list) before continuing — or confirm you want to proceed using ended_reason + metric_evaluations as the only failure signal.

Only continue once description issues are resolved or the user explicitly opts to proceed on outcome signal alone.

### 2b. Call logs

Call `mcp__cekura__call_logs_list` filtered to the agent, sorted descending by `created_at`, page size 50 (or the user's window). For each call log row, capture:

| Field | Used for |
|---|---|
| `id`, `created_at`, `duration` | Header, recency |
| `ended_reason` / `end_call_reason` | First-pass failure signal — see classifier in Step 3 |
| `metric_evaluations` (or summary fields) | Per-call metric pass/fail signal |
| `transcript` / `transcript_object` | The conversation to mine in Step 3 |
| `personality_id` (if attached) | Reuse on the generated scenario where it fits |
| `caller_number` / direction info | First-message + direction on the generated scenario |

If the rolled-up list view already includes a failure flag (`success`, `passed`, `status`), use it. If not, fetch full detail via `mcp__cekura__call_logs_retrieve(id=<call_log_id>)` in parallel for the candidate failures only — don't pull every transcript by default.

If `call_logs_list` returns 0 (pre-production agent), stop and tell the user — this skill needs prod signal. Recommend `cekura:cekura-eval-design` for design-from-scratch scenarios instead.

---

## Step 3 — Classify failures per call

For each call, decide if it's a failure and, if so, which **failure mode** it belongs to. Record `{call_log_id, mode, severity, evidence_quote, expected_behavior}`.

### Failure modes

| Code | Mode | Detection signals |
|---|---|---|
| 🛑 `drop` | Call dropped / ended early | `ended_reason` ∈ {`silence-timeout`, `customer-ended-after-1-turn`, `agent-disconnect`, `error`}; `duration` < 15s; transcript ends mid-workflow |
| 🌀 `drift` | Agent went off-task / off-persona | Transcript contains content unrelated to `agent_description`; agent answered a question outside its declared scope |
| 👻 `hallucination` | Agent stated facts not in KB / description | Numbers, policies, named products that aren't anywhere in the agent description or known KB sources |
| 🔧 `tool_error` | Tool selection / argument / post-tool handling broke | Tool call with error response; agent re-asks a question already answered by a successful tool call; wrong tool fired for the turn |
| 🎯 `workflow_miss` | Required workflow step skipped or wrong | Agent quoted a balance without verifying account; agent didn't escalate when policy said to; agent skipped consent disclosure |
| 🤔 `comprehension` | Agent misunderstood the caller | Caller repeats themselves 2+ times; caller says "no, I meant…"; agent repeats a clarifying question 3+ times |
| 🚪 `refusal` | Agent refused a legitimate ask | Agent said "I can't help with that" for something inside its description |
| ⚡ `latency` | Long silence / response gap | If latency metrics are attached; long inter-turn gaps visible in transcript timestamps |
| 🧨 `safety` | PII leak / unsafe content | Agent repeated back SSN/card number unprompted; produced content disallowed by description |

A call can fire multiple modes — record each one separately. If a call shows nothing wrong, it's not in the failure set and gets dropped.

### Evidence rule

For every recorded failure, the `evidence_quote` field MUST be a verbatim slice of the transcript (or the failing `metric_evaluation` justification). No paraphrasing — if the failure can't be quoted, it doesn't count.

### Expected behavior

For every failure, also capture `expected_behavior` — a single sentence describing what the agent **should have done**, grounded in `agent_description` or a policy quote. This becomes the scenario's `expected_outcome_prompt`.

---

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

- **`instruction`** for free-form / red-teamy clusters: hallucinations, drift, refusal, comprehension, safety. The testing agent needs latitude to push.
- **`conditional_actions`** for sequential workflow clusters: workflow_miss, tool_error, drop-mid-workflow. Walk the exact failure path turn by turn.

### Picking the personality

- `drop` after caller frustration → `Frustrated` matching language.
- `comprehension` repeats → `Confused` or `Mumbling`.
- `hallucination` where caller pressed for specifics → `Persistent` / `Inquisitive`.
- Everything else → `Normal` male or female matching the agent's language.
- **Never** pair `Interruptive` with `conditional_actions` — that's a known structural issue (see `cekura-internal:review-scenarios` R1).

### Picking `tool_ids` — testing-agent tools (REQUIRED for end-of-call patterns)

`tool_ids` on a scenario is the **testing agent's** tool surface — i.e., what the simulator can do to drive the world (hang up, press DTMF, sit silently). It is NOT the agent-under-test's tool list; that's owned by the agent's own provider config (ElevenLabs `built_in_tools`, VAPI `model.toolIds`, etc.) and the scenario can't change it.

**🔴 Always-on rule — every scenario this skill generates MUST include the testing-agent end-call tool in `tool_ids`. No exceptions, regardless of cluster/flow/type.** It's harmless when never invoked and it prevents the silent-timeout failure described below. The only open question is *which* tool reference to use (resolve it per rule 4 — don't invent it), never *whether* to include it. If you can't resolve the correct end-call tool ID for the provider, ask the user before creating rather than shipping a scenario without it.

The most common silent failure of generated scenarios is omitting `end_call` on a cluster whose expected flow requires the testing agent to terminate. Symptom: the scenario hangs until the global call timeout fires (~60s+), `ended_reason` comes back as `silence-timeout` or `testing-agent-ended-call` from a wall-clock kill instead of from the intended condition, and the failure-mode metrics evaluate against a garbage trailing transcript.

**Required tool by cluster flow:**

| Cluster pattern | Testing-agent tools required |
|---|---|
| Voicemail / recorded-greeting (agent must call `voicemail_detection`, not speak) | `end_call` — testing agent terminates after the beep / after the "leave a message" prompt |
| Indefinite hold music (agent must `end_call` after bounded `skip_turn`s) | `end_call` — testing agent kills the call when its bounded-hold loop expires, otherwise the scenario can't reach the "agent didn't end_call" failure state cleanly |
| AI virtual receptionist / IVR-side simulation that gates on DOB or refuses transfer (agent must hang up) | `end_call` — testing agent terminates after the gating condition fires, so the scenario exits even if the agent stalls instead of ending |
| Uncooperative receptionist / repeated refusal (agent must end politely) | `end_call` |
| Wrong-script / "Got it, thanks" prematurely (agent must stay on the call) | `end_call` — testing agent hangs up at the natural close so the run terminates; without it the agent-under-test's premature `end_call` IS the only termination, which is exactly the failure being tested but masks the post-failure recovery turn |
| Free-form instruction scenario where the testing agent just plays a caller and never needs to end first | **Still include `end_call`** (always-on rule) — harmless if never invoked, and lets the caller end cleanly if the conversation resolves |

**Hard rules:**

1. **If any `condition.action` contains the inline marker `<endcall />` (XML in `fixed_message`), the scenario MUST include `end_call` in `tool_ids`.** The XML marker is sugar that compiles to an `end_call` tool invocation on the testing-agent side — it's a no-op when the underlying tool isn't wired in. Same applies to `<silence time="..." />` (no extra tool, just timing) — but `<endcall />` is the foot-gun.
2. **If the cluster's `expected_behavior` reads "agent must hang up" / "agent must call end_call", the scenario MUST include `end_call` in `tool_ids`.** Reason: the run needs an authority that can force termination if the agent doesn't end, otherwise the scenario's success condition (which is "agent ended cleanly") can't be distinguished from "framework timeout fired because nobody ended."
3. **DTMF is an agent-under-test concern, not a testing-agent concern — do NOT add `play_keypad_touch_tone` to scenario `tool_ids`.** When a scenario simulates an IVR menu that the agent-under-test must navigate, the testing agent's job is to *announce the menu options in its `fixed_message`* and loop or advance based on which digit the agent presses. The agent-under-test needs `play_keypad_touch_tone` (ElevenLabs `built_in_tools.play_keypad_touch_tone`, VAPI equivalent) wired into ITS config — that's an agent-creation concern handled by `cekura-internal:create-agent`, not this skill. If the agent under test lacks DTMF capability, surface that as a coverage gap in the report's "Recommendations" section — don't try to compensate via scenario `tool_ids`.
4. **Don't invent tool IDs.** Provider-specific values differ — VAPI uses string constants like `"VAPI_TOOL_END_CALL"`, ElevenLabs / retell scenarios reference the platform's built-in system tool by its platform ID. Read `scenarios_list` output from Step 2a — copy the exact `tool_ids` value used by any existing scenario on the same agent that successfully terminates. If no existing scenario has `tool_ids` populated and you can't resolve the ID, ask the user for the end_call tool reference before creating; do not guess.

This is the always-on rule restated: **add `end_call` to every generated scenario.** A scenario with `end_call` in `tool_ids` that never invokes it is harmless; a scenario that needs to invoke it and can't is the silent-timeout case above. So there's no "when in doubt" — it's always in.

### Dedup against existing scenarios

Drop or flag any cluster that restates an existing scenario on the agent (Step 2a). Near-duplicates surface in the report with `similar_to_existing` so the user decides.

---

## Step 5 — Emit the report

Save as `failure_scenarios_<agent_id>.md` in the working directory. Structure:

```markdown
# Scenarios from failed calls — <agent_name> (`<agent_id>`)

**Project:** `<project_id>` · **Window:** <N> calls from <start> to <end> · **Failures:** <K> calls / <M> failure-mode hits · **Proposed scenarios:** <S>

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

**Draft scenario:**

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

---

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

---

## Step 6 — Offer to create

After printing the report, ask the user:

> Want me to create these scenarios? Options:
>
> 1. **Hand the failing call IDs to the platform endpoint** — call `mcp__cekura__call_logs_create_scenarios` with the failing `call_log_ids` and let Cekura's scenario-generation job produce scenarios server-side. Lowest control, fastest.
> 2. **Create each draft scenario directly** — bulk-create the <S> draft scenarios from the report via `mcp__cekura__scenarios_create` per cluster. Uses the spec we just drafted (you keep control over wording).
> 3. **Generate from one transcript at a time** — for each cluster, pick the best evidence call and run `mcp__cekura__scenarios_create_from_transcript` against that call's transcript. Trades draft fidelity for transcript-grounded phrasing.
> 4. **Custom subset** — pick specific cluster IDs (e.g. "create C1, C3, C7 only").
> 5. **No** — leave the report, I'll create them manually.

### Option 1 — platform endpoint

Call `mcp__cekura__call_logs_create_scenarios` with:

| Field | Value |
|---|---|
| `agent_id` | From Step 2a |
| `project_id` | From Step 2a |
| `call_log_ids` | Union of all evidence call IDs across clusters (deduped) |
| `extra_instructions` | A condensed version of the report's failure summary — one bullet per cluster: "<mode>: <expected_behavior>". The server-side generator uses this to bias scenario phrasing toward the failure modes we found. |

Poll `mcp__cekura__call_logs_create_scenarios_progress` until completed. Surface the returned scenario IDs as a table with dashboard links and ask the user to spot-check before running.

**After completion, audit each returned scenario for `test_profile == null`.** The server-side generator may or may not attach a test profile. For any returned scenario whose agent has `agent_dynamic_vars` non-empty and `test_profile` is null, derive `dynamic_variable_values` from the matching cluster (or the evidence call) and run steps 2 + 3 from Option 2 to attach a profile. Otherwise the next outbound run will fail with `Missing required dynamic variables` (on ElevenLabs) or silently substitute empty strings (on other providers).

### Option 2 — direct create per cluster

For each cluster, do **three calls in sequence**:

1. **Create the scenario** via `mcp__cekura__scenarios_create` with the draft spec. Required fields:

   | Field | Value |
   |---|---|
   | `agent_id` / `project_id` | From Step 2a |
   | `name` | From the cluster |
   | `scenario_type` | `instruction` or `conditional_actions` |
   | `personality` | From the cluster |
   | `scenario_language` | Required on CA scenarios; carry through on instruction too |
   | `first_message` | From the cluster |
   | `instructions` | Required for `instruction` type |
   | `conditions` | Required for `conditional_actions` type |
   | `tool_ids` | From the cluster |
   | `expected_outcome_prompt` | From the cluster |

2. **Create the test profile** via `mcp__cekura__test_profiles_create` — ONLY if the cluster has non-empty `dynamic_variable_values`. Skip this and step 3 for clusters with no placeholders.

   | Field | Value |
   |---|---|
   | `agent` | The agent_id from Step 2a |
   | `name` | `<cluster_id>-vars` (e.g. `C1-vars`) or a one-line persona summary |
   | `information` | The cluster's `dynamic_variable_values` dict, verbatim |

   Capture the returned `test_profile_id`.

3. **Attach the test profile to the scenario** via `mcp__cekura__scenarios_partial_update`:

   | Field | Value |
   |---|---|
   | `id` | The scenario_id returned in step 1 |
   | `test_profile` | The test_profile_id returned in step 2 |

   Verify by reading back the scenario — its `test_profile_data.information` should match what you sent. The Cekura outbound trigger only sees the variables once `test_profile` is set; the scenario's own `dynamic_variable_values` field is NOT read at runtime.

Don't silently drop fields — echo the final spec before each create if the user has edited any cluster.

### Option 3 — per-transcript path

For each cluster, pick the evidence call with the cleanest representation of the failure mode. Call `mcp__cekura__scenarios_create_from_transcript` with:

| Field | Value |
|---|---|
| `agent_id` / `project_id` | From Step 2a |
| `call_log_id` | The chosen evidence call |
| `extra_instructions` | The cluster's `expected_behavior` + a one-line "Specifically reproduce: <failure-mode + quote>" hint |

This path produces scenarios that more closely match the original call's flow at the cost of less control over phrasing.

Same caveat as Option 1: after each scenario is returned, check `test_profile` and attach one (Option 2 steps 2 + 3) if the agent has dynamic variables and the field is null.

### Option 4 — custom subset

User picks cluster IDs. Apply the matching option (1/2/3) only to those clusters.

After creation, print one line per new scenario with `https://dashboard.cekura.ai/test-case/<scenario_id>` so the user can spot-check, and recommend they:

1. Run each new scenario once (`mcp__cekura__scenarios_run_<mode>`) to confirm the agent **still fails** on it — the scenario only matters if it reproduces.
2. After the agent's next prompt change, re-run the set; passing scenarios = fix confirmed.

---

## When to escalate instead

Don't create scenarios (and say so) if any of these are true:

- The agent has **no `agent_description`** and the user opted to proceed on outcome signal alone — surface that the generated scenarios will be thin on "expected behavior" guidance and recommend fleshing out the description first.
- All failures classify as `drop` with no transcript content — call-not-connected failures aren't a scenario-fixable problem; redirect to `cekura-internal:debug-run` for the underlying telephony/agent-config issue.
- The user asks for "one scenario per failed call" — push back. Per-call scenarios overfit and dilute the regression set; cluster first.
- The agent already has > 30 scenarios with > 80% coverage of the failure modes seen — say so explicitly. "Your current coverage looks complete given the last <N> calls; consider tightening metrics instead via `cekura-internal:suggest-metrics`."

---

## Quick reference — failure modes

| Emoji | Code | Typical scenario_type | Cluster signal |
|---|---|---|---|
| 🛑 | drop | conditional_actions | ended_reason + short duration |
| 🌀 | drift | instruction | content outside `agent_description` |
| 👻 | hallucination | instruction | fact not in KB/description |
| 🔧 | tool_error | conditional_actions | tool error / unused tool result |
| 🎯 | workflow_miss | conditional_actions | required step skipped |
| 🤔 | comprehension | instruction | caller repeats themselves |
| 🚪 | refusal | instruction | "I can't help with that" inside scope |
| ⚡ | latency | (metric, not scenario) | latency metric outliers |
| 🧨 | safety | instruction | PII / disallowed content |
