"""In-sandbox stand-in for the fixture store when the real backend is attached.

Runs as root inside the target sandbox. It holds no credentials and no state: every tool
call goes over the relay's ``mcp`` listener to the host bridge, which owns the trace and
the backend. Only the captured catalog is local, so ``tools/list`` is unchanged.
"""
import json
import os
import urllib.request

_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _post(path, value):
    request = urllib.request.Request("http://127.0.0.1:%s%s" % (os.environ["BENCHMARK_BRIDGE_PORT"], path),
                                     data=json.dumps(value).encode(), method="POST", headers={"content-type": "application/json"})
    with _opener.open(request, timeout=300) as response:
        return json.load(response)


class ForwardingStore:
    def __init__(self, task, files, catalog=None):
        self.catalog, self.turn = catalog, 0
        self.state, self.trace = {}, []  # Cancellation markers only; the host trace is authoritative.

    def call(self, name, arguments):
        value = _post("/call", {"name": name, "arguments": arguments, "turn": self.turn})
        if value["cancel"]:
            self.trace.append({"kind": "cancel", "turn": self.turn})
        return value["response"]

    def apply_events(self, turn, boundary="before_turn", operation=None):
        cancelled = _post("/events", {"turn": turn, "boundary": boundary})["cancel"]
        if cancelled:
            self.trace.append({"kind": "cancel", "turn": turn})
        return cancelled

    def followup(self, turn, final_type, messages):
        """v3: the host bridge picks the simulated user's next message from stored state; ``None`` ends the session."""
        return _post("/followup", {"turn": turn, "final_type": final_type, "messages": messages})["message"]
