"""Pre-inference drills on the assembled real-backend stack with fake providers only.

Each drill runs the instrumented pinned backend, its Celery worker and the real generator
script inside a network-less local sandbox. Provider responses come from ``FakeProviders``;
nothing can reach a real provider, because the metering transport is the fake and the
networks have no external route. Results are written as evidence, with pass/fail per claim.
"""
from __future__ import annotations

import io
import json
import subprocess
import threading
import time
from decimal import Decimal
from pathlib import Path

from ..common import write
from .backend_stack import Infrastructure, Stack, docker
from .bridge import Bridge, operations
from .seed import seed

PINNED_ENGINE = "accounts/fireworks/routers/glm-5p3-fast"


class FakeResponse(io.RawIOBase):
    def __init__(self, status, content_type, chunks, delay):
        self.status, self.reason, self.content_type = status, "Fake", content_type
        self.chunks, self.delay, self.closed_by_caller = list(chunks), delay, False

    def getheaders(self):
        return [("Content-Type", self.content_type)]

    def getheader(self, name, default=None):
        return self.content_type if name.lower() == "content-type" else default

    def read1(self, n=-1):
        if self.closed_by_caller:
            raise ValueError("closed")
        if not self.chunks:
            return b""
        end = time.monotonic() + self.delay
        while time.monotonic() < end:
            if self.closed_by_caller:
                raise ValueError("closed")
            time.sleep(.05)
        return self.chunks.pop(0)


