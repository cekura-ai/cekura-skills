# Mock Tool Design — Detailed Guide

Detailed guidance for setting up mock tools (Phase 4 of the create-agent flow). The eval-design skill has a parallel guide focused on per-scenario mappings; this one focuses on initial setup.

## Per-Input Branching — Mock Tools Need Multiple Mappings

**A single input/output mapping per tool is NOT enough.** Each tool needs entries for every distinct input the agent might send during testing. If a tool accepts different parameters that should return different results, each variant needs its own mapping.

**Example:** A `load_game_info` tool that returns different content based on a `topic` parameter:

```json
{
  "name": "load_game_info",
  "description": "Loads game information by topic",
  "information": [
    {
      "input": {"topic": "lore"},
      "output": {"title": "World Lore", "content": "The galaxy was colonized in 2847..."}
    },
    {
      "input": {"topic": "combat"},
      "output": {"title": "Combat Guide", "content": "Weapons have three tiers: basic, advanced, elite..."}
    },
    {
      "input": {"topic": "trading"},
      "output": {"title": "Trading Manual", "content": "Credits can be earned through cargo runs..."}
    }
  ]
}
```

**When designing mock data, think about:**
- What different inputs will the main agent send to this tool across all test scenarios?
- What should each distinct input return?
- What error cases matter? (Add a mapping with a `response` status code — see [Simulating Tool Failures and Latency](#simulating-tool-failures-and-latency))

If you only create one mapping, every tool call — regardless of input — returns the same output. This masks bugs where the agent sends the wrong parameters.

## Simulating Tool Failures and Latency

A mapping can have an optional `response` to simulate a failing or slow tool:

```json
{
  "input": {"date": "2026-07-11"},
  "output": {"detail": "Service temporarily unavailable"},
  "response": {"status_code": 503, "headers": {"Retry-After": "30"}, "delay_ms": 2000}
}
```

- `status_code`: 200–299 (except 204 and 205) or 400–599. Default 200.
- `headers`: up to 20 headers with string values. `Content-Type`, `Content-Length`, `Content-Encoding`, `Transfer-Encoding`, `Connection`, `Set-Cookie`, `Strict-Transport-Security`, `Location`, and any `Access-Control-*` or `X-Accel-*` header are not allowed.
- `delay_ms`: 0–5000. Default 0.

How the agent sees a status of 400 or above:
- **Webhook tools** get that HTTP status and the headers, with `output` as the body.
- **VAPI function tools** get HTTP 200 with the result `Error 503: {"detail":"Service temporarily unavailable"}`.
- **MCP tools** get a tool result with `isError: true` and the same text.

Without state, one input has one outcome, so give the failure case its own input. For "fails once, then succeeds on retry", use [Stateful Mocks](#stateful-mocks).

## Entry Format

A simple mapping is `{input, output}` and needs nothing else. Every other key is optional:

| Key | Use it for |
|---|---|
| `input` (required) | The arguments the mapping answers. Only arguments present in both the mapping and the call are compared, so leave free-text arguments (notes, reason) out. |
| `output` (required) | What the tool returns. |
| `response` | Status code, headers, delay — see above. |
| `match: "exact"` | A near match must not count (identity checks, IDs). |
| `state`, `then` | A later call in the same call must see an earlier one (retry, booking then lookup). |

Default to plain `{input, output}` mappings. Add `match`, `state` or `then` only when the scenario needs that behavior.

## Exact Matching

By default a call gets the mapping whose input matches, or failing that the closest one, so a wrong date of birth can still receive another caller's record. Add `"match": "exact"` when a near match must not count: every key in `input` must then be in the call with an equal value. Comparison still ignores case and treats `"750"` and `750.00` as equal; extra arguments in the call are ignored. An exact mapping is never picked as the closest match.

To decide what a wrong input gets, add an exact mapping with an empty `input` **last**; it answers any call no earlier mapping matched:

```json
{"input": {}, "match": "exact", "output": {"detail": "No patient matches those details"}, "response": {"status_code": 404}}
```

## Stateful Mocks

Use state only when an earlier tool call in the same call must change a later reply: a booking that fails once and succeeds on retry, a lookup that shows what was just booked, a cancellation that can't happen twice. Everything else stays stateless.

**Prerequisite — Cekura must tell calls apart.** Retell (call or chat ID; Cekura turns off the tool's "Args only" when it points the tool at the mock), VAPI (call ID) and LiveKit with the Cekura SDK (room name) are automatic. Everything else — LiveKit without the SDK, custom/self-hosted agents, MCP clients — must send an `X-Cekura-Mock-Session` header on every mock request, with a value unique to the call and constant for the whole call (their own call ID, or the LiveKit room name). Without a call ID the call stays in `"start"` and `then` is ignored, so retry-then-success tests silently get the first reply every time. On Retell, if the Mock toggle was enabled before stateful mocks shipped, turn it off and on again.

**Format** — two optional keys on a mapping:

- `state`: a name or a list of names. The mapping answers only while the call is in one of them. A mapping without `state` answers in any state.
- `then`: a name. After the mapping replies (error replies included), the call moves to this state.

Every call starts in `"start"`; other names are free text up to 64 characters. One state is shared by all of the agent's mock tools, so a booking tool's `then` changes what a lookup tool returns. The next call starts in `"start"` again.

```json
[
  {"input": {"patient_id": "P-1001", "slot_id": "SLOT-9"}, "state": "start",
   "output": {"detail": "Scheduling system busy, please retry"}, "response": {"status_code": 503}, "then": "retried"},
  {"input": {"patient_id": "P-1001", "slot_id": "SLOT-9"}, "state": ["retried", "booked"],
   "output": {"status": "booked", "appointment_id": "APT-2"}, "then": "booked"}
]
```

with `get_appointments` holding a plain `{"input": {"patient_id": "P-1001"}, ...}` mapping (APT-1 only) plus the same input with `"state": "booked"` (APT-1 and APT-2).

**Which mapping answers:** mappings whose input matches, in list order; one whose `state` holds beats one without `state`; if none matches, the closest match among mappings with neither `state` nor `match: "exact"`; otherwise the tool's no-match reply. Stateful mappings never answer by closest match, so give them the exact values the scenario uses.

**Rules:**
- Same input in different states is allowed. Same input and same state with different outputs is rejected.
- List every state a mapping should keep answering in (`["retried", "booked"]` above), or a repeat call gets no match.
- Write the evaluator so the agent's calls happen in the order the states assume (fail → retry → read-back).

## Tool Data Design

Help the user design mock data by asking:
1. "What are the main tools and what data do they expect as input?"
2. "For each tool, what are the different inputs the main agent might send?" (different users, topics, actions, error cases)
3. "What should each distinct input return?"
4. "Do any tools depend on data from other tools?" (chain dependencies — downstream tool inputs must match upstream tool outputs)

For each scenario the user wants to test, they'll need a matching set of mock data across all related tools. Plan the full data graph: user lookup → account data → transaction history → payment methods. All IDs and references must be consistent.

## Critical: Append-Not-Replace

Mock tools are managed via `PATCH /v2/aiagents/{id}/` using the `mock_tools` field. The entire list is replaced on each PATCH. To add or update mappings without losing existing ones:

1. `GET /v2/aiagents/{id}/?ql={mock_tools}` to fetch current tools and their `id` values
2. Merge new mappings into the existing `mock_data` arrays
3. `PATCH /v2/aiagents/{id}/` with the full `mock_tools` list (include `id` for existing tools)

A PATCH that omits an existing tool **removes it entirely**.

## Key Rules Reminder

- **`name`** must exactly match the tool name in the main agent description (max 64 chars, alphanumeric + underscores + hyphens)
- **`information`** is an array of input/output mappings — Cekura returns the output of the mapping whose input matches the call, else the closest one (see [Entry Format](#entry-format))
- **Free-text arguments** — leave fields like "notes" or "reason" out of `input`; arguments a mapping does not list are never compared. `freetext_params` is stored on the tool but does not change matching
- **Phone format variants** — For phone-based lookups, add mappings for ALL variants: 10-digit, 11-digit with leading 1, and full E.164
- **Chain dependencies** — If tool B depends on output from tool A, the mock data must be consistent across tools
