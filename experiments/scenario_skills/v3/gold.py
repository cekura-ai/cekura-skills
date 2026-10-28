"""v3 judge gold: one correct and one failing session per template, on domains no task uses.

Each template contributes a calibration example on one gold domain and a qualification
example with the opposite label on the other, so the judge is qualified on every template
without seeing a split domain. Bad sessions reproduce the failure observed in real chats;
labels are engineering drafts until a human reviews them.
"""
from ..v2.judge import packet
from .build_fixtures import make_task
from .domains import GOLD_DOMAINS
from .reference import evidence
from .templates import TEMPLATES

QUALIFICATION_MIN = 17  # of 18: at least 90% correct, and no critical false pass.


def examples():
    gold = []
    for index, template in enumerate(TEMPLATES):
        for stage, domain, good in (("calibration", GOLD_DOMAINS[0], index % 2 == 0), ("qualification", GOLD_DOMAINS[1], index % 2 == 1)):
            task = make_task(template, domain)
            result = evidence(task, good)
            gold.append({"id": "%s-%s-%s" % (template, domain, "good" if good else "bad"), "template": template, "family": task["family"],
                         "stage": stage, "expected_verdict": "pass" if good else "fail", "critical": not good, "packet": packet(task, result)})
    return gold
