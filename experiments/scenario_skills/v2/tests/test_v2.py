from decimal import Decimal
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from experiments.scenario_skills.common import digest, read, write
from experiments.scenario_skills.budget import Ledger, BudgetError
from experiments.scenario_skills.fixture import main_agent_variables
from experiments.scenario_skills.skill import SKILL
from experiments.scenario_skills.v2.dataset import load, FAMILIES, canaries
from experiments.scenario_skills.v2.fixture import Store
from experiments.scenario_skills.v2.grader import grade, combine
from experiments.scenario_skills.v2.judge import ClaudeJudge, packet, check
from experiments.scenario_skills.v2.budget import family_costs, minimum_plan, plan_cost, MARGIN
from experiments.scenario_skills.tests.helpers import cumulative_ledger
from experiments.scenario_skills.v2.proposer import training_workspace, screen
from experiments.scenario_skills.v2.probe import skill_evidence
from experiments.scenario_skills.remote_claude import cli_args
from experiments.scenario_skills.v2.review import prepare, gate


from experiments.scenario_skills.v2.contract_probe import actor


class Fixtures(unittest.TestCase):
    def test_all_72_contracts_are_executable(self):
        for task in load():
            with self.subTest(task=task["id"]):
                store = Store(task, {"SKILL.md": SKILL.read_bytes()})
                messages = actor(task, store)
                verdict = grade(task, store.trace, store.initial, store.state, messages)
                self.assertEqual(verdict["failed_checks"], [])

    def test_pack_allocation_and_distinct_training_contexts(self):
        tasks = load()
        self.assertEqual(len(canaries(tasks)), 12)
        for family in FAMILIES:
            train = [t for t in tasks if t["family"] == family and t["split"] == "training"]
            self.assertEqual(len({t["pack_id"] for t in train}), 2)
        self.assertGreaterEqual(sum(len(t["followups"]) >= 2 for t in tasks), 36)

    def test_external_deletion_is_captured_and_state_resets(self):
        task = next(t for t in load() if t["id"] == "lifecycle-0")
        store = Store(task, {})
        actor(task, store)
        store.apply_events(1)
        self.assertEqual(store.state["scenarios"], store.initial["scenarios"])
        self.assertTrue(any(c.get("kind") == "external_delete" for c in store.trace))
        fresh = Store(task, {})
        self.assertEqual(fresh.trace, [])
        self.assertEqual(fresh.next_id, task["fixture"]["next_id"])

    def test_partial_and_failed_jobs_report_real_saved_counts(self):
        for tid, count in (("repair-3", 2), ("repair-2", 0)):
            t = next(t for t in load() if t["id"] == tid)
            store = Store(t, {})
            actor(t, store)
            self.assertEqual(len(store.state["scenarios"]) - len(store.initial["scenarios"]), count)

    def test_source_evidence_contains_bytes_not_just_filename(self):
        t = next(t for t in load() if t["id"] == "sources-0")
        store = Store(t, {})
        actor(t, store)
        sources = next(c["resolved_sources"] for c in store.trace if c.get("resolved_sources"))
        self.assertEqual(sources[0]["sha256"], digest(t["documents"][0]["content"].encode()))
        self.assertEqual(sources[0]["content"], t["documents"][0]["content"])

    def test_agent_read_does_not_supply_missing_private_profile_values(self):
        task = next(t for t in load() if t["id"] == "variables-0")
        store = Store(task, {})
        for op, args in (("aiagents_retrieve", {"id": store.agent["id"]}), ("aiagents_list", {})):
            result = json.loads(store.call(op, args)["content"][0]["text"])
            agent = result if op.endswith("retrieve") else result["results"][0]
            self.assertNotIn("required_variables", agent)
            self.assertTrue(agent["auto_dynamic_variables"])
        self.assertEqual(task["followups"][0]["message"], task["clarification_reply"])
        self.assertTrue(task["followups"][0]["reply_to_clarification"])


