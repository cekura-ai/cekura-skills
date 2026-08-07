# Retell Mode

Retell is a managed provider. Use `RETELL_API_KEY`; changes go live immediately.

## Fetch

- Fetch the agent with `GET /get-agent/{id}`; use `GET /get-chat-agent/{id}` for
  chat agents when required.
- Follow `response_engine` to the active Retell LLM or conversation flow.
- Fetch that configuration and treat its prompt and tools as the source of truth.
  Tools commonly live in `general_tools` or flow nodes.
- Preserve the active version when the provider returns one.

## Clone

Clone the referenced LLM/flow and its agent, preserving the response-engine
type, tools, built-ins, and end-call behavior. Rebind the disposable Cekura
agent to the clone before validation. If a required provider/MCP operation is
unavailable, stop and do not edit the original.

## Apply and sync

Apply changes to the owning Retell LLM or flow through the provider API/MCP.
Send the complete array being changed, then re-fetch the agent and owning
configuration to verify the edit before validation.

The provider configuration is authoritative; do not edit the Cekura
`description` as a substitute.
