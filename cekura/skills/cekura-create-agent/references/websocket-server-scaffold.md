# WebSocket Server — Cekura Protocol

Use this when the user selects "WebSocket endpoint" as their connection type and needs a server built or explained.

**Official example repo:** https://github.com/cekura-ai/llm-websocket-server-example

Clone and adapt this — it is a complete, production-quality WebSocket server that speaks Cekura's protocol out of the box.

---

## Design Principle: One Server, All Scenarios

**The server must be generic — not hardcoded to a single flow.** Every value that varies between test scenarios must be:
1. Read by the server from per-run context (Cekura headers or connection payload)
2. Registered as a dynamic variable in Cekura (so Cekura generates and injects the right value per run)

When adapting the server, identify everything that would need to change for a different test scenario — caller state, persona, account data, language, flow type, feature flags — and replace each hardcoded value with a variable read from the connection context. The goal is a single server URL that can exercise every scenario through parameterization, not a separate server or hardcoded path per scenario.

---

## Quickstart from the Official Repo

```bash
git clone https://github.com/cekura-ai/llm-websocket-server-example.git
cd llm-websocket-server-example
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Edit `main.py` — update two things:
1. Your LLM credentials (OpenAI / Azure OpenAI API key)
2. `SYSTEM_PROMPT` — your main agent's system prompt

```bash
python main.py
# WebSocket server started on ws://0.0.0.0:8765
```

Then expose it publicly with ngrok:
```bash
ngrok http 8765
# → wss://abc123.ngrok.io
```

Set that URL as `provider.chat_agent_details.config.url` on the Cekura agent.

---

## Cekura WebSocket Protocol

Cekura connects to the agent's WebSocket server as a **client**. The server must handle:

### Message format (JSON text frames)

**Cekura → Agent (user turn):**
```json
{"content": "Hello, I need help with my order"}
```

**Agent → Cekura (agent response):**
```json
{"content": "Sure, can I get your order number?"}
```

**Agent → Cekura (tool/function call):**
```json
{
  "role": "Function Call",
  "data": {
    "id": "call_123",
    "name": "get_order",
    "arguments": {"order_id": "ABC"}
  }
}
```

**Cekura → Agent (tool result):**
```json
{
  "role": "Function Call Result",
  "data": {"id": "call_123", "result": {"status": "shipped"}}
}
```

**Agent ends the conversation:**
```json
{"content": "Thank you, goodbye!", "type": "end_call"}
```

**Keepalive (prevent Cekura inactivity timer during slow LLM calls):**
```json
{"metadata": {"keepalive": true}}
```

### Agent speaks first

If the agent should open the conversation (most outbound/voice agents do), send the greeting immediately on connection before waiting for any message:

```python
async def handle_websocket(websocket):
    greeting = "Hello! How can I help you today?"
    await websocket.send(json.dumps({"content": greeting}))
    # then seed chat history with the greeting as assistant turn
    async for message in websocket:
        ...
```

---

## Key Patterns from the Reference Implementation

### 1. Keepalive task (essential for slow LLM calls)

Cekura has an inactivity timer. For LLM calls that take >25 seconds, send keepalive pings:

```python
async def outer_keepalive():
    while True:
        await asyncio.sleep(25)
        try:
            await websocket.send(json.dumps({"metadata": {"keepalive": True}}))
        except Exception:
            break

keepalive = asyncio.create_task(outer_keepalive())
# ... do LLM call ...
keepalive.cancel()
```

### 2. Tool call reporting to Cekura

When the main agent calls a tool, report it to Cekura so it appears in the transcript:

```python
# Report tool call
await websocket.send(json.dumps({
    "role": "Function Call",
    "data": {
        "id": tool_call.id,
        "name": tool_call.function.name,
        "arguments": json.loads(tool_call.function.arguments),
    }
}))

# Execute tool
result = await call_my_tool(tool_args)

