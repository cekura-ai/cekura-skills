"""Matching-image multi-turn/skill-delivery check with zero provider inference."""
import copy
import io
import json

from ..common import ROOT, digest, read, write, private_dir
from .fixture import Store
from ..modal_runtime import ModalRuntime
from ..runtime import delivered_skill
from ..skill import material
from .dataset import load


def response_factory():
    class Response(io.BytesIO):
        status, reason = 200, "OK"
        def getheaders(self): return [("Content-Type", "text/event-stream")]
        def getheader(self, name, default=None): return dict(self.getheaders()).get(name, default)
    class Transport:
        def request(self, method, path, body, headers): self.body = json.loads(body)
        def getresponse(self):
            last = self.body["messages"][-1]
            content = last.get("content", [])
            tool_result = isinstance(content, list) and any(isinstance(c, dict) and c.get("type") == "tool_result" for c in content)
            events = [{"type": "message_start", "message": {"id": "offline-v2", "type": "message", "role": "assistant",
                      "model": "accounts/fireworks/routers/kimi-k3-fast", "content": [], "stop_reason": None, "usage": {"input_tokens": 0, "output_tokens": 0}}}]
            if not tool_result or any(c.get("tool_use_id") == "offline-load" for c in content if isinstance(c, dict)):
                load = not tool_result
                args = {"skill": "cekura:cekura-eval-design"} if load else {"path": "/home/agent/.claude/plugins/marketplaces/cekura-skills/cekura/skills/cekura-eval-design/SKILL.md"}
                events += [{"type": "content_block_start", "index": 0, "content_block": {"type": "tool_use", "id": "offline-load" if load else "offline-read", "name": "Skill" if load else "read", "input": {}}},
                           {"type": "content_block_delta", "index": 0, "delta": {"type": "input_json_delta", "partial_json": json.dumps(args)}}]
                stop = "tool_use"
            else:
                events += [{"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
                           {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "Offline skill and history transport verified; no resources changed."}}]
                stop = "end_turn"
            events += [{"type": "content_block_stop", "index": 0}, {"type": "message_delta", "delta": {"stop_reason": stop, "stop_sequence": None}, "usage": {"output_tokens": 0}}, {"type": "message_stop"}]
            return Response(b"".join(b"event: " + e["type"].encode() + b"\ndata: " + json.dumps(e).encode() + b"\n\n" for e in events))
        def close(self): pass
    return Transport()


def skill_evidence(bodies, exact):
    """Match content to actual load/read tool calls; system text is insufficient."""
    observed = []
    for body in bodies:
        calls = {}
        for message in json.loads(body).get("messages", []):
            content = message.get("content", [])
            for block in content if isinstance(content, list) else []:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_use":
                    calls[block["id"]] = block
                if block.get("type") == "tool_result":
                    call = calls.get(block.get("tool_use_id"), {})
                    args = call.get("input", {})
                    if "cekura-eval-design" not in json.dumps(args):
                        continue
                    value = block.get("content", "")
                    text = value if isinstance(value, str) else "\n".join(b.get("text", "") for b in value if isinstance(b, dict))
                    observed.append({"tool": call.get("name"), "sha256": digest(text.encode()), "characters": len(text),
                                     "full_loader_content": text == exact, "starts_with_skill": text.startswith(exact[:1024])})
    return observed


def probe(config, directory, ledger):
    directory = private_dir(directory)
    cfg = copy.deepcopy(config["target"])
    cfg["catalog"] = read(cfg["catalog_path"])
    cfg["rates"] = {"input_per_million": .000001, "cached_input_per_million": 0, "output_per_million": .000001}
    task = copy.deepcopy(load()[0])
    task["request"] = "Read the installed eval-design skill and report this offline transport check. Do not write resources."
    task["followups"] = [{"message": "Continue this offline check and verify the same installed skill."}, {"message": "Confirm the earlier check is present in conversation history."}]
    files = material()
    store = Store(task, files, cfg["catalog"])
    runtime = ModalRuntime(cfg, ledger, offline=True, offline_factory=response_factory)
    run = runtime.run(task, files, store, None, directory)
    requests = list((directory / "gateway").glob("request-*/request.body"))
    bodies = [p.read_text() for p in requests]
    # Installed bytes and the capped delivered text are distinct; inspect actual provider input.
    exact = delivered_skill(files["SKILL.md"], cfg["snapshot"]["skill_max_chars"]).decode()
    marker = "Offline skill and history transport verified"
    history = (directory / "saved_history.txt").read_text() if (directory / "saved_history.txt").exists() else ""
    teardown = read(directory / "teardown.json") if (directory / "teardown.json").exists() else {}
    observed = skill_evidence(bodies, exact)
    write(directory / "observed-skill-results.json", observed)
    delivered = any(r["tool"] == "Skill" and r["full_loader_content"] for r in observed) and any(r["tool"] == "read" and r["starts_with_skill"] for r in observed)
    passed = run["status"] == "complete" and len(run["messages"]) == 3 and history.count('<turn role="user">') == 3 and marker in history and delivered and teardown.get("terminated") is True
    result = {"passed": passed, "identity": {"model": cfg["snapshot"]["model"], "endpoint": cfg["snapshot"]["model_base_url"]},
              "image": cfg["image"], "runtime_env": cfg["snapshot"]["runtime_env"], "inference_requests": 0,
              "mock_requests": len(requests), "terminated": teardown.get("terminated", False), "runtime_status": run["status"],
              "turns": len(run["messages"]), "production_history_format_verified": history.count('<turn role="user">') == 3,
              "candidate_material_read": delivered, "installed_sha256": digest(files["SKILL.md"]), "expected_delivered_sha256": digest(exact.encode()),
              "full_skill_loader_verified": any(r["full_loader_content"] for r in observed), "actual_user_turns": run.get("user_turns", []),
              "probe_sha256": digest(__import__("pathlib").Path(__file__)), "fixture_sha256": digest(ROOT / "v2/fixture.py"),
              "code_sha256": digest(ROOT / "gateway.py"), "adapter_sha256": digest(ROOT / "modal_runtime.py"), "relay_sha256": digest(ROOT / "relay.py")}
    write(directory / "gateway-probe.json", result)
    return result
