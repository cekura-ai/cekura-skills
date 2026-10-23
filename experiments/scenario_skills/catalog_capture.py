"""Read-only MCP tools/list capture; never calls a Cekura tool."""
import json
import os
from datetime import datetime, timezone
from urllib.request import Request, urlopen

from .common import digest, private_dir, write


def message(body):
    text = body.decode()
    if text.lstrip().startswith("{"):
        return json.loads(text)
    for line in text.splitlines():
        if line.startswith("data:"):
            result = json.loads(line[5:].strip())
            if "result" in result or "error" in result:
                return result
    raise ValueError("MCP response did not contain a JSON-RPC result")


def capture(directory, credential_env, url="https://api.cekura.ai/mcp", credential_type="oauth"):
    if url != "https://api.cekura.ai/mcp":
        raise ValueError("Capture only the original Cekura MCP endpoint")
    token = os.environ.get(credential_env)
    if not token:
        raise ValueError("Authenticated MCP capture credential unavailable")
    if credential_type not in ("oauth", "api-key"):
        raise ValueError("MCP credential type must be oauth or api-key")
    directory = private_dir(directory)
    headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    headers.update({"Authorization": "Bearer " + token} if credential_type == "oauth" else {"X-CEKURA-API-KEY": token})

    def call(method, params, identifier):
        payload = {"jsonrpc": "2.0", "method": method, "params": params}
        if identifier is not None:
            payload["id"] = identifier
        with urlopen(Request(url, headers=headers, data=json.dumps(payload).encode()), timeout=30) as response:
            session = response.headers.get("Mcp-Session-Id")
            if session:
                headers["Mcp-Session-Id"] = session
            body = response.read()
            if identifier is None:
                return None
            result = message(body)
            if "error" in result:
                raise ValueError("MCP schema discovery returned a protocol error")
            return result["result"]

    call("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                       "clientInfo": {"name": "cekura-synthetic-schema-capture", "version": "1"}}, 1)
    headers["MCP-Protocol-Version"] = "2024-11-05"
    call("notifications/initialized", {}, None)
    tools, cursor, seen = [], None, set()
    for number in range(2, 102):
        result = call("tools/list", {"cursor": cursor} if cursor else {}, number)
        tools.extend(result["tools"])
        cursor = result.get("nextCursor")
        if not cursor:
            break
        if cursor in seen:
            raise ValueError("MCP catalog pagination repeated a cursor")
        seen.add(cursor)
    else:
        raise ValueError("MCP catalog exceeded bounded pagination")
    if not tools or any(t["name"].startswith("mcp__") or not isinstance(t.get("inputSchema"), dict) for t in tools):
        raise ValueError("Catalog must preserve original MCP leaf names and schemas")
    write(directory / "catalog.json", tools)
    write(directory / "catalog-provenance.json", {"endpoint": url, "method": "tools/list", "count": len(tools),
          "captured_at": datetime.now(timezone.utc).isoformat(), "catalog_sha256": digest(tools), "tool_calls": 0})
    return directory / "catalog.json"
