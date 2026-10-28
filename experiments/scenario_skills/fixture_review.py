"""Human review of synthetic policies and frozen expectations before inference."""
from .common import digest, read, write
from .dataset import load


def packet(directory):
    tasks = load()
    evidence = [{k: t[k] for k in ("id", "pack_id", "family", "split", "request", "fixture", "expected")}
                | {"documents": t.get("documents", []), "followups": t.get("followups", []),
                   "context": t.get("context", {}), "starting_resources": t.get("starting_resources", t["fixture"]["resources"]),
                   "generator_response": t.get("generator_response", [])} for t in tasks]
    value = {"dataset_sha256": digest(tasks), "tasks": evidence}
    write(directory / "fixture-review.json", value)
    rows = ["# Synthetic fixture expectation review", "", "Review the supplied policies, requested behavior and expected observable checks before any baseline inference.",
            "All domains and facts are synthetic. Approval freezes expectations for this experiment.", ""]
    for task, review in zip(tasks, evidence):
        rows += ["## " + task["id"] + " — " + task["family"], "", "Split: " + task["split"], "", task["request"], "",
                 "Agent policy: " + task["fixture"]["agent"].get("description", ""), ""]
        for document in task.get("documents", []):
            rows += [document["name"] + ":", "", document["content"], ""]
        rows += ["Scripted follow-ups:", "", "```json", __import__("json").dumps(review["followups"], indent=2), "```", "",
                 "<details><summary>Context, initial resources and fixed generation response</summary>", "", "```json",
                 __import__("json").dumps({k: review[k] for k in ("context", "starting_resources", "generator_response")}, indent=2),
                 "```", "", "</details>", ""]
        rows += ["Expected observable checks:", "", "```json", __import__("json").dumps(task["expected"], indent=2), "```", ""]
    (directory / "fixture-review.md").write_text("\n".join(rows))
    write(directory / "fixture-signoff.template.json", {"dataset_sha256": digest(tasks), "packet_sha256": digest(value),
          "reviewer": "", "domain_signoff": False, "policies_and_expectations_reviewed": False, "findings": ""})
    return directory / "fixture-review.md"


def gate(directory):
    path = directory / "fixture-signoff.json"
    if not path.exists():
        return False
    signoff = read(path)
    return (signoff.get("dataset_sha256") == digest(load())
            and signoff.get("packet_sha256") == digest(read(directory / "fixture-review.json"))
            and bool(signoff.get("reviewer")) and signoff.get("domain_signoff") is True
            and signoff.get("policies_and_expectations_reviewed") is True)


def engineering_gate(directory, config):
    """Engineering evidence is distinct from human semantic/domain signoff."""
    from .contract_probe import identity
    target = config["target"]
    probe = read(target["contract_probe_path"])
    passed = probe.get("passed") is True and all(probe.get(k) == v for k, v in identity(target["catalog"]).items())
    write(directory / "engineering-fixture-review.json", {
        "dataset_sha256": digest(load()), "packet_sha256": digest(read(directory / "fixture-review.json")),
        "contract_probe_sha256": digest(probe), "authorization": config["review_authorization"],
        "engineering_checks_passed": passed, "human_domain_signoff": False,
        "semantic_status": "pending_human_review"})
    return passed
