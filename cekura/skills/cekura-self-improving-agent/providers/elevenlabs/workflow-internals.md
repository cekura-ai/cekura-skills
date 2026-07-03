# ElevenLabs Workflow Internals

Most ElevenLabs agents are single-prompt (see `overview.md`). When `GET /v1/convai/agents/{id}` returns a top-level `workflow: { nodes: {...}, edges: {...} }`, you are editing a **multi-node graph** — the single-prompt mental model does not apply. Each node has its own prompt.

## Node types

- **`start`** — entry-only, **non-conversational**. Never takes a turn; immediately evaluates edges and routes. Never put greeting/first_message logic here.
- **`override_agent`** — an **inline** node. Inherits the base agent's `conversation_config` (model, `built_in_tools`, turn config, voice) and overrides only what you set (`conversation_config.agent.prompt.prompt`, `first_message`). Routes onward via workflow edges. Normal building block.
- **`standalone_agent`** — references an external agent by `agent_id`. **Terminal for workflow routing** — hands off to that agent and does **not** continue through the workflow's edges. Use only for genuine terminal handoffs. Common bug: making a mid-flow node `standalone` and expecting its outgoing edge to fire — it never does.

A **router / branch** is a non-conversational `override_agent` (prompt = "Routing agent. Do not converse.") whose only job is to hold `expression` edges.

## Edges

Each edge has `source`, `target`, and `forward_condition` with `type`:

- **`unconditional`** — always fires (e.g., `start → first node`).
- **`expression`** — **deterministic**, evaluated against dynamic variables. Prefer for anything expressible as variables. Schema:
  ```json
  {"type":"and_operator","children":[
    {"type":"eq_operator",
     "left":{"type":"dynamic_variable","name":"totalQuestionCount"},
     "right":{"type":"string_literal","value":"0"}}
  ]}
  ```
  Operators: `eq_operator`, `neq_operator`, `and_operator`, `or_operator`. **Values compare as strings** — use `"0"`, `"true"`, not integers/bools.
- **`llm`** — a **separate LLM judge call**. The judge sees **only the running transcript + the `condition` text** — it does **NOT** see the node's system prompt. A condition like "transfer after all CORE_QUALIFICATION_QUESTIONS are asked" is meaningless unless you **interpolate the questions into the condition** with `{{var}}`.

**Evaluation order = the node's `edge_order` array; first matching edge wins.** Put deterministic bypass/short-circuit edges first.

`{{dynamic_variable}}` interpolation works in both node prompts and `llm` edge conditions.

Transitions are executed by the **workflow engine**, not by the model calling a tool.

## Where dynamic variables come from (call init)

Every `{{var}}` in node prompts and `expression` / `llm` edge conditions is resolved from `conversation_initiation_client_data.dynamic_variables` passed by the calling system at call start. **In Cekura, those values are the test profile's `main_agent_variables`.**

- The workflow author and profile author must agree on variable **names** — a node whose prompt is `{{allVettingQuestionsAgentPrompt}}` only works if the profile supplies that exact key.
- A variable the profile **omits** falls back to the agent's placeholder default (often junk like `"init from langfuse"`), silently running the node on a garbage prompt or mis-evaluating an edge.
- Supporting a new edge/prompt variable is a **two-sided change**: add the `{{var}}` in the workflow **and** the key in every profile that reaches that node.

## The `transfer_to_agent` trap (most important gotcha)

Inline nodes **inherit the base agent's `built_in_tools`**. If the base has `transfer_to_agent` enabled (even with an empty `transfers` list), every node "sees" a transfer tool it cannot usefully call — routing is edge-driven. Two failure modes:

1. A prompt that says "call `transfer_to_agent` to hand off" — the model tries, there's no valid target, and (on gemini-flash especially) it **collapses into a degenerate repetition monologue** for tens of seconds until an edge eventually fires.
2. Even without an explicit prompt line, the dead-end tool is an attractor at end-of-turn.

