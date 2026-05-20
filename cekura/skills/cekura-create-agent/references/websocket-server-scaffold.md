# WebSocket Server Scaffold — Cekura Protocol

Use this when the user selects "WebSocket endpoint" as their connection type. Offer to generate a working WebSocket server in their tech stack that speaks Cekura's protocol.

---

## Cekura WebSocket Protocol

Cekura connects to the agent's WebSocket server as a **client**. The agent must run a WebSocket server at a `wss://` (or `ws://` for local testing) URL.

### Headers Cekura sends on connect

| Header | Value |
|--------|-------|
| `X-VOCERA-SECRET` | The Cekura API key — use this to authenticate the connection |
| `X-VOCERA-SCENARIO-ID` | Scenario being tested |
| `X-VOCERA-RESULT-ID` | Result ID |
| `X-VOCERA-RUN-ID` | Run ID |
| `X-*` (any) | Test profile fields prefixed with `X-` |

### Message format (JSON text frames)

**Cekura → Agent (incoming):**
```json
{"content": "Hello, I need help with my order"}
```

**Agent → Cekura (outgoing):**
```json
{"content": "Sure, can I get your order number?"}
```

**Function call from agent → Cekura:**
```json
{"role": "Function Call", "data": {"id": "call_123", "name": "get_order", "arguments": "{\"order_id\": \"ABC\"}"}}
```

**Cekura returns function result → Agent:**
```json
{"role": "Function Call Result", "data": {"id": "call_123", "result": "{\"status\": \"shipped\"}"}}
```

**Agent ends the call:**
```json
{"content": "Thank you, goodbye!", "type": "end_call"}
```

---

## Scaffolds by Language

Before generating, ask the user:
1. What language/framework? (Python, Node.js/TypeScript, Go, etc.)
2. Does their agent call any tools/functions during the conversation?
3. Is this for local testing (ws://) or production (wss://)?
4. Should it validate the `X-VOCERA-SECRET` header?

---

### Python (websockets library)

```python
import asyncio
import json
import websockets

CEKURA_SECRET = "your-cekura-api-key"  # Set to your X-CEKURA-API-KEY

async def handle_connection(websocket):
    # Authenticate
    secret = websocket.request_headers.get("X-VOCERA-SECRET")
    if secret != CEKURA_SECRET:
        await websocket.close(1008, "Unauthorized")
        return

    run_id = websocket.request_headers.get("X-VOCERA-RUN-ID")
    scenario_id = websocket.request_headers.get("X-VOCERA-SCENARIO-ID")
    print(f"[Cekura] Connected — run={run_id} scenario={scenario_id}")

    async for raw_message in websocket:
        message = json.loads(raw_message)

        # Handle function call result from Cekura
        if message.get("role") == "Function Call Result":
            result = json.loads(message["data"]["result"])
            # TODO: process function result
            continue

        # Handle regular user message
        user_text = message.get("content", "")
        print(f"[User] {user_text}")

        # TODO: call your agent/LLM here
        agent_response = await your_agent_respond(user_text)

        # Send response back
        await websocket.send(json.dumps({"content": agent_response}))

        # If agent wants to end the call
        # await websocket.send(json.dumps({"content": "Goodbye!", "type": "end_call"}))

async def your_agent_respond(user_text: str) -> str:
    # Replace with your actual agent logic
    return f"You said: {user_text}"

async def main():
    async with websockets.serve(handle_connection, "0.0.0.0", 8765):
        print("WebSocket server started on ws://localhost:8765")
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    asyncio.run(main())
```

Install: `pip install websockets`

---

### Node.js / TypeScript (ws library)

```typescript
import WebSocket, { WebSocketServer } from "ws";
import http from "http";

const CEKURA_SECRET = process.env.CEKURA_API_KEY ?? "";

const server = http.createServer();
const wss = new WebSocketServer({ server });

wss.on("connection", (ws, req) => {
  const secret = req.headers["x-vocera-secret"];
  if (secret !== CEKURA_SECRET) {
    ws.close(1008, "Unauthorized");
    return;
  }

  const runId = req.headers["x-vocera-run-id"];
  console.log(`[Cekura] Connected — run=${runId}`);

  ws.on("message", async (data) => {
    const message = JSON.parse(data.toString());

    // Handle function call result
    if (message.role === "Function Call Result") {
      const result = JSON.parse(message.data.result);
      // TODO: process function result
      return;
    }

    // Handle regular user message
    const userText = message.content ?? "";
    console.log(`[User] ${userText}`);

    // TODO: call your agent/LLM here
    const agentResponse = await yourAgentRespond(userText);

    ws.send(JSON.stringify({ content: agentResponse }));

    // To end the call:
    // ws.send(JSON.stringify({ content: "Goodbye!", type: "end_call" }));
  });
});

async function yourAgentRespond(userText: string): Promise<string> {
  // Replace with your actual agent logic
  return `You said: ${userText}`;
}

server.listen(8765, () => {
  console.log("WebSocket server started on ws://localhost:8765");
});
```

Install: `npm install ws @types/ws`

---

### FastAPI + WebSockets (Python)

```python
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Header, HTTPException
import json
import asyncio

app = FastAPI()
CEKURA_SECRET = "your-cekura-api-key"

@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    x_vocera_secret: str = Header(None),
    x_vocera_run_id: str = Header(None),
    x_vocera_scenario_id: str = Header(None),
):
    if x_vocera_secret != CEKURA_SECRET:
        await websocket.close(code=1008)
        return

    await websocket.accept()
    print(f"[Cekura] Connected — run={x_vocera_run_id}")

    try:
        while True:
            raw = await websocket.receive_text()
            message = json.loads(raw)

            if message.get("role") == "Function Call Result":
                # TODO: handle function result
                continue

            user_text = message.get("content", "")
            agent_response = await your_agent_respond(user_text)
            await websocket.send_text(json.dumps({"content": agent_response}))

    except WebSocketDisconnect:
        print("[Cekura] Disconnected")

async def your_agent_respond(user_text: str) -> str:
    # Replace with your actual agent logic
    return f"You said: {user_text}"
```

Run with: `uvicorn main:app --host 0.0.0.0 --port 8765`

---

## Exposing Local Servers to Cekura

For local development, the server needs a public `wss://` URL. Recommend:

```bash
# ngrok (easiest)
ngrok http 8765
# gives you: https://abc123.ngrok.io → wss://abc123.ngrok.io

# cloudflare tunnel
cloudflare tunnel --url http://localhost:8765
```

Set the resulting URL as `provider.chat_agent_details.config.url` on the Cekura agent.

---

## With Tool Calls

If the agent makes function calls during the conversation:

```python
# Agent initiates a function call
await websocket.send(json.dumps({
    "role": "Function Call",
    "data": {
        "id": "call_001",
        "name": "get_account_info",
        "arguments": json.dumps({"account_id": "ACC123"})
    }
}))

# Wait for Cekura to return the mock result
raw = await websocket.recv()
result_msg = json.loads(raw)
if result_msg.get("role") == "Function Call Result":
    result = json.loads(result_msg["data"]["result"])
    # use result in next agent response
```
