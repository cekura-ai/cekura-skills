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
- `headers`: up to 20 headers with string values. `Content-Type`, `Content-Length`, `Content-Encoding`, `Transfer-Encoding`, `Connection`, `Set-Cookie` and `Strict-Transport-Security` are not allowed.
- `delay_ms`: 0–30000. Default 0.

How the agent sees a status of 400 or above:
- **Webhook tools** get that HTTP status and the headers, with `output` as the body.
- **VAPI function tools** get HTTP 200 with the result `Error 503: {"detail":"Service temporarily unavailable"}`.
- **MCP tools** get a tool result with `isError: true` and the same text.

One input can only have one outcome, so give the failure case its own input.

## Matching a Format with a Pattern

When every value in a format should get the same reply, write the input value as a pattern (`"r'...'"`) instead of one mapping per value:

```json
{
  "input": {"phone_number": "r'(\\+?1)?4155551234'"},
  "output": {"borrower_id": "B001", "first_name": "John", "last_name": "Doe"}
}
```

This one mapping answers `4155551234`, `14155551234` and `+14155551234`.

- The whole value must match, ignoring case. Numbers are matched as text.
- Mock data is JSON, so backslashes are doubled (`\\d`, `\\+`). Character classes such as `[0-9]` avoid them.
- Patterns use RE2 syntax: no backreferences (`\1`) or lookarounds (`(?=...)`), repeat counts up to 1000, at most 200 characters. An invalid pattern is rejected on save.
- A call whose arguments are exactly a mapping's plain values gets that mapping even when a pattern also matches. Otherwise list order decides, so put specific mappings before a pattern catch-all.
- Values that need different replies still need one mapping each; a pattern gives every value it accepts the same reply.

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
- **`information`** is an array of input/output mappings — Cekura matches incoming tool calls to the closest input and returns the corresponding output
- **`freetext_params`** — Parameter names to skip during mock matching (free-text fields like "notes" or "reason" that vary per call)
- **Phone format variants** — For phone-based lookups, add mappings for ALL variants: 10-digit, 11-digit with leading 1, and full E.164, or one pattern mapping that accepts all three
- **Patterns** — An input value written `"r'...'"` matches every value the regex accepts. See [Matching a Format with a Pattern](#matching-a-format-with-a-pattern)
- **Chain dependencies** — If tool B depends on output from tool A, the mock data must be consistent across tools