class Grading(unittest.TestCase):
    def test_long_text_truncation_fails_and_valid_full_text_passes(self):
        t = next(t for t in load() if t["id"] == "verbatim-2")
        store = Store(t, {})
        messages = actor(t, store)
        self.assertEqual(grade(t, store.trace, store.initial, store.state, messages)["score"], 1)
        store.state["scenarios"][-1]["instructions"] = "First archive entry only"
        self.assertIn("field:instructions", grade(t, store.trace, store.initial, store.state, messages)["failed_checks"])

    def test_wrong_routing_missing_variables_and_invented_ids_fail(self):
        t = next(t for t in load() if t["id"] == "variables-0")
        store = Store(t, {})
        messages = actor(t, store)
        store.state["profiles"][0]["information"] = {}
        self.assertIn("variables", grade(t, store.trace, store.initial, store.state, messages)["failed_checks"])
        messages = ["Saved evaluator 999999. All tests passed."]
        failed = grade(t, store.trace, store.initial, store.state, messages)["failed_checks"]
        self.assertIn("no_invented_ids", failed)
        self.assertIn("no_executed_claim", failed)
        t = dict(t, expected=dict(t["expected"], route="generate"))
        self.assertIn("routing", grade(t, store.trace, store.initial, store.state, messages)["failed_checks"])

    def graded(self, task_id, mutate=None, messages=None):
        t = next(t for t in load() if t["id"] == task_id)
        store = Store(t, {})
        result = actor(t, store)
        if mutate:
            mutate(store)
        return grade(t, store.trace, store.initial, store.state, messages or result)["failed_checks"]

    def test_modifying_the_original_during_duplication_fails(self):
        self.assertEqual(self.graded("lifecycle-2"), [])
        def edit_original(store):
            next(r for r in store.state["scenarios"] if r["id"] == 101311)["expected_outcome_prompt"] = "Changed original"
        failed = self.graded("lifecycle-2", edit_original)
        self.assertIn("allowed_writes:scenarios", failed)
        self.assertIn("untouched:101311", failed)
        def same_folder(store):
            store.state["scenarios"][-1]["folder_path"] = store.initial["folders"][0]["path"]
        self.assertIn("duplicate_destination", self.graded("lifecycle-2", same_folder))
        def unchanged_outcome(store):
            store.state["scenarios"][-1]["expected_outcome_prompt"] = store.initial["scenarios"][0]["expected_outcome_prompt"]
        self.assertIn("duplicate_fields", self.graded("lifecycle-2", unchanged_outcome))

    def test_profile_reuse_and_fill_only_profile_updates(self):
        self.assertEqual(self.graded("variables-1"), [])
        def new_profile(store):
            store.state["profiles"].append(dict(store.state["profiles"][0], id=999))
            store.state["scenarios"][-1]["test_profile"] = 999
        self.assertIn("profile_reuse", self.graded("variables-1", new_profile))
        def overwrite_shared(store):
            store.state["profiles"][0]["information"]["main_agent_variables"]["ParcelCode"] = "000000"
        self.assertIn("allowed_writes:profiles", self.graded("variables-1", overwrite_shared))
        self.assertEqual(self.graded("variables-0"), [])  # Filling registered nulls is allowed.
        def rename_key(store):
            values = store.state["profiles"][0]["information"]["main_agent_variables"]
            values["parcelcode"] = values.pop("ParcelCode")
        self.assertIn("allowed_writes:profiles", self.graded("variables-0", rename_key))

    def test_folder_and_configuration_mutations_fail(self):
        def drop_folder(store):
            store.state["folders"] = store.state["folders"][1:]
        self.assertIn("allowed_writes:folders", self.graded("routing-1", drop_folder))
        def change_configuration(store):
            store.state["configuration"] = {"metrics": ["duplicate"]}
        self.assertIn("allowed_writes:configuration", self.graded("configuration-2", change_configuration))

    def test_repair_accepts_recovery_or_two_saved_with_truthful_report(self):
        self.assertEqual(self.graded("repair-0"), [])
        def unrecovered(store):
            store.state["scenarios"].pop()
        failed = self.graded("repair-0", unrecovered, ["Saved current resources: two cases; the third remains unresolved."])
        self.assertNotIn("requested_count", failed)

    def test_semantic_false_and_uncertain_never_pass(self):
        contract = {"score": 1, "checks": {"count": True}, "failed_checks": []}
        for verdict in ("fail", "uncertain"):
            grade_result = combine(contract, {"criteria": [{"id": "policy", "verdict": verdict}]})
            self.assertEqual(grade_result["score"], 0)
        self.assertEqual(combine(contract, {"criteria": [{"id": "policy", "verdict": "pass"}]})["score"], 1)

    def test_judge_missing_or_duplicate_criteria_rejected(self):
        evidence = {"rubric": [{"id": "policy"}, {"id": "trigger"}]}
        row = {"id": "policy", "verdict": "pass", "attribution": "not_applicable", "evidence": ["/rubric"], "reason": "Supported"}
        for rows in ([row], [row, row]):
            with self.assertRaises(ValueError): check({"criteria": rows}, evidence)

    def test_blinded_packet_excludes_candidate_and_loading_material(self):
        t = load()[0]
        r = {"messages": [], "initial_state": {}, "final_state": {}, "trace": [{"name": "mcp__cekura__cekura_load_skill", "response": "secret revision"}], "status": "complete", "candidate_body": "candidate-2"}
        value = json.dumps(packet(t, r))
        self.assertNotIn("secret revision", value)
        self.assertNotIn("candidate-2", value)

    def test_judge_cannot_cite_missing_locations_or_rubric_as_evidence(self):
        evidence = {"rubric": [{"id": "policy"}], "evidence": {"final_state": {}}}
        for pointers in (["/evidence/final_state/missing"], ["/rubric/0"], ["/evidence/final_state", "/rubric/0"], ["/request"]):
            row = {"id": "policy", "verdict": "pass", "attribution": "not_applicable", "evidence": pointers, "reason": "Supported"}
            with self.assertRaises(ValueError): check({"criteria": [row]}, dict(evidence, request="Make one check."))

    def test_judge_may_cite_sources_alongside_evidence_and_must_attribute_failures(self):
        evidence = {"rubric": [{"id": "policy"}], "request": "Make one check.", "documents": [{"name": "p.txt", "content": "Policy"}],
                    "evidence": {"final_state": {}}}
        row = {"id": "policy", "verdict": "fail", "attribution": "generator", "reason": "Unsupported outcome",
               "evidence": ["/documents/0/content", "/request", "/evidence/final_state"]}
        self.assertEqual(check({"criteria": [row]}, evidence)["criteria"][0]["attribution"], "generator")
        for attribution, verdict in (("not_applicable", "fail"), ("authoring", "pass")):
            with self.assertRaises(ValueError):
                check({"criteria": [dict(row, attribution=attribution, verdict=verdict)]}, evidence)

    def test_actual_user_replies_survive_blinded_packet(self):
        task = load()[0]
        r = {"messages": ["saved"], "user_turns": [task["request"], "The answer is café  Ω"], "initial_state": {}, "final_state": {}, "trace": [], "status": "complete"}
        self.assertEqual(packet(task, r)["evidence"]["user_turns"], r["user_turns"])

    def test_skill_delivery_requires_correlated_exact_tool_result(self):
        exact = "---\ncekura-eval-design\n## distinctive skill body"
        mentions = json.dumps({"system": exact, "messages": []})
        self.assertEqual(skill_evidence([mentions], exact), [])
        body = {"messages": [{"role": "assistant", "content": [{"type": "tool_use", "id": "one", "name": "Skill", "input": {"skill": "cekura:cekura-eval-design"}}]},
                             {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "one", "content": exact}]}]}
        self.assertTrue(skill_evidence([json.dumps(body)], exact)[0]["full_loader_content"])
        body["messages"][-1]["content"][0]["content"] = exact[:20]
        self.assertFalse(skill_evidence([json.dumps(body)], exact)[0]["full_loader_content"])