**Fix:** in a workflow, **remove `transfer_to_agent` from the base agent** (`conversation_config.agent.prompt.built_in_tools.transfer_to_agent = null`) and strip every "call transfer_to_agent" / "Invisible Transfer" instruction from node prompts. Keep `end_call`. Let edges do all transitions.

## Failure modes and signatures

| Symptom in transcript | Root cause | Fix |
|---|---|---|
| One agent turn + a huge inter-turn gap (long TTS of repeated filler) | `transfer_to_agent` dead-end → repetition collapse | Remove the tool + prompt directive |
| Many alternating agent/user turns stuck in one node | Node ignored its stop/short-circuit rule, OR inherited prior node's interview context | Harden the rule to absolute-override; add an expression bypass edge |
| Last transcript turn far before `call_duration_secs`; trailing dead air; ended by "remote party" | `llm` edge never fired (final turn was interrupted — judge reads "still answering") → stall | Use a deterministic expression edge; don't gate a critical transition on an LLM judge |
| Node runs on a garbage prompt like "init from langfuse" | A dynamic variable wasn't supplied by the profile → fell back to base placeholder | Add the variable to every profile that reaches this node |

## Architectural principles

- **Prefer deterministic `expression` edges** over `llm` edges for any transition expressible via variables.
- **Short-circuit / bypass edges**: when a node would have nothing to do, add an `expression` edge that skips it entirely. Order it first in `edge_order`.
- **Gate `llm` transition edges on a specific, detectable event**, not a vague "after all questions."
- **Inject ground truth into `llm` edges** via `{{…List}}` variables so the judge has a concrete completion test.
- **Harden overriding rules** as "ABSOLUTE — OVERRIDES EVERY OTHER INSTRUCTION" when a conditional rule must beat the prompt's general goals.
- **Data-completeness invariant**: every node a flow can reach must have all its variables supplied (prompt and edge condition vars). A missing var silently becomes a base placeholder.
- **Reconnection / resume flows**: a node entered mid-conversation inherits the full prior transcript — route to skip vetting entirely via deterministic bypass rather than trusting a prompt to suppress re-interviewing.

## API gotchas

- PATCH rejects sending **both** `prompt.tools` and `prompt.tool_ids` — strip expanded `tools` before every workflow PATCH.
- `auto_advance: true` on a node is **feature-gated** — PATCH/create returns `422 feature_not_available` on non-enabled workspaces.
- `update_state` system tool config: `params = {system_tool_type:"update_state", updates:[{variable_name, expression:{type:"string_literal", value}}]}`. System-tool **names must be reserved** — a custom name like `complete_interview` is rejected; reusing `transfer_to_agent` collides and breaks the LLM.
- When editing edges/nodes, send the **full `workflow` object** back (deep-merge doesn't reliably patch nested edge maps); re-fetch and verify the `forward_condition` / `edge_order` landed.

## Debugging a workflow run (ZDR-safe)

ElevenLabs conversation GET **redacts message text** on ZDR/HIPAA workspaces (`<REDACTED>`). Fix structurally:

- Trace **`transcript[i].agent_metadata.workflow_node_id`** per turn to reconstruct the node path and count agent turns per node.
- Classify by shape (see the table): **monologue collapse** = 1 turn + big gap; **conversational loop** = many alternating turns in one node; **stall** = last turn ≪ `call_duration_secs`.
- Confirm **which prompt/variable version actually ran** from the run's captured test-profile snapshot — profiles are snapshotted at result-creation time, so a recent edit may not be reflected in an older run.
- A clean `termination_reason: "end_call tool was called"` with a full node path = the workflow succeeded; a failing evaluation metric is a separate content issue, not a routing failure.
- Do **not** trust the conversation GET's `conversation_initiation_client_data.dynamic_variables` to confirm variable passthrough — for phone/Twilio-outbound calls it returns `{}` even when variables were sent and applied. Verify against the calling system's outbound-request logs instead.
