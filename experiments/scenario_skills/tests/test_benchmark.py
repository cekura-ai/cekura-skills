"""Local verification uses scripted actors, never Codex or paid target inference."""
from __future__ import annotations

import copy
import json
import subprocess
import tempfile
import sys
import unittest
from pathlib import Path
from urllib.request import Request, urlopen

from experiments.scenario_skills.budget import BudgetError, Ledger
from experiments.scenario_skills.common import ROOT, digest, read, write
from experiments.scenario_skills.dataset import load, visible
from experiments.scenario_skills.evaluator import Evaluator
from experiments.scenario_skills.fixture import FixtureServer, PREFIX, Store
from experiments.scenario_skills.grader import grade
from experiments.scenario_skills.meta_harness import History, search
from experiments.scenario_skills.preflight import preflight
from experiments.scenario_skills.proposer import CodexProposer, sandbox_profile, training_payload, usage_cost
from experiments.scenario_skills.runtime import ModelProxy, delivered_skill, pin_runtime_files
from experiments.scenario_skills.selection import human_gate, qualifies, review_packet, select
from experiments.scenario_skills.skill import SKILL, candidate, material, split


from experiments.scenario_skills.contract_probe import response, payload, generate, observable_trajectory as perfect_actor


class DatasetAndStateTests(unittest.TestCase):
    def setUp(self):
        self.tasks = load()
        self.files = material()

    def task(self, identifier):
        return next(t for t in self.tasks if t["id"] == identifier)

    def test_all_24_frozen_contracts_have_a_successful_tool_trajectory(self):
        for task in self.tasks:
            with self.subTest(task=task["id"]):
                store = Store(task, self.files)
                messages = perfect_actor(task, store)
                result = grade(task, store.trace, store.initial, store.state, messages)
                self.assertEqual(result["failed_checks"], [])
                self.assertEqual(result["semantic_status"], "pending_human_review")

    def test_visible_inputs_do_not_include_labels_or_scripted_followups(self):
        for task in self.tasks:
            self.assertEqual(set(visible(task)), {"id", "request", "documents", "context"})
            self.assertNotIn("expected", visible(task))

    def test_captured_tool_schema_rejects_invalid_arguments(self):
        task = self.task("museum-1")
        catalog = [{"name":PREFIX+"scenarios_create", "inputSchema":{"type":"object","required":["agent"],
                    "properties":{"agent":{"type":"integer"}}}}]
        store = Store(task,self.files,catalog)
        result = store.call(PREFIX+"scenarios_create",{"agent":"wrong"})
        self.assertTrue(result["isError"])
        self.assertIn("integer",result["content"][0]["text"])

    def test_wrong_behavioral_direct_routing_fails(self):
        task = self.task("library-1")
        store = Store(task, self.files)
        rows = [response(store, "scenarios_create", **payload(task)) for _ in range(2)]
        result = grade(task, store.trace, store.initial, store.state, ["Saved 2 scenarios: " + str([r["id"] for r in rows])])
        self.assertIn("routing", result["failed_checks"])
        self.assertIn("completed_poll", result["failed_checks"])

    def test_generating_verbatim_fails_and_truncation_is_detected(self):
        task = self.task("museum-1")
        store = Store(task, self.files)
        row = payload(task)
        row["instructions"] = row["instructions"][:20]
        created = response(store, "scenarios_create", **row)
        result = grade(task, store.trace, store.initial, store.state, [str(created["id"])])
        self.assertIn("field:instructions", result["failed_checks"])

    def test_missing_case_sensitive_variables_are_validation_errors_and_fail_grading(self):
        task = self.task("repair-1")
        store = Store(task, self.files)
        profile = response(store, "test_profiles_create", agent=task["fixture"]["agent"]["id"], name="Invalid", information={"servicecode": "OV-48"})
        args = payload(task)
        args.pop("instructions")
        args.update(scenario_type="conditional_actions", conditional_actions=task["suggested_actions"], test_profile=profile["id"])
        result = store.call(PREFIX + "scenarios_create", args)
        self.assertTrue(result["isError"])
        self.assertIn("case-sensitive", result["content"][0]["text"])
        result = grade(task, store.trace, store.initial, store.state, ["Saved 1 scenario."])
        self.assertIn("requested_count", result["failed_checks"])

    def test_missing_variables_in_final_state_fail_even_if_server_validation_was_bypassed(self):
        task = self.task("repair-1")
        store = Store(task, self.files)
        perfect_actor(task, store)
        store.state["profiles"][0]["information"].clear()
        self.assertIn("variables", grade(task, store.trace, store.initial, store.state, [str(store.state["scenarios"][-1]["id"])])["failed_checks"])

    def test_stale_id_cannot_be_reported_as_updated(self):
        task = self.task("recycling-2")
        store = Store(task, self.files)
        result = store.call(PREFIX + "scenarios_partial_update", {"id":task["context"]["stale_scenario_id"], "expected_outcome_prompt":"updated"})
        self.assertTrue(result["isError"])
        result = grade(task, store.trace, store.initial, store.state, ["Updated 1 evaluator."])
        self.assertIn("resource_ids", result["failed_checks"])
        self.assertIn("completion_count", result["failed_checks"])

    def test_updates_preserve_functions_and_other_scenarios(self):
        task = self.task("recycling-1")
        store = Store(task, self.files)
        row = response(store, "scenarios_partial_update", id=task["expected"]["ids"][0], expected_outcome_prompt=task["expected"]["fields"]["expected_outcome_prompt"])
        self.assertEqual(row["conditional_actions"]["functions"], store.initial["scenarios"][0]["conditional_actions"]["functions"])
        response(store, "scenarios_partial_update", id=row["id"], conditional_actions={"role":"Caller", "first_message":"", "conditions":[{"when":"greeting", "say":"hello"}]})
        result = grade(task, store.trace, store.initial, store.state, [str(row["id"])])
        self.assertIn("preserve:%d:conditional_actions" % row["id"], result["failed_checks"])
        row["folder_path"] = "Moved without request"
        store.state["scenarios"][0]["folder_path"] = row["folder_path"]
        result = grade(task, store.trace, store.initial, store.state, [str(row["id"])])
        self.assertIn("preserve:%d:folder" % row["id"], result["failed_checks"])

    def test_sectioned_profiles_reach_main_agent_and_replace_full_information(self):
        task = self.task("repair-1")
        store = Store(task, self.files)
        variables = task["fixture"]["agent"]["required_variables"]
        profile = response(store, "test_profiles_create", project=store.agent["project"], name="Sectioned caller",
                           information={"main_agent_variables": variables, "testing_agent_variables": {"name": "Caller"}})
        args = payload(task)
        args.pop("instructions")
        args.update(scenario_type="conditional_actions", conditional_actions=task["suggested_actions"], test_profile=profile["id"])
        row = response(store, "scenarios_create", **args)
        self.assertNotIn("variables", grade(task, store.trace, store.initial, store.state, [str(row["id"])])["failed_checks"])
        response(store, "test_profiles_partial_update", id=profile["id"], information={"testing_agent_variables": variables})
        self.assertEqual(response(store, "test_profiles_retrieve", id=profile["id"])["information"], {"testing_agent_variables": variables})
        self.assertTrue(store.call(PREFIX + "scenarios_create", args)["isError"])
        self.assertIn("variables", grade(task, store.trace, store.initial, store.state, [str(row["id"])])["failed_checks"])

    def test_bulk_operations_use_ids_and_validate_before_mutating(self):
        task = self.task("museum-1")
        store = Store(task, self.files)
        rows = [response(store, "scenarios_create", **payload(task)) for _ in range(2)]
        ids = [r["id"] for r in rows]
        before = copy.deepcopy(store.state)
        result = store.call(PREFIX + "scenarios_bulk_update", {"scenarios": ids + [999999], "agent": store.agent["id"], "append_instruction": "Suffix"})
        self.assertTrue(result["isError"])
        self.assertEqual(store.state, before)
        for _ in range(2):
            response(store, "scenarios_bulk_update", scenarios=ids, agent=store.agent["id"], append_instruction="Suffix",
                     metric_ids_to_add=[42], metric_ids_to_remove=[43])
        for identifier in ids:
            row = response(store, "scenarios_retrieve", id=identifier)
            self.assertTrue(row["instructions"].endswith("SuffixSuffix"))
            self.assertEqual(row["metrics"], [42])
        result = store.call(PREFIX + "scenarios_bulk_delete", {"scenarios": ids + [999999], "agent_id": store.agent["id"]})
        self.assertTrue(result["isError"])
        self.assertTrue(all(any(r["id"] == identifier for r in store.state["scenarios"]) for identifier in ids))
        response(store, "scenarios_bulk_delete", scenarios=ids, agent_id=store.agent["id"])
        self.assertEqual(store.state["scenarios"], store.initial["scenarios"])

    def test_folder_paths_and_duplicate_api_shape(self):
        task = self.task("museum-1")
        store = Store(task, self.files)
        parent = store.state["folders"][0]["path"]
        folder = response(store, "scenarios_folder_create", project_id=store.agent["project"], parent_path=parent, name="Copies")
        self.assertEqual(folder["path"], parent + ".Copies")
        copied = response(store, "scenarios_duplicate_create", project=store.agent["project"], copy_to_project=store.agent["project"],
                          scenarios=[store.initial["scenarios"][0]["id"]], folder_path=folder["path"])[0]
        self.assertEqual(copied["name"], "Copy of " + store.initial["scenarios"][0]["name"])
        self.assertEqual(copied["folder_path"], folder["path"])
        self.assertEqual(copied["conditional_actions"], store.initial["scenarios"][0]["conditional_actions"])
        args = payload(task); args["folder_path"] = "Missing folder"
        self.assertTrue(store.call(PREFIX + "scenarios_create", args)["isError"])

    def test_extra_arguments_cannot_invent_fields_missing_from_original_schema(self):
        task = self.task("museum-1")
        args = payload(task)
        catalog = [{"name": "scenarios_create", "inputSchema": {"type": "object",
                    "required": ["name", "personality"], "properties": {k: {} for k in args}}}]
        store = Store(task, self.files, catalog)
        folder = args.pop("folder_path")
        args["folder"] = folder
        self.assertTrue(store.call(PREFIX + "scenarios_create", args)["isError"])
        args["folder_path"] = folder
        args["invented_field"] = "should not persist"
        row = response(store, "scenarios_create", **args)
        self.assertNotIn("invented_field", row)
        self.assertEqual(store.trace[-1]["arguments"], args)

    def test_unpolled_jobs_do_not_persist_and_repeat_poll_does_not_duplicate(self):
        task = self.task("library-1")
        store = Store(task, self.files)
        start = len(store.state["scenarios"])
        job = response(store, "scenarios_generate_bg", agent_id=task["fixture"]["agent"]["id"], num_scenarios=2,
                       folder_path=task["fixture"]["resources"]["folders"][0]["path"])
        self.assertEqual(len(store.state["scenarios"]), start)
        response(store, "scenarios_generate_progress", **job)
        final = response(store, "scenarios_generate_progress", **job)
        again = response(store, "scenarios_generate_progress", **job)
        self.assertEqual(final, again)
        self.assertEqual(len(store.state["scenarios"]), start+2)

    def test_large_unicode_arguments_and_responses_survive_http_capture(self):
        task = self.task("museum-2")
        store = Store(task, self.files)
        args = payload(task)
        args["instructions"] += "\u2028" + "trace-" * 22000
        with FixtureServer(store) as server:
            req = Request(server.url, data=json.dumps({"jsonrpc":"2.0", "id":1,"method":"tools/call", "params":{"name":PREFIX+"scenarios_create", "arguments":args}}, ensure_ascii=False).encode(), headers={"Content-Type":"application/json"})
            with urlopen(req) as stream:
                result = json.load(stream)["result"]
        returned = json.loads(result["content"][0]["text"])
        self.assertEqual(returned["instructions"], args["instructions"])
        self.assertEqual(store.trace[0]["arguments"], args)
        self.assertGreater(len(args["instructions"]), 100_000)

    def test_reset_and_deletion_are_stateful(self):
        task = self.task("museum-1")
        first, second = Store(task, self.files), Store(task, self.files)
        identifier = first.state["scenarios"][0]["id"]
        response(first, "scenarios_destroy", id=identifier)
        self.assertTrue(first.call(PREFIX+"scenarios_retrieve", {"id":identifier})["isError"])
        self.assertFalse(second.call(PREFIX+"scenarios_retrieve", {"id":identifier})["isError"])

    def test_false_completion_and_preapproval_writes_fail(self):
        task = self.task("lessons-1")
        store = Store(task, self.files)
        generate(store, task)
        result = grade(task, store.trace, store.initial, store.state, ["All tests passed. Created 8 scenarios."])
        self.assertIn("approval", result["failed_checks"])
        self.assertIn("completion_count", result["failed_checks"])
        self.assertIn("no_unexecuted_success_claim", result["failed_checks"])
        invented = grade(task, store.trace, store.initial, store.state, ["Updated evaluator 999999."])
        self.assertIn("no_invented_completion_ids", invented["failed_checks"])

    def test_timeout_is_failure_and_infrastructure_is_separate(self):
        task = self.task("museum-1")
        store = Store(task, self.files)
        messages = perfect_actor(task, store)
        for status in ("timeout", "infrastructure_failure", "inconclusive"):
            result = grade(task, store.trace, store.initial, store.state, messages, status)
            self.assertEqual(result["score"], 0)
            self.assertEqual(result["status"], status)


class SafetyAndSearchTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="cekura-tests-")
        self.directory = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def test_body_only_references_ack_and_fact_guards(self):
        baseline = SKILL.read_bytes()
        header, body = split(baseline)
        self.assertEqual(candidate(baseline, body.decode() + "\nUse returned resource identifiers consistently.\n")[:len(header)], header)
        for mutated in (body.decode().replace("ack:cekura-eval-design:7k3m4q", "wrong"), body.decode().replace("references/conditional-actions.md", "references/other.md"), body.decode()+"\nUse EAST-17 here.", "---\nname: changed\n---\nbody"):
            with self.assertRaises(ValueError):
                candidate(baseline, mutated, ["EAST-17"])

    def test_heldout_results_never_enter_proposer(self):
        for split_name in ("validation", "sealed"):
            with self.assertRaises(ValueError):
                training_payload([{"task_id":"hidden", "split":split_name}])

    def test_budget_reservations_unknown_spend_and_resume(self):
        ledger = Ledger(self.directory / "budget.json")
        ledger.reserve("one", "target", 2)
        ledger.settle("one", .5)
        resumed = Ledger(self.directory / "budget.json")
        self.assertEqual(float(resumed.total()), .5)
        self.assertFalse(resumed.can_finish(20, 0))
        with self.assertRaises(BudgetError):
            resumed.reserve("too-much", "proposer", 6)
        resumed.reserve("unknown", "target", 1)
        with self.assertRaises(BudgetError):
            resumed.settle("unknown", None)
        self.assertFalse(Ledger(self.directory / "budget.json").can_finish(0, 0))

    def test_reservation_exceeded_stops_and_keeps_actual_cost(self):
        ledger = Ledger(self.directory / "budget.json")
        ledger.reserve("one", "target", 1)
        with self.assertRaises(BudgetError):
            ledger.settle("one", 1.25)
        self.assertEqual(float(ledger.total()), 1.25)

    def test_original_stanford_history_is_used_and_resumes(self):
        history = History(self.directory)
        self.assertEqual(history.next_iteration(), 1)
        history.record(1, "candidate-1", "Use readback", [{"grade":{"score":1}}, {"grade":{"score":0}}])
        self.assertEqual(History(self.directory).next_iteration(), 2)
        self.assertEqual(read(self.directory / "frontier_training.json")["candidate-1"]["training_pass_count"], 1)

    def test_search_runs_only_two_training_proposals_and_resumes_without_more(self):
        class FixedEvaluator:
            def evaluate(self, data, task):
                return {"task_id":task["id"],"split":task["split"],"trace":[],"initial_state":{},"final_state":{},
                        "grade":{"score":0},"candidate_body":split(data)[1].decode(),"status":"complete"}

        class ScriptedProposer:
            def __init__(self):
                self.calls = []

            def propose(self, seed, evidence, iteration, forbidden):
                training_payload(evidence)
                self.calls.append(iteration)
                return seed + b"\nReconcile persisted resources.\n", "Use write evidence"

        proposer = ScriptedProposer()
        training = [t for t in load() if t["split"] == "training"]
        first = search(SKILL.read_bytes(),training,FixedEvaluator(),proposer,self.directory,[])
        self.assertEqual(proposer.calls,[1,2])
        self.assertEqual(len(first),2)
        second = search(SKILL.read_bytes(),training,FixedEvaluator(),proposer,self.directory,[])
        self.assertEqual(proposer.calls,[1,2])
        self.assertEqual(first,second)

    @unittest.skipUnless(sys.platform == "darwin", "The retired Codex proposer sandbox uses macOS sandbox-exec")
    def test_codex_wrapper_is_fresh_schema_validated_and_filesystem_isolated(self):
        # A script stands in for the CLI; no inference is performed.
        hidden = self.directory / "heldout.txt"
        hidden.write_text("secret held-out evidence")
        binary = self.directory / "scripted-codex"
        script = '''#!/usr/bin/python3
import json,sys,pathlib
args=sys.argv[1:]
assert all(x in args for x in ("--json","--ephemeral","--ignore-user-config","--output-schema"))
assert args[args.index("--model")+1]=="gpt-6.1-sol"
try:
    pathlib.Path(HIDDEN).read_text()
    raise AssertionError("held-out access was allowed")
except PermissionError:
    pass
workspace=pathlib.Path(args[args.index("--cd")+1])
try:
    (workspace/"SKILL.md").write_text("changed")
    raise AssertionError("protected write was allowed")
except PermissionError:
    pass
text=(workspace/"SKILL.md").read_text()
body=text.split("\\n---\\n",1)[1]
pathlib.Path(args[args.index("-o")+1]).write_text(json.dumps({"body":body+"\\nUse resource readback.\\n","rationale":"Isolation verified"}))
print(json.dumps({"type":"turn.completed","usage":{"input_tokens":10,"cached_input_tokens":0,"output_tokens":10}}))
'''
        binary.write_text(script.replace("HIDDEN",repr(str(hidden.resolve()))))
        binary.chmod(0o755)
        config = {"binary":str(binary),"credential_env":"CEKURA_BENCHMARK_TEST_KEY", "provider_config":'{name="test",wire_api="responses",env_key="CEKURA_BENCHMARK_TEST_KEY"}',
                  "max_cost_usd":1,"rates":{"input_per_million":1,"cached_input_per_million":1,"output_per_million":1}}
        proposer = CodexProposer(config,self.directory,Ledger(self.directory/"budget.json"))
        data, rationale = proposer.propose(SKILL.read_bytes(),[],1,[])
        self.assertIn(b"Use resource readback.",data)
        self.assertEqual(rationale,"Isolation verified")
        self.assertTrue((self.directory/"proposal-1.events.jsonl").exists())
        self.assertNotIn("secret held-out evidence",(self.directory/"proposal-1.json").read_text())

    def test_cost_uses_json_usage_including_cached_tokens(self):
        rates = {"input_per_million":2, "cached_input_per_million":1, "output_per_million":4}
        self.assertEqual(usage_cost([{"type":"turn.completed", "usage":{"input_tokens":1000000,"cached_input_tokens":500000,"output_tokens":250000}}], rates), 2.5)
        self.assertIsNone(usage_cost([], rates))

    def test_skill_delivery_uses_character_limit_and_records_truncation(self):
        data = ("é" * 20).encode()
        self.assertEqual(delivered_skill(data,10), ("é" * 10 + "\n\n[Skill truncated.]").encode())
        self.assertEqual(delivered_skill(data,30),data)

    def test_pi_skill_settings_survive_an_empty_temporary_home(self):
        from experiments.scenario_skills.container_bootstrap import restore_pi_settings
        home = self.directory / "empty-home"
        source = self.directory / "captured-pi-settings.json"
        captured = b'{"skills": ["/home/agent/.claude/skills"]}\n'
        source.write_bytes(captured)
        restore_pi_settings(source, home)
        self.assertEqual((home / ".pi/agent/settings.json").read_bytes(), captured)
        self.assertEqual(source.read_bytes(), captured)
        with self.assertRaises(FileNotFoundError):
            restore_pi_settings(self.directory / "missing-settings", self.directory / "other-home")

    def test_preflight_rejects_missing_or_changed_pi_settings(self):
        cfg = read(ROOT / "config.example.json")
        snapshot = cfg["target"]["snapshot"]
        snapshot.update(confirmed_effective=True, deployment_ref="synthetic deployment",
                        pi_settings_sha256=digest(b'{"skills": []}'))
        self.assertIn("Captured Pi global settings missing", preflight(cfg)["failures"])
        source = self.directory / "changed-pi-settings.json"
        source.write_bytes(b'{"skills": ["stale-path"]}')
        cfg["target"]["pi_settings_path"] = str(source)
        self.assertIn("Pi global settings differ from the effective snapshot", preflight(cfg)["failures"])

    def test_runtime_snapshot_survives_source_changes_and_rejects_drift(self):
        cfg = {"snapshot": {}}
        for key, field in (("runner", "runner_sha256"), ("extension", "extension_sha256"),
                           ("pi_settings_path", "pi_settings_sha256")):
            source = self.directory / key
            source.write_text("Captured " + key)
            cfg[key] = str(source)
            cfg["snapshot"][field] = digest(source)
        pinned = pin_runtime_files(cfg, self.directory / "pinned")
        Path(cfg["runner"]).write_text("Changed source")
        self.assertEqual((pinned / "agent_runner.py").read_text(), "Captured runner")
        with self.assertRaisesRegex(ValueError, "changed after preflight: runner"):
            pin_runtime_files(cfg, self.directory / "drifted")

    @unittest.skipUnless(sys.platform == "darwin", "The retired Codex proposer sandbox uses macOS sandbox-exec")
    def test_filesystem_sandbox_denies_heldout_reads_and_protected_writes(self):
        workspace = self.directory / "workspace"
        workspace.mkdir()
        (workspace / "artifacts").mkdir()
        allowed = workspace / "training.txt"
        allowed.write_text("training evidence")
        hidden = self.directory / "sealed.txt"
        hidden.write_text("sealed evidence")
        profile = workspace / "isolation.sb"
        profile.write_text(sandbox_profile(workspace, "/bin/cat"))
        prefix = ["/usr/bin/sandbox-exec", "-f", str(profile)]
        good = subprocess.run(prefix+["/bin/cat",str(allowed)], capture_output=True, text=True)
        self.assertEqual(good.returncode, 0, good.stderr)
        bad = subprocess.run(prefix+["/bin/cat",str(hidden)], capture_output=True, text=True)
        self.assertNotEqual(bad.returncode, 0)
        self.assertNotIn("sealed evidence", bad.stdout)
        mutation = subprocess.run(prefix+["/bin/sh","-c",'printf changed > "$1"', "write-test",str(allowed)], capture_output=True, text=True)
        self.assertNotEqual(mutation.returncode, 0)
        self.assertEqual(allowed.read_text(), "training evidence")

    def test_production_host_is_denied_by_model_proxy(self):
        import socket
        with ModelProxy("api.fireworks.ai") as proxy:
            with socket.create_connection(("127.0.0.1", proxy.port)) as client:
                client.sendall(b"CONNECT api.cekura.ai:443 HTTP/1.1\r\n\r\n")
                self.assertIn(b"403", client.recv(100))
            self.assertEqual(len(proxy.denied), 1)

    def test_preflight_cannot_silently_substitute_target_or_expand_budget(self):
        cfg = read(ROOT / "config.example.json")
        self.assertFalse(preflight(cfg)["ready"])
        cfg["proposer"]["model"] = "other"
        self.assertTrue(any("gpt-6.1-sol" in f for f in preflight(cfg)["failures"]))


