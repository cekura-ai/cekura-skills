"""Seed one task's synthetic resources into the rollout database and read state back.

Scripts run through ``manage.py shell`` inside the rollout's own backend container, so
they use the pinned models directly. Seeded rows keep their fixture primary keys; real
rows created during the rollout keep the IDs the backend assigns. Nothing is renumbered,
so the only mapping is the identity, recorded explicitly with each rollout.
"""
import json

MARKER = "CEKURA_JSON:"

SEED = r'''
import json
from django.contrib.auth import get_user_model
from django.core.management.color import no_style
from django.db import connection
from django.db.models.signals import post_save
from django.apps import apps
from test_framework.models import (create_user_related, AIAgent, AIAgentDynamicVariable, Tool, AIAgentTestProfile,
                                   Personality, Metric, ScenarioFolder, Scenario, SettingValue, Result, Run)
from test_framework.conditional_actions_format import to_stored_validated
from user.models import Organization, Project, Membership
from test_framework.enums import RoleChoices
from ltree_folders.fields import encode_label
from product_chat.models import Conversation, Message
from user.views import _generate_oauth_access_token

task = json.loads(TASK)
settings_rows = json.loads(SETTINGS)
fixture = task["fixture"]
agent = fixture["agent"]
resources = task.get("starting_resources") or fixture["resources"]
User = get_user_model()
post_save.disconnect(create_user_related, sender=User)  # It would create a second organization and project.

org = Organization.objects.create(name=agent["name"] + " organization", hide_calls_in_admin=False,
    conditional_actions_generation_enabled=agent.get("default_scenario_type") == "conditional_actions",
    action_rate_limits={"generate_scenarios": {"daily_limit": -1, "monthly_limit": -1, "max_batch": 100}})
user = User.objects.create_user(email="owner-%d@experiment.invalid" % agent["project"], name="Experiment owner", password=None)
Membership.objects.create(organization=org, user=user, role=RoleChoices.ADMIN)
project = Project.objects.bulk_create([Project(id=agent["project"], organization=org, name=agent["name"])])[0]
personalities = {}
for p in fixture["personalities"]:
    personalities[p["id"]] = Personality.objects.create(id=p["id"], organization=org, project=project, name=p["name"],
        description=p["name"], prompt=p.get("prompt", "You are a " + p["name"].lower() + "."), language=p["language"], vapi_settings={})
    project.enabled_personalities.add(personalities[p["id"]])

agents = {}
for a in [agent] + fixture.get("other_agents", []):
    description = a["description"]
    if a.get("greeting"):
        description += "\nGreeting: " + a["greeting"]
    row = AIAgent.objects.create(id=a["id"], organization=org, project=project, user=user, agent_name=a["name"],
        description=description, language=a["language"], inbound=a.get("inbound", True),
        agent_gives_first_message=a.get("agent_speaks_first", True),
        auto_dynamic_variables=[{"name": v["name"], "description": v["name"]} for v in a.get("auto_dynamic_variables", []) if not v.get("deleted")])
    for v in a.get("auto_dynamic_variables", []):
        AIAgentDynamicVariable.objects.create(agent=row, name=v["name"], description=v["name"], is_deleted=bool(v.get("deleted")))
    tools = {}
    for t in a.get("mock_tools", []):
        tools.setdefault(t["name"], []).append(t)
    for name, rows in tools.items():
        Tool.objects.create(id=rows[0]["id"], agent=row, project=project, name=name, description="Mock " + name,
                            information=[{"input": r["input"], "output": r["output"]} for r in rows])
    agents[a["id"]] = row

for p in resources.get("profiles", []):
    AIAgentTestProfile.objects.create(id=p["id"], agent=agents[p.get("agent", agent["id"])], name=p["name"], information=p["information"])
folders = {}
for f in resources.get("folders", []):
    folders[f["path"]] = ScenarioFolder.objects.create(id=f["id"], project=project, name=f["name"], path=encode_label(f["path"]))
for m in fixture.get("metrics", []):
    Metric.objects.create(id=m["id"], agent=agents[m.get("agent", agent["id"])], project=project, name=m["name"],
                          type="llm_judge", eval_type="binary", description=m["name"], prompt="Evaluate: " + m["name"])
metrics = {m.id: m for m in Metric.objects.filter(project=project)}
first_personality = personalities[fixture["personalities"][0]["id"]]
for s in resources.get("scenarios", []):
    mode = s.get("scenario_type", "instruction")
    instructions = s.get("instructions", "")
    if mode == "conditional_actions":
        instructions = json.dumps(to_stored_validated(s["conditional_actions"])[0])
    row = Scenario.objects.create(id=s["id"], agent=agents[s["agent"]], project=project, name=s["name"],
        personality=personalities.get(s.get("personality"), first_personality),
        scenario_language=s.get("scenario_language", "en"), scenario_type=mode, instructions=instructions,
        expected_outcome_prompt=s.get("expected_outcome_prompt", ""), folder=folders[s["folder_path"]],
        test_profile_id=s.get("test_profile"), first_message="", retell_agent_id="", tags=s.get("tags", []))
    if s.get("metrics"):
        row.metrics.set([metrics[i] for i in s["metrics"]])
# Prior test results the target may read: transcripts and metric verdicts, never executed here.
for r in task.get("results") or fixture.get("results", []):
    result = Result.objects.create(id=r["id"], agent=agents[r["agent"]], project=project, name=r["name"], status=r.get("status", "completed"),
                                   success_rate=r.get("success_rate", 0), failed_reasons=r.get("failed_reasons", {}))
    for run in r["runs"]:
        Run.objects.create(id=run["id"], result=result, scenario_id=run["scenario"], personality_id=run.get("personality"),
                           test_profile_id=run.get("test_profile"), status=run.get("status", "completed"), success=run["success"],
                           evaluation=run["evaluation"], transcript_object=run["transcript_object"],
                           transcript="\n".join("%s: %s" % (t["role"], t["content"]) for t in run["transcript_object"]),
                           expected_outcome=run.get("expected_outcome"), duration=run.get("duration", 60.0), call_id="fixture-%d" % run["id"])
for key, value in settings_rows.items():
    SettingValue.objects.update_or_create(key=key, defaults={"value": value})
conversation = Conversation.objects.create(user=user, organization=org, name="Experiment conversation")
if task.get("documents"):
    Message.objects.create(conversation=conversation, role="user", status="complete",
                           metadata={"uploaded_files": {d["name"]: d["content"] for d in task["documents"]}, "project_id": project.id})
models = [m for label in ("user", "test_framework", "product_chat", "ltree_folders") for m in apps.get_app_config(label).get_models()]
with connection.cursor() as cursor:
    for sql in connection.ops.sequence_reset_sql(no_style(), models):
        cursor.execute(sql)
from django.core.cache import cache
cache.delete("llm_fallback:deepseek_provider_order")
token = _generate_oauth_access_token(user, extra_claims={"ctx": "product_chat", "organization_id": org.id})
print(MARKER + json.dumps({"organization": org.id, "user": str(user.id), "project": project.id, "conversation": str(conversation.id),
                           "token": token, "id_map": "identity: every seeded row keeps its fixture primary key"}))
'''

