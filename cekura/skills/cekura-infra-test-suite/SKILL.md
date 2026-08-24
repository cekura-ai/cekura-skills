---
name: cekura-infra-test-suite
description: >
  Use when the user asks to create, update, or review a source-controlled Cekura JSON CI/CD test
  suite for a voice AI repository; create Tests-as-Code specs; turn a voice-agent code change into
  regression coverage; add deterministic Cekura voice tests to CI; or test an STT, LLM, TTS, VAD,
  interruption, idle-timer, DTMF, or call-lifecycle pipeline. Inspects the repository before
  authoring a compact JSON suite and validates it safely with Cekura dry-run.
license: MIT
compatibility: Requires a Cekura account (https://dashboard.cekura.ai) — sign in via OAuth or use an API key.
metadata:
  author: cekura
  version: "0.2.0"
---

# Cekura Voice AI Infrastructure CI/CD Suite

Build a compact, reviewable Cekura test suite **in the voice-agent repository**. The deliverable is a
JSON spec that CI submits to Cekura's Tests-as-Code endpoint. It is not a folder of persistent
dashboard evaluators.

Use this skill when the repository, its deployment target, and the Cekura agent are in scope. For
one-off dashboard evaluators or adaptive quality scenarios, use `cekura-eval-design` instead.

## API Access — Cekura MCP Server

Authenticate the Cekura MCP server with OAuth or an API key before discovering the target. Use MCP
reads where the client provides them. Tests-as-Code validation is the public HTTPS endpoint below;
when using it directly, take the base URL and API key from the user's local environment or CI secret,
never from source control. If the target environment lacks the endpoint, report that fact and do not
fall back to creating dashboard evaluators.

## Safety and scope

- Inspect the repository before proposing coverage. Do not infer providers, transports, tools, or
  pipeline behavior from a framework name alone.
- Treat Cekura as read-only. You may `GET` agent, enabled metric, personality, test-profile, schema,
  and export data. The only permitted write-like request is
  `POST /test_framework/v1/scenarios/run_scenarios_json/?dry_run=true`.
- Never create, edit, delete, duplicate, or export-and-reimport scenarios, test profiles,
  personalities, metrics, agents, or folders. Never run the suite live unless the user separately
  asks for it after reviewing the spec and accepts the cost.
- Never place API keys, phone numbers, production customer data, or deployment secrets in a spec or
  committed workflow. Use CI secrets and non-sensitive, staging-compatible profile data.
- Preserve existing unrelated repository changes. Limit edits to the agreed spec, its coverage note,
  and CI files explicitly requested by the user.

## Required inputs

Establish these before authoring. Discover them from the repository or Cekura where possible; ask
only for what cannot be safely inferred.

1. **Target** — Cekura base URL, project/agent ID, channel, and any request-only connection data.
   `agent_id` belongs in the run request, never in the JSON spec.
2. **Execution contract** — which deployed bot is under test, how CI reaches it, and whether this is
   a PR suite, deploy gate, or both. A spec is reusable, but the run request supplies the target.
3. **Available dependencies** — enabled metrics, usable personality IDs, and whether a saved
   personality is required because it has non-inline settings.
4. **Repository intent** — supported languages, user journeys, staging fixtures/mocks, and explicit
   non-goals. Do not fabricate a business flow that the code and fixtures cannot support.

If a required target, enabled metric, or staging fixture is unknown, prepare the repository-side
plan and mark that case blocked. Do not silently substitute a weaker check.

## Workflow

### 1. Read the actual agent path

Start from the runtime entrypoint and trace the call path rather than searching only for provider
names. Inventory, with source references:

- inbound/outbound direction and transport (phone, WebSocket, WebRTC, SIP, LiveKit, Pipecat, etc.);
- STT, LLM, TTS, VAD/turn detection, buffering, endpointing, and interruption processors;
- prompt/config loading and per-session variables;
- tools, handoff/end-call behavior, DTMF/IVR, voicemail, idle/timeout, retry, and error handling;
- supported languages and any code paths that switch language/provider; and
- test fixtures, mocks, staging dependencies, and existing Cekura JSON or workflow files.

For every candidate behavior, record its **seat and transport**. The simulated caller and the
agent-under-test can execute different code. Coverage that exercises only one seat does not prove a
regression is covered in the other.

### 2. Make a coverage matrix before editing

Create or update a concise coverage note beside the spec. Use this table:

| Code path / source evidence | Behavior to prove | Seat + transport | Transcript-observable assertion | Case key | Status |
| --- | --- | --- | --- | --- | --- |

Only include behavior that the suite can exercise and judge. For example, assert that an expected
spoken response occurs after an interruption; do not assert that a volume tag, ambient sound, or
internal processor itself ran. Mark a row `uncovered` when it needs a different transport, test
fixture, metric, or backend capability, and state what is missing.

Prefer one 10–12 case deploy-grade suite unless the user asks for tiers. If a fast PR suite is also
needed, keep it compact (typically 4–6 cases) and make the broad suite a superset. Merge compatible
turns into a single case; add a case only for a distinct subsystem, seat, transport, provider, or
terminal call lifecycle.

### 3. Choose the spec shape

Use the live schema returned by the target environment as the authority. A v1 spec normally has:

```json
{
  "$schema": "https://docs.cekura.ai/schemas/test-suite/v1.json",
  "version": "1",
  "suite": { "name": "…", "description": "…" },
  "defaults": { "frequency": 1, "language": "en", "max_duration": 180 },
  "scenarios": []
}
```

Keep stable, descriptive `key` values. Put reusable defaults at the suite level only when every
case actually shares them. Set `language` explicitly on every conditional-actions case.

For configuration that controls the agent under test, preserve the entire discovered session blob:

```json
"test_profile": {
  "name": "staging-caller-and-agent-config",
  "agent_variables": { "...": "full agent-under-test configuration" },
  "caller_variables": { "...": "simulated caller context" }
}
```

`agent_variables` become the agent-under-test configuration; `caller_variables` drive the simulated
caller and `{{test_profile.key}}` substitution. Do not move fields between them. Do not invent a
profile simply to make the JSON look self-contained.

An inline personality is intentionally limited. If the required saved personality uses network
simulation, speaking plans, message plans, generation config, background volume, or interruption
level, keep the personality reference by ID and document that dependency. Do not drop those settings
to force an inline object through validation.

### 4. Author deterministic, observable cases

Use `type: "conditional_actions"` for deterministic infrastructure and regression coverage. All
conditions on **both seats** use `fixed_message: true`; no LLM-generated caller responses belong in
a CI gate. Every condition has `id`, `condition`, `action`, `type`, and `fixed_message`. The first
condition is `id: 0`, `condition: "FIRST_MESSAGE"`.

Use the public `cekura-eval-design` skill and its conditional-actions reference while authoring:

- `<interruption time="Xs" />` begins an `action_followup`; use a positive time after a greeting or
  lead-in, and `0s` only when speech is already in progress.
- `<ivr ... />` and `<voicemail ... />` occupy the entire action. Put follow-on speech in a later
  `action_followup`.
- `<silence>` can be interrupted; `<hold>` cannot. Test the behavior selected by the code path.
- `<speed>` and `<volume>` start the action and require quoted, valid ratios. Use them to exercise
  the path, but never make an inaudible property the assertion.
- Do not reference stored audio clips. Do not hand-author unsupported tags.

Every `expected_outcome` must be narrow and transcript-verifiable: required spoken content, absence
of leaked literal tag text, turn order, tool-visible outcome when it appears in the transcript, or
the terminal end of a call. Terminal assertions such as end-call and max-duration go last. Do not
weaken an assertion to turn a real failure green.

Select metrics by their enabled slug or ID only after checking the target agent. A missing or
disabled metric is a validation error to fix, not a reason to remove that metric from the case.

### 5. Review changes safely

For an update, determine the change against the PR merge base, not just the last commit:

```bash
git fetch origin main
BASE_REF="${PR_BASE_REF:-origin/main}"
MERGE_BASE="$(git merge-base "$BASE_REF" HEAD)"
git diff --name-status "$MERGE_BASE" HEAD
git diff "$MERGE_BASE" HEAD -- <runtime paths> <existing suite paths>
```

Before editing, complete the coverage matrix row for every changed runtime symbol. `No suite change`
is a valid conclusion when no observable behavior changed. Do not modify unrelated cases, relax
expected outcomes, or add generic provider tests merely because a nearby file changed.

### 6. Validate the committed artifact

Use a dry run for the whole file. It validates syntax, metrics, personalities, profiles, target
compatibility, planned runs, and estimated cost without creating objects or placing a call:

```bash
curl -sS -X POST \
  -H "X-CEKURA-API-KEY: $CEKURA_API_KEY" \
  -H "Content-Type: application/json" \
  "$CEKURA_BASE_URL/test_framework/v1/scenarios/run_scenarios_json/?dry_run=true" \
  -d '{"agent_id": 123, "spec": { ... }}'
```

Require `valid: true`. Check that each planned case has the intended metrics and reports an inline
profile when an inline `test_profile` was supplied. Save the validation response only if it contains
no credentials or sensitive caller data. If dry-run validation needs a write beyond `dry_run=true`,
stop and report the blocker.

## Handoff

Leave the repository with:

- the JSON spec or specs, formatted and source-controlled;
- a coverage note mapping code paths to stable case keys, including explicit uncovered rows;
- a short README note describing the target assumptions, Cekura dependencies (metrics,
  personalities, channels), and how CI invokes the endpoint; and
- the dry-run result or the exact validation blocker.

Report case count, target channel/seat coverage, dependencies, and anything that needs a live run or
a backend capability. A dry-run proves the spec is valid; it does not prove a bot deployment works.
