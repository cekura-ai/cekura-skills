"""Author the v3 fixtures from the fictional domains and the templates, then freeze them.

Run only when authoring a reviewed dataset; the loader verifies the freeze and never rebuilds.
"""
import json
from pathlib import Path

from ..common import digest
from .domains import SPLITS, fixture
from .templates import TEMPLATES, instantiate

TASK_FIELDS = ("family", "request", "followups", "clarification_reply", "documents", "plants", "add", "results", "injections")


def make_task(template, domain, fx=None, split="gold"):
    """One materialized task, as the loader would produce it (also for the gold-only domains)."""
    from .dataset import plant
    fx = fx or fixture(domain)
    body = instantiate(template, domain, fx)
    return dict({k: body[k] for k in TASK_FIELDS}, id="%s-%s" % (template, domain), template=template, domain=domain, benchmark_version=3,
                split=split, pack_id=domain, fixture=fx, starting_resources=plant(fx["resources"], body["plants"], body["add"]),
                expected=body["expected"], context={"agent_id": fx["agent"]["id"], "project_id": fx["agent"]["project"]})


def build():
    packs, expectations = [], {}
    for domain, split in SPLITS.items():
        fx = fixture(domain)
        tasks = []
        for template in TEMPLATES:
            body = instantiate(template, domain, fx)
            tid = "%s-%s" % (template, domain)
            tasks.append(dict({k: body[k] for k in TASK_FIELDS}, id=tid, template=template, domain=domain,
                              context={"agent_id": fx["agent"]["id"], "project_id": fx["agent"]["project"]}))
            expectations[tid] = body["expected"]
        packs.append({"id": domain, "split": split, "fixture": fx, "tasks": tasks})
    data = Path(__file__).parent / "fixtures"
    data.mkdir(exist_ok=True)
    from .gold import examples
    values = {"packs": packs, "expectations": expectations, "judge-gold": examples()}
    for name, value in values.items():
        (data / (name + ".json")).write_text(json.dumps(value, ensure_ascii=False, indent=1) + "\n")
    (data / "freeze.json").write_text(json.dumps({name + "_sha256": digest(v) for name, v in values.items()}, indent=2) + "\n")


if __name__ == "__main__":
    build()