class FakeProviders:
    """Scripted provider behavior keyed by mode; records every forwarded request."""
    def __init__(self, mode="answer", stream_delay=0.0):
        self.mode, self.stream_delay, self.received, self.lock = mode, stream_delay, [], threading.Lock()

    def __call__(self, host):
        owner = self

        class Connection:
            def request(self, method, target, body, headers):
                self.payload = json.loads(body)
                self.target = target
                with owner.lock:
                    owner.received.append({"host": host, "target": target, "model": self.payload.get("model") or target.split("models/")[-1].split(":")[0],
                                           "stream": bool(self.payload.get("stream"))})

            def getresponse(self):
                self.response = owner.respond(host, self.target, self.payload)
                return self.response

            def close(self):
                if hasattr(self, "response"):
                    self.response.closed_by_caller = True
        return Connection()

    def respond(self, host, target, payload):
        if self.mode == "fail":
            return FakeResponse(500, "application/json", [b'{"error":"fake provider outage"}'], 0)
        if "generativelanguage" in host:
            body = {"candidates": [{"content": {"parts": [{"text": "ok"}]}, "finishReason": "STOP"}],
                    "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 1}}
            return FakeResponse(200, "application/json", [json.dumps(body).encode()], 0)
        if target.endswith("/chat/completions"):
            body = {"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": []}}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 1}}
            return FakeResponse(200, "application/json", [json.dumps(body).encode()], 0)
        if not payload.get("stream"):
            body = {"id": "fake", "type": "message", "role": "assistant", "content": [{"type": "text", "text": "pong"}],
                    "usage": {"input_tokens": 5, "output_tokens": 1}}
            return FakeResponse(200, "application/json", [json.dumps(body).encode()], 0)
        events = [{"type": "message_start", "message": {"id": "fake", "type": "message", "role": "assistant", "model": payload.get("model"),
                                                         "content": [], "usage": {"input_tokens": 10, "output_tokens": 0}}},
                  {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}}]
        events += [{"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "thinking "}} for _ in range(40)]
        events += [{"type": "content_block_stop", "index": 0},
                   {"type": "message_delta", "delta": {"stop_reason": "end_turn"}, "usage": {"output_tokens": 40}}, {"type": "message_stop"}]
        chunks = [("event: %s\ndata: %s\n\n" % (e["type"], json.dumps(e))).encode() for e in events]
        return FakeResponse(200, "text/event-stream", chunks, self.stream_delay)


def drill_generator(rates):
    """Drill configuration: the pinned routes with synthetic rates; real runs need verified ones."""
    model = {"rates": rates, "admission": {"input_token_limit": 262000, "output_token_limit": 65536, "token_bound_evidence": "drill"}}
    return {"endpoints": [
        {"host": "api.fireworks.ai", "credential_env": "CEKURA_DRILL_FIREWORKS",
         "routes": [{"path": "/inference/v1/messages", "api": "anthropic", "query": {"beta": ["true"]}},
                    {"path": "/inference/v1/chat/completions", "api": "chat"}],
         "models": {PINNED_ENGINE: model, "accounts/fireworks/models/deepseek-v4p1-flash": model}},
        {"host": "generativelanguage.googleapis.com", "credential_env": "CEKURA_DRILL_GEMINI",
         "routes": [{"pattern": r"^/v1beta/models/(?P<model>[A-Za-z0-9._-]+):(?:generateContent|streamGenerateContent)$", "api": "gemini", "query": {"alt": ["sse"]}}],
         "models": {"gemini-3.7-flash": model}}],
        "passthrough": ["api.modal.com"],
        "sandbox": {"rates": {"source": "drill", "cpu_core_second": .0000394, "memory_gib_second": .0000067},
                    "max_lifetime_seconds": 600, "teardown_grace_seconds": 60},
        "backend_env": {"AGENT_SCENARIO_ENGINE_MODEL": PINNED_ENGINE, "AGENT_SCENARIO_PI_PROVIDER": "google",
                        "AGENT_SCENARIO_PI_MODEL": "gemini-3.7-flash", "AGENT_SCENARIO_PI_THINKING": "low", "AGENT_DIRECT_ANTHROPIC": "0"},
        "settings": {"DEEPSEEK_PROVIDER_ORDER": ["fireworks"], "VAPI_TOOL_END_CALL": ["drill"], "VAPI_TOOL_DTMF": ["drill"],
                     "VAPI_TOOL_END_CALL_ONLY_ON_TRANSFER": ["drill"]},
        "sandbox_image": "cekura-generator-sandbox-local:drill", "modal_secret": "cekura-experiment-generator",
        "modal_app": "claude-cekura-experiment", "queues": "simulation-eval"}


def worker_python(stack, code, timeout=120):
    result = subprocess.run(["docker", "exec", "-i", stack.containers["worker"], "python", "manage.py", "shell"], input=code,
                            capture_output=True, text=True, timeout=timeout)
    return result.stdout + result.stderr


SANDBOX_PROBE = r'''
from app.claude_utils import get_or_create_phased_sandbox
from app import cekura_metering as m
import json, os
sb = get_or_create_phased_sandbox(key="drill-%s", timeout=43200)
env = dict(m.exec_kwargs(sb)["env"], PLACEHOLDER=os.environ["FIREWORKS_API_KEY"])
CODE
'''


def bypass(stack):
    probe = r'''
import os, socket, json, urllib.request
out = {}
try:
    socket.create_connection(("1.1.1.1", 443), timeout=5); out["direct_ip"] = "reachable"
except OSError as e: out["direct_ip"] = "blocked: " + type(e).__name__
try:
    socket.gethostbyname("api.example.com"); out["unaliased_dns"] = "resolved"
except OSError: out["unaliased_dns"] = "unresolvable"
for host in ("api.anthropic.com", "pass.wafer.ai", "bedrock-runtime.us-east-1.amazonaws.com"):
    try:
        urllib.request.urlopen("https://%s/v1/messages" % host, timeout=10); out[host] = "reachable"
    except Exception as e: out[host] = "denied: " + type(e).__name__
out["provider_keys_in_env"] = sorted(k for k, v in os.environ.items() if v and v in (os.environ.get("CEKURA_REAL_KEY_CANARY", "-"),))
import modal
try:
    modal.Sandbox.create("sleep", "1"); out["unmetered_sandbox"] = "created"
except RuntimeError as e: out["unmetered_sandbox"] = "refused"
print("DRILL" + json.dumps(out))
'''
    worker = json.loads(worker_python(stack, probe).split("DRILL", 1)[1].splitlines()[0])
    sandbox_code = '''
code = """
import json, os, socket, urllib.request
out = {}
try:
    socket.create_connection(("1.1.1.1", 443), timeout=5); out["direct_ip"] = "reachable"
except OSError as e: out["direct_ip"] = "blocked"
for host in ("api.anthropic.com", "bedrock-runtime.us-east-1.amazonaws.com", "statsig.anthropic.com"):
    try:
        urllib.request.urlopen("https://%s/" % host, timeout=10); out[host] = "reachable"
    except Exception as e: out[host] = "denied"
r = urllib.request.Request("https://api.fireworks.ai/inference/v1/messages", data=json.dumps({"model": "''' + PINNED_ENGINE + '''", "max_tokens": 1, "messages": []}).encode(),
                           headers={"x-api-key": os.environ["PLACEHOLDER"], "content-type": "application/json"})
out["metered_control"] = urllib.request.urlopen(r, timeout=30).status
print(json.dumps(out))
"""
p = sb.exec("python3", "-c", code, env=env)
out, err = p.stdout.read(), p.stderr.read()
print("DRILL" + (out.strip() or json.dumps({"sandbox_error": err[-1500:]})))
'''
    sandbox = json.loads(worker_python(stack, SANDBOX_PROBE.replace("%s", "bypass").replace("CODE", sandbox_code)).split("DRILL", 1)[1].splitlines()[0])
    passed = (worker["direct_ip"].startswith("blocked") and worker["unaliased_dns"] == "unresolvable"
              and all(worker[h].startswith("denied") for h in ("api.anthropic.com", "pass.wafer.ai", "bedrock-runtime.us-east-1.amazonaws.com"))
              and worker["unmetered_sandbox"] == "refused" and sandbox["direct_ip"] == "blocked"
              and all(sandbox[h] == "denied" for h in ("api.anthropic.com", "bedrock-runtime.us-east-1.amazonaws.com", "statsig.anthropic.com"))
              and sandbox["metered_control"] == 200)
    return {"passed": passed, "worker": worker, "sandbox": sandbox}


def generate(stack, task, catalog, files, spec):
    session = seed(stack, task, stack.generator["settings"])
    bridge = Bridge(task, stack.base_url, session, catalog, files, operations(spec))
    response, _ = bridge.call("scenarios_generate_bg", {"agent_id": task["fixture"]["agent"]["id"], "num_scenarios": 1,
                                                       "extra_instructions": "1. One ordinary policy check.", "simulation_type": "instruction"}, 0)
    if response["isError"]:
        raise RuntimeError("generate-bg refused: " + response["content"][0]["text"][:500])
    return bridge, json.loads(response["content"][0]["text"])["progress_id"]


def poll(bridge, progress, seconds):
    deadline, state = time.time() + seconds, {}
    while time.time() < deadline:
        response, _ = bridge.call("scenarios_generate_progress", {"progress_id": progress}, 0)
        state = json.loads(response["content"][0]["text"]) if not response["isError"] else {"error": response["content"][0]["text"]}
        if state.get("status") in ("failed", "completed") or state.get("error") or (state.get("total_scenarios") and
                (state.get("completed_scenarios") or 0) + (state.get("failed_scenarios") or 0) >= state["total_scenarios"]):
            break
        time.sleep(5)
    return state


def fallback(stack, providers, task, catalog, files, spec):
    """Every pinned model fails; the generator's own fallbacks must stay metered or be denied."""
    bridge, progress = generate(stack, task, catalog, files, spec)
    state = poll(bridge, progress, 420)
    pinned = {m for e in stack.generator["endpoints"] for m in e["models"]}
    forwarded = sorted({(r["host"], r["model"]) for r in providers.received})
    denied = [d["reason"] for d in stack.metering.denied]
    produced = len(state.get("scenarios_list") or [])
    passed = bool(providers.received) and all(m in pinned for _, m in forwarded) and produced == 0
    return {"passed": passed, "progress": state, "forwarded_models": forwarded, "denied": denied,
            "requests": [{k: r[k] for k in ("host", "model", "status", "reserved_usd")} for r in stack.metering.requests]}


def concurrency(stack):
    """Twelve parallel sandbox requests through the real relay under a cap that fits four."""
    body = len(json.dumps({"model": PINNED_ENGINE, "max_tokens": 2000, "messages": [], "stream": True}).encode())
    model = stack.generator["endpoints"][0]["models"][PINNED_ENGINE]["rates"]
    bound = (Decimal(body + 4096) * Decimal(str(model["input_per_million"])) + 2000 * Decimal(str(model["output_per_million"]))) / Decimal(1_000_000)
    cap = str(bound * Decimal("4.5"))
    code = '''
code = """
import json, os, urllib.request
from concurrent.futures import ThreadPoolExecutor
def one(_):
    r = urllib.request.Request("https://api.fireworks.ai/inference/v1/messages", data=json.dumps({"model": "''' + PINNED_ENGINE + '''", "max_tokens": 2000, "messages": [], "stream": True}).encode(),
                               headers={"x-api-key": os.environ["PLACEHOLDER"], "content-type": "application/json"})
    try:
        response = urllib.request.urlopen(r, timeout=300)
        response.read()
        return response.status
    except urllib.error.HTTPError as e:
        return e.code
with ThreadPoolExecutor(12) as pool:
    print(json.dumps(sorted(pool.map(one, range(12)))))
"""
p = sb.exec("python3", "-c", code, env=env)
out, err = p.stdout.read(), p.stderr.read()
print("DRILL" + (out.strip() or json.dumps({"sandbox_error": err[-1500:]})))
'''
    ledger = stack.ledger
    with ledger.staged("drill-concurrency-" + stack.scope, cap):
        statuses = json.loads(worker_python(stack, SANDBOX_PROBE.replace("%s", "concurrency").replace("CODE", code), 300).split("DRILL", 1)[1].splitlines()[0])
    if isinstance(statuses, dict):
        raise RuntimeError("Sandbox concurrency probe failed: " + statuses.get("sandbox_error", "")[-1200:])
    with ledger.transaction():
        staged = [e for e in ledger.state["entries"].values() if e.get("stage") == "drill-concurrency-" + stack.scope]
    charged = sum((Decimal(e["charged"]) for e in staged), Decimal(0))
    admitted = sum(e.get("entry_type") == "generator_request" for e in staged)
    return {"passed": 0 < admitted < 12 and statuses.count(402) == 12 - admitted and charged <= Decimal(cap),
            "statuses": statuses, "admitted": admitted, "stage_charged_usd": str(charged), "cap_usd": cap}


def termination(stack, providers, task, catalog, files, spec):
    """Cancel while the real generator is streaming; all nested work must stop."""
    bridge, progress = generate(stack, task, catalog, files, spec)
    deadline = time.time() + 300
    while time.time() < deadline and not any(r["status"] == "incomplete" and r.get("api") == "anthropic" for r in stack.metering.requests):
        time.sleep(1)
    in_flight = [dict(r) for r in stack.metering.requests if r["status"] == "incomplete"]
    sandboxes = stack.sandboxes()
    started = time.monotonic()
    evidence = stack.stop("drill cancellation")
    elapsed = time.monotonic() - started
    settled = all(stack.metering.requests[i]["status"] == "complete" for i, r in enumerate(stack.metering.requests))
    leftovers = docker("ps", "-aq", "--filter", "label=" + stack.label, check=False).split()
    return {"passed": bool(in_flight) and bool(sandboxes) and evidence["terminated"] and settled and not leftovers and elapsed < 60,
            "in_flight_at_cancel": in_flight, "sandboxes_before": sandboxes, "teardown": evidence, "seconds": round(elapsed, 1),
            "requests_after": [{k: r.get(k) for k in ("model", "status", "charged_usd", "charged_at_bound")} for r in stack.metering.requests]}


def run(directory, ledger, catalog, files, spec, task, names=("bypass", "fallback", "concurrency", "termination")):
    """Run all four drills; returns the evidence document. Fake providers only."""
    import os
    os.environ.setdefault("CEKURA_DRILL_FIREWORKS", "drill-key-never-sent-anywhere")
    os.environ.setdefault("CEKURA_DRILL_GEMINI", "drill-key-never-sent-anywhere")
    directory = Path(directory)
    rates = {"input_per_million": 1.0, "cached_input_per_million": .1, "output_per_million": 4.0, "source": "drill", "verified_at": "drill"}
    generator = drill_generator(rates)
    infra = Infrastructure(directory).ensure()
    results = {}
    previous = __import__("json").loads((directory / "drills.json").read_text()) if (directory / "drills.json").exists() else {}
    results.update({k: v for k, v in previous.items() if k not in names and k != "passed"})
    for name in names:
        providers = FakeProviders("fail" if name == "fallback" else "answer", stream_delay=2.0 if name in ("termination", "concurrency") else 0)
        stack = Stack(infra, "drill-" + name, directory / ("drill-" + name), generator, ledger, transport=providers, sandbox_backend="local-docker")
        try:
            stack.start()
            if name == "bypass":
                results[name] = bypass(stack)
            elif name == "fallback":
                results[name] = fallback(stack, providers, task, catalog, files, spec)
            elif name == "concurrency":
                results[name] = concurrency(stack)
            else:
                results[name] = termination(stack, providers, task, catalog, files, spec)
        except Exception as error:
            results[name] = {"passed": False, "error": type(error).__name__ + ": " + str(error)[:2000]}
        finally:
            if not stack.teardown:
                stack.stop("drill finished")
            results[name]["teardown_terminated"] = stack.teardown.get("terminated")
            results[name]["metering"] = {"denied": stack.metering.denied if getattr(stack, "metering", None) else None,
                                         "errors": stack.metering.errors if getattr(stack, "metering", None) else None}
            write(directory / "drills.json", results)
    results["passed"] = all(r.get("passed") and r.get("teardown_terminated") for r in results.values() if isinstance(r, dict))
    write(directory / "drills.json", results)
    return results
