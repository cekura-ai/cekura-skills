"""Export original MCP tool metadata via Codex's existing authenticated client.

Only initialization and mcpServerStatus/list are sent. No model thread, turn,
tool invocation or credential export is needed. The proposer stays separate.
"""
import json
import os
import queue
import signal
import subprocess
import threading
from datetime import datetime, timezone

from .common import digest, private_dir, read, write

MAX_LINE = 16 * 1024 * 1024
METHODS = {"initialize", "initialized", "mcpServerStatus/list"}


def original_catalog(status, server_name="cekura"):
    result = status.get("result") if isinstance(status, dict) else None
    if not isinstance(result, dict) or status.get("error") or result.get("nextCursor"):
        raise ValueError("Codex MCP discovery failed or returned an incomplete server page")
    data = result.get("data")
    if not isinstance(data, list) or any(not isinstance(s, dict) for s in data):
        raise ValueError("Malformed Codex MCP server metadata")
    matches = [s for s in data if s.get("name") == server_name]
    if len(matches) != 1:
        raise ValueError("Expected exactly one configured Cekura server")
    server = matches[0]
    if server.get("httpOrigin") != "https://api.cekura.ai" or server.get("toolsError"):
        raise ValueError("Discovery must use the original Cekura endpoint with no tool-list error")
    tools = server.get("tools")
    if not isinstance(tools, dict) or not tools:
        raise ValueError("Codex did not return the original MCP tool objects")
    catalog = []
    for name, tool in sorted(tools.items()):
        if (not isinstance(tool, dict) or name != tool.get("name") or name.startswith("mcp__")
                or not isinstance(tool.get("inputSchema"), dict)):
            raise ValueError("Preserve original leaf names and JSON schemas; do not infer schemas from signatures")
        import jsonschema
        jsonschema.validators.validator_for(tool["inputSchema"]).check_schema(tool["inputSchema"])
        catalog.append(tool)
    return catalog, server


def discover(directory, server_name="cekura", binary="codex"):
    directory = private_dir(directory)
    version = subprocess.check_output([binary, "--version"], text=True, timeout=20).strip()
    messages = queue.Queue()
    with (directory / "codex-mcp.stderr").open("w") as stderr:
        process = subprocess.Popen([binary, "app-server", "--listen", "stdio://"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr,
            cwd=directory, text=True, start_new_session=True)

        def drain():
            try:
                while True:
                    line = process.stdout.readline(MAX_LINE + 1)
                    if not line:
                        raise RuntimeError("Codex app-server exited before discovery completed")
                    if len(line.encode()) > MAX_LINE:
                        raise ValueError("MCP metadata exceeded the bounded capture limit")
                    messages.put(json.loads(line))
            except Exception as error:
                messages.put(error)

        reader = threading.Thread(target=drain, daemon=True)
        reader.start()

        def send(value):
            if value["method"] not in METHODS:
                raise ValueError("Schema capture cannot start model turns or invoke tools")
            process.stdin.write(json.dumps(value) + "\n")
            process.stdin.flush()

        def receive(identifier):
            import time
            deadline = time.monotonic() + 90
            while True:
                try:
                    value = messages.get(timeout=max(.01, deadline - time.monotonic()))
                except queue.Empty:
                    raise TimeoutError("Read-only Codex MCP discovery timed out")
                if isinstance(value, Exception):
                    raise value
                if value.get("id") == identifier:
                    return value
                if time.monotonic() >= deadline:
                    raise TimeoutError("Read-only Codex MCP discovery timed out")

        try:
            send({"method": "initialize", "id": 0, "params": {"clientInfo": {"name": "cekura_schema_export", "version": "1"}}})
            if receive(0).get("error"):
                raise RuntimeError("Codex app-server initialization failed")
            send({"method": "initialized", "params": {}})
            send({"method": "mcpServerStatus/list", "id": 1,
                  "params": {"detail": "toolsAndAuthOnly", "serverName": server_name, "limit": 10}})
            status = receive(1)
        finally:
            process.stdin.close()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
            reader.join(timeout=2)
            process.stdout.close()
    write(directory / "codex-mcp-status.json", status)
    return status, version


def capture(directory, server_name="cekura", status_path=None):
    directory = private_dir(directory)
    if status_path is None:
        status, version = discover(directory, server_name)
    else:
        # Reuse a complete private status export without another connection.
        status, version = read(status_path), None
    catalog, server = original_catalog(status, server_name)
    write(directory / "catalog.json", catalog)
    write(directory / "catalog-provenance.json", {
        "endpoint": "https://api.cekura.ai/mcp", "method": "mcpServerStatus/list",
        "transport": "codex_app_server", "source_status_sha256": digest(status),
        "catalog_sha256": digest(catalog), "count": len(catalog),
        "server_info": server.get("serverInfo"), "auth_status": server.get("authStatus"),
        "cli_version": version, "captured_at": datetime.now(timezone.utc).isoformat(),
        "tool_calls": 0, "model_turns": 0,
        "documentation": "https://developers.openai.com/codex/app-server/"})
    return directory / "catalog.json"
