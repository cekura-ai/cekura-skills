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
- What error cases matter? (Add a mapping with an error response for tool-failure scenarios)

If you only create one mapping, every tool call — regardless of input — returns the same output. This masks bugs where the agent sends the wrong parameters.

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
- **Phone format variants** — For phone-based lookups, add mappings for ALL variants: 10-digit, 11-digit with leading 1, and full E.164
- **Chain dependencies** — If tool B depends on output from tool A, the mock data must be consistent across tools