# Report result
await websocket.send(json.dumps({
    "role": "Function Call Result",
    "data": {
        "id": tool_call.id,
        "result": result,
    }
}))
```

### 3. Tool URL pattern (Cekura mock tools)

The reference implementation calls Cekura's mock tool endpoint directly:

```python
TOOL_URL = "https://api.cekura.ai/test_framework/v1/aiagents/{agent_id}/tool/{tool_name}/"

async def call_tool(tool_args: dict) -> str:
    async with aiohttp.ClientSession() as session:
        async with session.post(TOOL_URL, json=tool_args) as resp:
            result = await resp.json()
            return json.dumps(result)
```

This lets Cekura's mock tool system return the configured mock responses during testing.

### 4. Context window management

Keep the chat history bounded to avoid token bloat:

```python
if len(chat_histories[session_id]) > 32:  # system prompt + 30 exchanges
    tail = chat_histories[session_id][-30:]
    # advance past any orphaned tool/assistant messages
    while tail and tail[0].get("role") != "user":
        tail = tail[1:]
    chat_histories[session_id] = [chat_histories[session_id][0]] + tail
```

---

## What to Customise — Match the Main Agent Exactly

When adapting the repo, every configuration must match the main agent. Do not use defaults:

1. **LLM client** — use the exact same provider the main agent uses (OpenAI, Anthropic, Azure, Gemini, etc.)
2. **Model name** — exact model the main agent uses (e.g. `gpt-4o`, `claude-3-5-sonnet-20241022`, `gemini-2.5-flash`) — not a cheaper or default substitute
3. **Temperature** — exact temperature from the main agent's config, not 0.0 or any assumed default
4. **Max tokens** — match the main agent's token limit setting
5. **`SYSTEM_PROMPT`** — the full, unmodified system prompt from Phase 4
6. **`TOOLS`** — exact tool schemas matching the main agent's tool definitions
7. **`TOOL_URL`** — Cekura mock tool endpoint so responses are controlled during testing
8. **`GREETING`** — exact opening message the main agent sends (or omit if testing agent speaks first)
9. **Dynamic variables** — read them the same way the main agent does (same headers, same keys)
10. **Port** — set via `PORT` environment variable

---

## Minimal Skeleton (if not using the repo)

```python
import asyncio
import json
import websockets

SYSTEM_PROMPT = "You are a helpful assistant."

chat_histories = {}

async def handle_websocket(websocket):
    session_id = id(websocket)
    chat_histories[session_id] = [{"role": "system", "content": SYSTEM_PROMPT}]

    # Optional: agent speaks first
    greeting = "Hello! How can I help?"
    await websocket.send(json.dumps({"content": greeting}))
    chat_histories[session_id].append({"role": "assistant", "content": greeting})

    async for raw in websocket:
        msg = json.loads(raw)
        user_text = msg.get("content", "")

        chat_histories[session_id].append({"role": "user", "content": user_text})

        # TODO: call your LLM here
        reply = "Echo: " + user_text

        chat_histories[session_id].append({"role": "assistant", "content": reply})
        await websocket.send(json.dumps({"content": reply}))

async def main():
    async with websockets.serve(handle_websocket, "0.0.0.0", 8765):
        print("ws://localhost:8765")
        await asyncio.Future()

asyncio.run(main())
```

---

## Running the Server and Getting the ngrok URL (do this yourself in Bash)

Start the server in the background:
```bash
# Run in background — replace with the actual start command
python bot.py &
sleep 2  # give it time to start
```

Start ngrok and capture the public URL:
```bash
# Start ngrok in background, log to file
ngrok http 8765 --log=stdout > /tmp/ngrok.log 2>&1 &
sleep 3  # wait for ngrok to establish tunnel

# Extract the wss:// URL from ngrok output
NGROK_URL=$(grep -o 'https://[a-z0-9-]*.ngrok[a-z.-]*/[a-z0-9]*\|https://[a-z0-9-]*.ngrok-free.app' /tmp/ngrok.log | head -1 | sed 's/https:/wss:/')
echo "WebSocket URL: $NGROK_URL"
```

Use `$NGROK_URL` as the `chat_agent_details.config.url` value.
