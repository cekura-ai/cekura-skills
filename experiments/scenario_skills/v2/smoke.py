"""One v3 rollout end to end with no model inference, before money is committed to a paid stage.

Runs the real evaluator path: isolated backend stack, seeding and readback, the Modal target
sandbox, the admission gateway, the bridge, the contract grader and the result record. The
target's model transport is the fixed offline response and the generator sandbox is the local
stand-in whose provider transport refuses every connection, so no provider is ever reached. The
only charge is the bounded Modal sandbox reservation. The harness breakages that previously cost
paid rollouts (missing modules in the sandbox, DNS, relay, settlement) all fail here first.
"""
from __future__ import annotations

import time
from decimal import Decimal

from ..common import read, write
from ..skill import SKILL
from .backend_stack import Stack
from .evaluator import Evaluator, code_identity
from .experiment import benchmark

# A finished harness run: the offline reply ends the session, so the skill may never load.
HARNESS_COMPLETE = ("complete", "inconclusive")


class NoProviders:
    """Generator transport for the smoke: any provider connection is a failure, never a request."""
    def __call__(self, host):
        raise OSError("Smoke rollout: provider connection refused for " + host)


def smoke(config, directory, ledger, task_id="T01-harborview", concurrent=2):
    """``concurrent`` rollouts at once, as the parallel controller runs them; each must pass on its own."""
    from concurrent.futures import ThreadPoolExecutor
    from ..modal_runtime import ModalRuntime
    target = dict(config["target"], catalog=config["target"].get("catalog") or read(config["target"]["catalog_path"]))
    runtime = ModalRuntime(target, ledger, offline=True)
    factory = lambda infra, scope, path, generator, wallet: Stack(infra, scope, path, generator, wallet, transport=NoProviders(),
                                                                  sandbox_backend="local-docker")
    started = time.time()
    directory = directory / "smoke" / ("%d" % started)
    evaluator = Evaluator(config, directory, ledger, judge=None, runtime=runtime, stack_factory=factory)
    task = next(t for t in benchmark(config)[0]() if t["id"] == task_id)
    before = ledger.total()
    # A fresh key per rollout (a trailing comment): a smoke must run, never return a cached result.
    variants = [SKILL.read_bytes() + ("\n<!-- smoke %f %d -->\n" % (started, i)).encode() for i in range(concurrent)]
    with ThreadPoolExecutor(concurrent) as pool:
        outcomes = list(pool.map(lambda data: evaluator.execute(data, task), variants))
    rows = []
    for result in outcomes:
        rollout = directory / "rollouts" / result["scope"]
        checks = {"harness_complete": result["status"] in HARNESS_COMPLETE, "teardown_terminated": bool(result.get("backend_teardown", {}).get("terminated")),
                  "target_request_admitted": any(rollout.glob("gateway/request-*/request.json")), "graded": "grade" in result,
                  "no_generator_connection": not result.get("generator_requests"),
                  "no_inference_charge": Decimal(str(result.get("cost_usd") or 0)) == 0}
        rows.append({"scope": result["scope"], "status": result["status"], "error": result.get("error"), "checks": checks})
    report = {"passed": all(all(r["checks"].values()) for r in rows), "rollouts": rows, "task": task_id, "concurrent": concurrent,
              "seconds": round(time.time() - started, 1), "wallet_delta_usd": str(ledger.total() - before),
              "directory": str(directory), "code": code_identity()}
    write(directory / "smoke.json", report)
    return report


def smoke_passed(directory):
    """A passed smoke on the current rollout code; any change to that code needs a new one."""
    code = code_identity()
    return any(read(p).get("passed") is True and read(p).get("code") == code for p in (directory / "smoke").glob("*/smoke.json"))