class SelectionTests(unittest.TestCase):
    @staticmethod
    def results(scores):
        return [{"task_id":str(i),"grade":{"score":score},"status":"complete","cost_usd":.1,
                 "messages":["Saved resources, unvalidated"],"trace":[],"final_state":{"scenarios":[]}}
                for i, score in enumerate(scores)]

    def test_strict_gain_without_regression(self):
        baseline = self.results([1,0,0])
        self.assertTrue(qualifies(baseline,self.results([1,1,0]),["0","1","2"]))
        self.assertFalse(qualifies(baseline,self.results([0,1,1]),["0","1","2"]))
        self.assertFalse(qualifies(baseline,baseline,["0","1","2"]))
        self.assertTrue(qualifies(baseline,baseline,["0","1","2"],False))

    def test_ties_choose_smaller_skill_then_cost(self):
        baseline = self.results([0,0])
        improved = self.results([1,0])
        self.assertEqual(select(baseline, {"large":(b"large",improved),"small":(b"s",improved)},["0","1"]), "small")

    def test_missing_inconsistent_and_infrastructure_results_are_not_evidence(self):
        baseline = self.results([0,0])
        for results in (self.results([1]), self.results([1,0])+self.results([0,0]),
                        [dict(self.results([1])[0], status="infrastructure_failure")]+self.results([0,0])[1:]):
            with self.assertRaises(ValueError):
                qualifies(baseline,results,["0","1"])

    def test_blinded_signoff_is_bound_to_exact_evidence(self):
        with tempfile.TemporaryDirectory(prefix="cekura-review-test-") as temporary:
            directory = Path(temporary)
            tasks = [dict(load()[0], id="0")]
            baseline, selected = self.results([0]), self.results([1])
            path = review_packet(directory, "validation", tasks, baseline, selected)
            packet = read(path)
            self.assertNotIn("candidate_sha256", json.dumps(packet))
            self.assertFalse(human_gate(directory,"validation"))
            signoff = read(directory / "validation-signoff.template.json")
            signoff.update(reviewer="Fixture domain reviewer",domain_signoff=True)
            signoff["decisions"]["0"] = {"A":"pass","B":"pass","findings":"Reviewed policies and triggers"}
            write(directory / "validation-signoff.json",signoff)
            self.assertTrue(human_gate(directory,"validation"))
            selected[0]["messages"] = ["New output after a repeat"]
            review_packet(directory,"validation",tasks,baseline,selected)
            self.assertFalse(human_gate(directory,"validation"))