class ReviewAndBudget(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="cekura-v2-tests-")
        self.directory = Path(self.temp.name)
    def tearDown(self): self.temp.cleanup()

    def test_human_review_cannot_be_assumed(self):
        prepare(self.directory)
        self.assertFalse(gate(self.directory))
        value = read(self.directory / "fixture-and-gold-signoff.template.json")
        value.update(reviewer="Human reviewer", domain_signoff=True, fixture_expectations_approved=True)
        write(self.directory / "fixture-and-gold-signoff.json", value)
        self.assertTrue(gate(self.directory))
        value["packet_sha256"] = "wrong"
        write(self.directory / "fixture-and-gold-signoff.json", value)
        self.assertFalse(gate(self.directory))

    def test_minimum_plan_uses_highest_family_cost_margin_and_all_cost_parts(self):
        r = {"family": "routing", "task_id": "r1", "cost_usd": 1, "generator_cost_usd": .5, "infrastructure_reserved_usd": .1, "repeat": 0}
        self.assertEqual(family_costs([r, dict(r, task_id="r2", cost_usd=.2)]), {"routing": Decimal("1.6")})
        tasks = [t for t in load() if t["family"] == "routing"]
        self.assertEqual(plan_cost({"routing": Decimal("1.6")}, tasks), Decimal("1.6") * len(tasks))
        config = {"target": {"rates": {"input_per_million": 4.5, "cached_input_per_million": .45, "output_per_million": 22.5},
                             "admission": {"input_token_limit": 1048576, "output_token_limit": 32000}}, "backend": {"generator": {"endpoints": []}}}
        train = [t for t in load() if t["split"] == "training" and t["family"] == "routing"]
        plan = minimum_plan([r], train[1:], train, [], [], [], config)
        self.assertEqual(Decimal(plan["needed_usd"]), Decimal("1.6") * (len(train) * 2 - 1) * MARGIN + Decimal(plan["headroom_usd"]))
        with self.assertRaises(BudgetError):
            plan_cost({}, tasks)

    def test_proposer_workspace_denies_heldout_history(self):
        with self.assertRaises(ValueError): training_workspace(SKILL.read_bytes(), [{"split": "sealed", "task_id": "x"}])
        with self.assertRaises(ValueError): training_workspace(SKILL.read_bytes(), [{"split": "training", "task_id": "x"}])

    def test_shared_training_files_decode_losslessly(self):
        record = {"split": "training", "task_id": "example", "trace": [{"content": "é" * 1000}], "initial_state": {}, "final_state": {},
                  "candidate_body": "é" * 1000, "grade": {"score": 0, "failed_checks": ["policy"]}}
        files = training_workspace(SKILL.read_bytes(), [record])
        def decode(value):
            if isinstance(value, dict) and set(value) == {"$text_file"}: return files[value["$text_file"]]
            if isinstance(value, dict): return {k: decode(v) for k, v in value.items()}
            if isinstance(value, list): return [decode(v) for v in value]
            return value
        self.assertEqual(decode(json.loads(files["training/trace-000.json"])), record)
        self.assertEqual(len([n for n in files if n.startswith("training/shared/")]), 1)

    def test_proposer_read_tools_deny_auth_and_runtime_state(self):
        cfg = {"model": "claude-opus-5-5", "reasoning_effort": "high", "max_cost_usd": 2.5, "subscription_only": True, "read_training_files": True}
        args = cli_args(cfg, {})
        self.assertEqual(args[args.index("--tools") + 1], "Read,Grep,Glob")
        permissions = json.loads(args[args.index("--settings") + 1])["permissions"]
        self.assertTrue(permissions["blockReadsOutsideWorkingDirectories"])
        self.assertEqual(len(permissions["deny"]), 4)
        self.assertIn("Read(//state/**)", permissions["deny"])
        self.assertEqual(args[args.index("--allowedTools") + 1], "Read(//workspace/**),Grep,Glob")

    def test_duplicate_noop_or_unsupported_hypothesis_rejected(self):
        parent = b"parent"
        history = [{"candidate_sha256": digest(parent), "grade": {"failed_checks": ["routing"]}}]
        rationale = {"hypothesis": "Repair routing", "targeted_checks": ["routing"]}
        screen(b"new", parent, history, rationale, [])
        for data, reason, previous in ((parent, rationale, []), (b"new", rationale, [(b"new", rationale)]),
                                       (b"other", rationale, [(b"new", rationale)]), (b"new", dict(rationale, targeted_checks=["already-passing"]), [])):
            with self.assertRaises(ValueError): screen(data, parent, history, reason, previous)

    def test_qualification_rejects_critical_false_pass_and_wrong_paraphrase(self):
        prepare(self.directory)
        signoff = read(self.directory / "fixture-and-gold-signoff.template.json")
        signoff.update(reviewer="Test human", domain_signoff=True, fixture_expectations_approved=True)
        write(self.directory / "fixture-and-gold-signoff.json", signoff)
        gold = read(self.directory / "fixture-and-gold-review.json")["gold"]
        for wrong in (None, "routing-gold-3", "sources-paraphrase-gold-2"):
            def session(prompt, evidence, schema, key):
                item = next(g for g in gold if g["packet"] == evidence)
                verdict = item["expected_verdict"]
                if item["id"] == wrong: verdict = "fail" if verdict == "pass" else "pass"
                return {"criteria": [{"id": evidence["rubric"][0]["id"], "verdict": verdict, "attribution": "not_applicable" if verdict == "pass" else "authoring",
                                      "evidence": ["/evidence/final_state"], "reason": "Offline control"}]}
            judge = ClaudeJudge({"model": "offline", "wrong": wrong}, self.directory, None, call=session)
            self.assertEqual(judge.qualify()["passed"], wrong is None)
            if wrong is None:
                self.assertTrue(judge.qualified())
                write(self.directory / "adjudications/unrelated-trial.json", {"human_changed": True})
                self.assertTrue(judge.qualified())  # Target-trial adjudications do not touch qualification.
                key = judge.key(gold[0]["packet"])
                write(self.directory / "adjudications" / (key + ".json"), {"human_changed": True})
                self.assertFalse(judge.qualified())
                for path in (self.directory / "adjudications").glob("*.json"): path.unlink()

    def test_criterion_adjudication_overrides_only_named_criteria_on_cached_reads(self):
        session = lambda prompt, evidence, schema, key: {"criteria": [
            {"id": "a", "verdict": "uncertain", "attribution": "authoring", "evidence": ["/evidence/final_state"], "reason": "Unclear"},
            {"id": "b", "verdict": "pass", "attribution": "not_applicable", "evidence": ["/evidence/final_state"], "reason": "Supported"}]}
        judge = ClaudeJudge({"model": "fixed"}, self.directory, None, call=session)
        evidence = {"rubric": [{"id": "a"}, {"id": "b"}], "evidence": {"final_state": {}}}
        self.assertEqual(judge.judge(evidence)["criteria"][0]["verdict"], "uncertain")
        key = judge.key(evidence)
        write(self.directory / "adjudications" / (key + ".json"), {"reviewer": "Domain reviewer", "evidence_sha256": digest(evidence),
              "judge_sha256": judge.identity, "criteria": {"a": {"verdict": "fail", "reason": "Outcome invents a refund", "attribution": "authoring"}}})
        value = judge.judge(evidence)
        self.assertEqual([c["verdict"] for c in value["criteria"]], ["fail", "pass"])
        self.assertEqual((value["criteria"][0]["judge_verdict"], value["criteria"][0]["adjudicated_by"]), ("uncertain", "Domain reviewer"))
        write(self.directory / "adjudications" / (key + ".json"), {"reviewer": "Domain reviewer", "evidence_sha256": "stale",
              "judge_sha256": judge.identity, "criteria": {"a": {"verdict": "fail", "reason": "x"}}})
        with self.assertRaises(ValueError): judge.judge(evidence)

    def test_judge_cache_and_trial_isolation(self):
        class Session:
            count = 0
            def __call__(self, prompt, evidence, schema, key):
                self.count += 1
                return {"criteria": [{"id": "p", "verdict": "pass", "attribution": "not_applicable", "evidence": ["/evidence/final_state"], "reason": "Supported"}]}
        session = Session()
        judge = ClaudeJudge({"model": "fixed"}, self.directory, None, call=session)
        evidence = {"rubric": [{"id": "p"}], "evidence": {"final_state": {}}}
        judge.judge(evidence); judge.judge(evidence)
        self.assertEqual(session.count, 1)
        judge.judge(evidence, trial=1)
        self.assertEqual(session.count, 2)


if __name__ == "__main__": unittest.main()
