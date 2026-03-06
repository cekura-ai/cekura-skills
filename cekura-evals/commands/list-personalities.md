---
name: list-personalities
description: Browse available Cekura caller personalities for evaluators
argument-hint: ""
allowed-tools: ["Bash"]
---

# List Available Personalities

Fetch and display all available caller personalities from the Cekura platform.

## Process

1. **Fetch personalities**:
```bash
source ${CLAUDE_PLUGIN_ROOT}/scripts/cekura-api.sh
list_personalities
```

2. **Present in a table**: Display key attributes:
   - ID, Name, Language, Accent, Provider
   - Interruption level, Background noise

3. **Help with selection**: If the user is creating evaluators, suggest appropriate personalities based on:
   - Language requirements (match the agent's supported languages)
   - Testing goals (high interruption for stress testing, calm for happy path)
   - Provider compatibility (11labs vs cartesia)

**Important:** Personalities control how the testing agent *sounds* (voice, accent, interruption, noise). Scenario instructions control what the testing agent *says*. Writing "speak in a mumbling voice" in instructions has no effect — use a personality with those characteristics instead.

## Personality Attributes

| Attribute | Description |
|-----------|-------------|
| `language` | ISO language code (en, es, etc.) |
| `accent` | Voice accent style |
| `voice_model` | e.g., "sonic-3" |
| `provider` | "11labs" or "cartesia" |
| `interruption_level` | How often the caller interrupts |
| `background_noise` | Ambient sound configuration |
