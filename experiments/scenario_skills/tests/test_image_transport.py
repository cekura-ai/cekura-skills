"""Image preparation and fail-closed transport; no paid compute or inference."""
import io
import json
import socket
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from experiments.scenario_skills.common import digest
from experiments.scenario_skills.dataset import load
from experiments.scenario_skills.fixture import FixtureServer, PREFIX, Store
from experiments.scenario_skills.modal_probe import RATES, allocation, package
from experiments.scenario_skills.modal_probe import reserve_infrastructure
from experiments.scenario_skills.budget import BudgetError, Ledger
from experiments.scenario_skills.network_guard import firewall_rules, validate_proof
from experiments.scenario_skills.runtime import ModelProxy
from experiments.scenario_skills.runtime_image import prepare_image
from experiments.scenario_skills.skill import material


class TransportTests(unittest.TestCase):
    def test_wire_names_are_leaves_and_trace_preserves_both_names(self):
        task = load()[0]
        store = Store(task, material())
        self.assertTrue(all(not t["name"].startswith(PREFIX) for t in store.catalog))
        result = store.call("aiagents_retrieve", {"id": task["fixture"]["agent"]["id"]})
        self.assertFalse(result["isError"])
        self.assertEqual(store.trace[0]["wire_name"], "aiagents_retrieve")
        self.assertEqual(store.trace[0]["name"], PREFIX + "aiagents_retrieve")
        qualified = store.call(PREFIX + "aiagents_retrieve", {"id": task["fixture"]["agent"]["id"]})
        self.assertEqual(result, qualified)

    def test_guard_drops_before_flush_and_allows_only_two_host_ports(self):
        rules = firewall_rules("192.0.2.1", [3001, 3002])
        self.assertEqual(rules[:2], [["-P", "OUTPUT", "DROP"], ["-F", "OUTPUT"]])
        self.assertEqual(len(rules), 5)
        for invalid in ([0, 3001], [3001, 65536], [3001]):
            with self.assertRaises(ValueError):
                firewall_rules("192.0.2.1", invalid)

    def test_guard_rejects_extra_egress_rules_ipv6_and_port_drift(self):
        proof = {"type": "network_guard_ready", "gateway": "192.0.2.1", "ports": [3001, 3002],
                 "ipv4": "-P OUTPUT DROP\n-A OUTPUT -o lo -j ACCEPT\n-A OUTPUT -d 192.0.2.1/32 -p tcp -m tcp --dport 3001 -j ACCEPT\n-A OUTPUT -d 192.0.2.1/32 -p tcp -m tcp --dport 3002 -j ACCEPT\n",
                 "ipv6": "-P OUTPUT DROP\n"}
        self.assertEqual(validate_proof(proof, 3001, 3002), "192.0.2.1")
        for mutation in (dict(proof, ipv4=proof["ipv4"] + "-A OUTPUT -j ACCEPT\n"),
                         dict(proof, ipv6="-P OUTPUT ACCEPT\n"), dict(proof, ports=[3001, 9999])):
            with self.assertRaises(ValueError):
                validate_proof(mutation, 3001, 3002)

    def test_offline_proxy_never_opens_upstream_even_for_allowed_host(self):
        with ModelProxy("api.fireworks.ai", forward=False) as proxy:
            client = socket.create_connection(("127.0.0.1", proxy.port))
            with client, patch("experiments.scenario_skills.runtime.socket.create_connection", side_effect=AssertionError("Upstream opened")):
                client.sendall(b"CONNECT api.fireworks.ai:443 HTTP/1.1\r\n\r\n")
                self.assertIn(b"502", client.recv(100))
            self.assertEqual(proxy.attempts, ["api.fireworks.ai:443"])
            self.assertEqual(proxy.denied, [])

    def test_modal_allocation_requires_verified_sandbox_rates(self):
        evidence = {"source": "https://modal.com/pricing", "verified_at": "synthetic verification", "rates": RATES}
        budget = allocation(evidence)
        self.assertLess(budget["compute_and_transfer_bound_usd"], budget["reserved_usd"])
        self.assertTrue(budget["block_network"])
        self.assertEqual(budget["cpu"], (1, 1))
        self.assertEqual(budget["memory_mib"], (1024, 1024))
        for invalid in ({}, dict(evidence, rates={"cpu_core_second": 0}), dict(evidence, source="unverified")):
            with self.assertRaises(ValueError):
                allocation(invalid)

    def test_offline_infrastructure_consumes_shared_allowance_and_cannot_repeat(self):
        with tempfile.TemporaryDirectory(prefix="cekura-infrastructure-budget-") as temporary:
            root = Path(temporary)
            ledger, key = reserve_infrastructure(root / "budget.json", root / "probe")
            self.assertEqual(float(ledger.total("target")), .1)
            self.assertTrue(ledger.state["entries"][key]["infrastructure_only"])
            self.assertFalse(ledger.can_finish(20, 0))
            with self.assertRaises(BudgetError):
                reserve_infrastructure(root / "budget.json", root / "probe")
            ledger.reserve("rest", "target", 19.9)
            with self.assertRaises(BudgetError):
                reserve_infrastructure(root / "budget.json", root / "another-probe")


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="cekura-image-tests-")
        self.root = Path(self.temporary.name)
        self.source = self.root / "source"
        self.source.mkdir()
        self.recipe = '''raise RuntimeError("Source must never execute")
_NODE_VERSION = "22.23.2"
_PI_VERSION = "0.84.1"
_NODE_PREFIX = "/opt/node"
_PI_PREFIX = "/opt/pi"
_SANDBOX_SKILLS_DST = "/home/agent/.claude/plugins/marketplaces/cekura-skills"
def _build_sandbox_image():
    return modal.Image.debian_slim(python_version="3.11").pip_install("httpx==0.28.1")
'''
        (self.source / "modal_driver.py").write_text(self.recipe)
        (self.source / "agent_runner.py").write_text("Captured synthetic runner")
        (self.source / "pi_extension.ts").write_text("Captured synthetic extension")
        self.settings = self.root / "captured.json"
        self.captured = b'{"skills":["/home/agent/.claude/plugins/marketplaces/cekura-skills/cekura/skills","/home/agent/.claude/skills"]}\n'
        self.settings.write_bytes(self.captured)

    def tearDown(self):
        self.temporary.cleanup()

    def prepare(self, name="prepared"):
        output = self.root / name
        output.mkdir()
        manifest = prepare_image(self.source, output, "synthetic deployed recipe", self.settings)
        return output, manifest

    def test_recipe_is_parsed_without_execution_and_captured_settings_are_exact(self):
        output, manifest = self.prepare()
        self.assertEqual((output / "pi-settings.json").read_bytes(), self.captured)
        self.assertEqual(manifest["pi_settings_sha256"], digest(self.captured))
        self.assertEqual(manifest["python_packages"], ["httpx==0.28.1"])
        self.assertIn("unverified", manifest["provenance"])
        self.assertEqual(manifest["source_sha256"]["agent_runner.py"], digest(output / "runtime/agent_runner.py"))

    def test_floating_recipe_and_changed_loader_paths_are_rejected(self):
        for change in (self.recipe.replace("httpx==0.28.1", "httpx"), self.recipe.replace("/opt/node", "/opt/other")):
            (self.source / "modal_driver.py").write_text(change)
            output = self.root / str(len(list(self.root.iterdir())))
            output.mkdir()
            with self.assertRaises(ValueError):
                prepare_image(self.source, output, "synthetic recipe")

    def test_modal_upload_has_only_transport_skill_and_synthetic_material(self):
        output, _ = self.prepare()
        packed = package(output, {"image_id": "im-synthetic"})
        with tarfile.open(fileobj=io.BytesIO(packed), mode="r:gz") as archive:
            names = archive.getnames()
            self.assertNotIn("app/experiments/scenario_skills/grader.py", names)
            self.assertTrue(all(not n.startswith("/") and ".." not in Path(n).parts for n in names))
            self.assertTrue(all(".env" not in n and ".git/" not in n for n in names))
            task = json.load(archive.extractfile("app/probe-task.json"))
            self.assertEqual(task["id"], "library-1")
            self.assertEqual(task["split"], "training")
            self.assertEqual(archive.extractfile("home/agent/.pi/agent/settings.json").read(), self.captured)
        (output / "runtime/agent_runner.py").write_text("Source drift")
        with self.assertRaises(ValueError):
            package(output, {"image_id": "im-synthetic"})