READBACK = r'''
import json
from test_framework.models import AIAgent, AIAgentTestProfile, Personality, Metric, ScenarioFolder, Scenario, Tool, AIAgentDynamicVariable
from test_framework.serializers import ScenarioSerializerV2
from ltree_folders.fields import decode_label

project = int(PROJECT)
def path(value):
    return ".".join(decode_label(label) for label in str(value).split("."))

scenarios, raw = [], []
for s in Scenario.objects.filter(project_id=project, is_deleted=False).order_by("id"):
    data = ScenarioSerializerV2(s).data
    raw.append(json.loads(json.dumps(data, default=str)))
    row = {"id": s.id, "agent": s.agent_id, "project": s.project_id, "name": s.name, "folder_path": path(s.folder.path) if s.folder_id else None,
           "scenario_type": s.scenario_type, "scenario_language": s.scenario_language, "expected_outcome_prompt": s.expected_outcome_prompt,
           "test_profile": s.test_profile_id, "personality": s.personality_id, "first_message": s.first_message,
           "tool_ids": s.tool_ids, "metrics": sorted(s.metrics.values_list("id", flat=True)), "tags": s.tags}
    if s.scenario_type == "conditional_actions":
        row["conditional_actions"] = json.loads(data["instructions"]) if isinstance(data["instructions"], str) else data["instructions"]
    else:
        row["instructions"] = s.instructions
    scenarios.append(row)
profiles = [{"id": p.id, "agent": p.agent_id, "project": p.project_id, "name": p.name, "information": p.information}
            for p in AIAgentTestProfile.objects.filter(agent__project_id=project).order_by("id")]
profiles += [{"id": p.id, "agent": None, "project": p.project_id, "name": p.name, "information": p.information}
             for p in AIAgentTestProfile.objects.filter(project_id=project, agent__isnull=True).order_by("id")]
folders = [{"id": f.id, "name": f.name, "path": path(f.path)} for f in ScenarioFolder.objects.filter(project_id=project).order_by("id")]
agents = [{"id": a.id, "name": a.agent_name, "description": a.description, "language": a.language, "inbound": a.inbound,
           "agent_speaks_first": a.agent_gives_first_message,
           "dynamic_variables": [{"name": v.name, "deleted": v.is_deleted} for v in AIAgentDynamicVariable.objects.filter(agent=a).order_by("name")],
           "mock_tools": [{"id": t.id, "name": t.name, "information": t.information, "deleted": t.is_deleted} for t in Tool.objects.filter(agent=a).order_by("id")]}
          for a in AIAgent.objects.filter(project_id=project).order_by("id")]
metrics = [{"id": m.id, "name": m.name, "agent": m.agent_id, "deleted": m.is_deleted, "prompt": m.prompt}
           for m in Metric.objects.filter(project_id=project).order_by("id")]
from django.forms.models import model_to_dict
def fingerprint(obj):
    # Every stored field except bookkeeping timestamps: any edit to shared configuration shows.
    values = model_to_dict(obj)
    return {k: values[k] for k in sorted(values) if k not in ("created_at", "updated_at", "last_updated_by")}
personalities = [{"id": p.id, "name": p.name, "language": p.language, "fingerprint": json.loads(json.dumps(fingerprint(p), default=str))}
                 for p in Personality.objects.filter(project_id=project).order_by("id")]
metrics = [dict(m, fingerprint=json.loads(json.dumps(fingerprint(Metric.objects.get(id=m["id"])), default=str))) for m in metrics]
print(MARKER + json.dumps({"scenarios": scenarios, "profiles": profiles, "folders": folders,
                           "configuration": {"agents": agents, "metrics": metrics, "personalities": personalities},
                           "raw_scenarios": raw}, default=str))
'''


def script(template, **values):
    head = "MARKER = %r\n" % MARKER + "".join("%s = %r\n" % (k, v) for k, v in values.items())
    return head + template


def parse(output):
    lines = [line for line in output.splitlines() if line.startswith(MARKER)]
    if len(lines) != 1:
        raise RuntimeError("Backend script produced no result: " + output[-1500:])
    return json.loads(lines[0][len(MARKER):])


def seed(stack, task, settings):
    return parse(stack.manage(script(SEED, TASK=json.dumps(task), SETTINGS=json.dumps(settings))))


def readback(stack, project):
    """Normalized grader state plus raw serializer rows; the grader never sees raw formats."""
    value = parse(stack.manage(script(READBACK, PROJECT=str(project))))
    raw = value.pop("raw_scenarios")
    return value, raw
