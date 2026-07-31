# Bland Mode

Bland is a managed provider. Use `BLAND_API_KEY` and the provider's live
persona/tool configuration as the source of truth; changes are live after apply.

- Voice: `provider.agent_id` is the Bland persona ID.
- Chat: `chat_agent_details.config.agent_id` is the Bland pathway ID.
- Fetch the active persona version and referenced tools before editing; apply only
  fields returned by the live provider API/MCP, then re-fetch to verify.
- Keep voice and chat identifiers separate. If a provider operation is unavailable,
  stop rather than guessing field paths or editing a different target.