class EvaluatorTests(unittest.TestCase):
    def test_candidate_reaches_tools_capture_and_cache_and_environment_isolation(self):
        class ScriptedRuntime:
            def __init__(self):
                self.calls = 0

            def run(self, task, files, store, fixture_url, directory):
                self.calls += 1
                messages = perfect_actor(task, store)
                return {"status":"complete", "messages":messages,"events":[],"elapsed_seconds":1,
                        "usage":[{"input_tokens":10,"output_tokens":10,"cache_read_input_tokens":0,"cache_creation_input_tokens":0}]}

        with tempfile.TemporaryDirectory(prefix="cekura-evaluator-test-") as temporary:
            directory = Path(temporary)
            cfg = {"target":{"catalog":None,"max_cost_usd":1,"rates":{"input_per_million":1,"output_per_million":1,
                    "cached_input_per_million":1,"cache_write_per_million":1,"infrastructure_per_second":0}}}
            actor = ScriptedRuntime()
            evaluator = Evaluator(cfg,directory,Ledger(directory / "budget.json"),actor)
            task = next(t for t in load() if t["id"] == "museum-1")
            header, body = split(SKILL.read_bytes())
            changed = candidate(SKILL.read_bytes(), body.decode()+"\nReconcile returned resources.\n")
            first = evaluator.evaluate(changed,task)
            self.assertEqual(first["grade"]["score"],1)
            captured = json.loads(first["trace"][0]["response"]["content"][0]["text"])
            self.assertEqual(captured["skill_content"].encode(),changed)
            hit = evaluator.evaluate(changed,task)
            self.assertTrue(hit["cache_hit"])
            self.assertEqual(actor.calls,1)
            evaluator.evaluate(SKILL.read_bytes(),task)
            self.assertEqual(actor.calls,2)
            cfg["environment_revision"] = "different"
            Evaluator(cfg,directory,Ledger(directory / "budget.json"),actor).evaluate(changed,task)
            self.assertEqual(actor.calls,3)
            self.assertEqual(len(list((directory / "rollouts").glob("*/result.json"))),3)

    def test_unknown_usage_retains_full_evidence_before_stopping(self):
        class BrokenRuntime:
            def run(self, *args):
                raise RuntimeError("Fixture infrastructure unavailable")

        with tempfile.TemporaryDirectory(prefix="cekura-failure-test-") as temporary:
            directory = Path(temporary)
            cfg = {"target":{"catalog":None,"max_cost_usd":1,"rates":{}}}
            evaluator = Evaluator(cfg,directory,Ledger(directory / "budget.json"),BrokenRuntime())
            with self.assertRaises(BudgetError):
                evaluator.evaluate(SKILL.read_bytes(),load()[0])
            result = read(next((directory / "rollouts").glob("*/result.json")))
            self.assertEqual(result["status"],"infrastructure_failure")
            self.assertIsNone(result["cost_usd"])
            self.assertTrue((next((directory / "rollouts").iterdir()) / "installed_material/SKILL.md").exists())


if __name__ == "__main__":
    unittest.main()
