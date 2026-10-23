"""Transport-only probes use fixed local responses; no paid model inference."""
import copy
from pathlib import Path

from .budget import Ledger
from .common import ROOT, digest, private_dir, read, write
from .dataset import load
from .fixture import Store, offline_catalog
from .modal_runtime import ModalRuntime
from .skill import material


def modal_probe(config, directory, ledger_path):
    cfg = copy.deepcopy(config["target"])
    cfg["catalog"] = offline_catalog()
    # Synthetic prices exist solely to exercise reservation/reconciliation.
    # The mock transport never opens a socket upstream and emits zero usage.
    cfg["rates"] = {"input_per_million": .000001, "cached_input_per_million": 0, "output_per_million": .000001}
    cfg["admission"] = {"input_token_limit": 256000, "output_token_limit": 32000}
    task = copy.deepcopy(load()[0])
    task.update(request="Report that this is an offline transport check.", followups=[])
    files = material()
    ledger = Ledger(Path(ledger_path), config.get("budget_policy"))
    runtime = ModalRuntime(cfg, ledger, offline=True)
    store = Store(task, files)
    directory = private_dir(directory)
    hashes = {"code_sha256": digest(ROOT / "gateway.py"), "adapter_sha256": digest(ROOT / "modal_runtime.py"),
              "relay_sha256": digest(ROOT / "relay.py")}
    result = runtime.run(task, files, store, None, directory)
    teardown = read(directory / "teardown.json") if (directory / "teardown.json").exists() else {}
    requests = result.get("gateway", {}).get("requests", [])
    result = {"passed": bool(requests) and all(r["status"] == "complete" for r in requests)
              and not result.get("gateway", {}).get("errors") and teardown.get("terminated") is True,
              "identity": {"model": cfg["snapshot"]["model"], "endpoint": cfg["snapshot"]["model_base_url"]},
              "image": cfg["image"], "runtime_env": cfg["snapshot"]["runtime_env"],
              **hashes, "inference_requests": 0, "mock_requests": len(requests),
              "terminated": teardown.get("terminated", False), "runtime_status": result["status"],
              "error": result.get("error"), "gateway": result.get("gateway")}
    write(directory / "gateway-probe.json", result)
    return result


def codex_probe(config, directory):
    import io
    import json
    from .proposer import CodexProposer
    from .skill import SKILL, split
    cfg = copy.deepcopy(config["proposer"])
    cfg["accounting"] = "per_request"
    cfg["rates"] = {"input_per_million": .000001, "cached_input_per_million": 0, "output_per_million": .000001}
    cfg["admission"] = {"input_token_limit": 1000000, "output_token_limit": 128000}
    directory = private_dir(directory)
    proposal = {"body": split(SKILL.read_bytes())[1].decode(), "rationale": "Offline CLI transport check; no proposed improvement"}
    text = json.dumps(proposal)
    message = {"type": "message", "id": "msg_probe", "role": "assistant", "status": "completed",
               "content": [{"type": "output_text", "text": text, "annotations": []}]}
    response = {"id": "resp_probe", "object": "response", "created_at": 0, "status": "completed", "model": cfg["model"],
                "output": [message], "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}}

    class Response(io.BytesIO):
        status, reason = 200, "OK"
        def getheaders(self):
            return [("Content-Type", "text/event-stream")]
        def getheader(self, name, default=None):
            return dict(self.getheaders()).get(name, default)

    class Transport:
        def request(self, method, path, body, headers):
            pass
        def getresponse(self):
            events = [{"type": "response.created", "response": dict(response, status="in_progress", output=[])},
                      {"type": "response.output_item.added", "output_index": 0, "item": dict(message, status="in_progress", content=[])},
                      {"type": "response.output_text.delta", "item_id": "msg_probe", "output_index": 0, "content_index": 0, "delta": text},
                      {"type": "response.output_item.done", "output_index": 0, "item": message},
                      {"type": "response.completed", "response": response}]
            return Response(b"".join(b"event: " + e["type"].encode() + b"\ndata: " + json.dumps(e).encode() + b"\n\n" for e in events))
        def close(self):
            pass
    result = {"passed": False, "inference_requests": 0,
              "identity": {"model": cfg["model"], "endpoint": cfg["model_base_url"]},
              "code_sha256": digest(ROOT / "gateway.py"), "proposer_sha256": digest(ROOT / "proposer.py")}
    try:
        data, _ = CodexProposer(cfg, directory, Ledger(directory / "budget.json"), offline_transport=Transport).propose(SKILL.read_bytes(), [], 1, [])
        billing = read(directory / "proposal-1.billing.json")
        result.update(passed=data == SKILL.read_bytes() and bool(billing["requests"]) and not billing["errors"], mock_requests=len(billing["requests"]))
    except Exception as error:
        result["error"] = type(error).__name__ + ": " + str(error)
    write(directory / "gateway-probe.json", result)
    return result
