---
name: config-sync
description: >-
  At DEPLOY time, push the running bot's OWN truth into its Cekura agent so the
  agent's Cekura-side config never silently drifts from the code: (1) the
  dynamic variables the prompt uses, (2) the mock tools for simulated calls, and
  (3) the assembled system prompt → the Cekura agent `description`. Use this
  WHENEVER wiring a voice-AI codebase's deploy pipeline to keep Cekura in sync,
  or whenever someone says "sync dynamic variables to Cekura", "push mock tools",
  "sync system prompt to agent description", "update the agent description on
  deploy", "stop config drift", "PATCH the Cekura agent at deploy", "post-deploy
  config sync", or "cekura_sync". Applies to ANY repo, language, framework, and
  domain, and ANY deploy system (CI, container build, serverless, k8s). The
  example voice agent — Python + Jinja2 + GitHub Actions + Cloud Run — is just
  one instantiation; adapt the contract, don't copy the Python.
license: MIT
compatibility: Requires a Cekura account (https://dashboard.cekura.ai) — sign in via OAuth or use an API key.
metadata:
  author: cekura
  version: "0.1.0"
---

<!-- cekura-ack-tag: ack:config-sync:5d7m4q -->
> **Cekura skill verification tag:** `ack:config-sync:5d7m4q`
> Before taking any action, call `mcp__cekura__cekura_skill_started` with `skill_name="config-sync"`, `verification_tag="ack:config-sync:5d7m4q"`, and `plugin_version="0.9.0"`. It returns immediately and lets Cekura see which skills are in use.

# config-sync — push the code's truth into Cekura at deploy

## What this skill does

At **deploy time**, after the new revision is live, run a post-deploy step that
PATCHes the deployment's Cekura agent with config **derived from the bot being
deployed**. The sync is nothing more than a few **plain HTTP calls** to the
Cekura agent API (`GET` to read the live agent, `PATCH` to update it) — so it can
be a script in **any language** (Python, Node/TS, Go, …), a `curl` step in your
deploy pipeline, or a task in your CI tooling. There is nothing Python-specific
about the contract.

> **The auto-sync workflow doesn't change — only how you send it.** You still run
> this as a post-deploy step. For Python, use the official `cekura` SDK/CLI instead
> of hand-rolling the GET/PATCH: `pip install cekura`, then the `agents` resource
> (`client.agents.retrieve(...)` / `client.agents.update(...)`) or the CLI
> (`cekura agents`, `cekura config`). Other languages use the plain HTTP calls
> below.

> **Don't stop at a manual script — wire the auto-sync into CI/CD.** The sync only
> holds config in step with the code if it runs on every deploy, not by hand. After
> the sync script exists, **set up the automation**: if the repo is on GitHub,
> create a **GitHub Actions** workflow that runs the sync (post-deploy, or on merge
> to the environment's branch) using repo secrets for `CEKURA_API_KEY`. If it's on
> another CI (GitLab CI, Bitbucket Pipelines, CircleCI, Jenkins, …), **ask the user
> which one they use** and add the equivalent job there. Only fall back to
> "run it manually" if the user explicitly declines automation. See `ci-cd`'s CD
> half for the per-environment env wiring and the "fail the workflow, not the
> deploy" gating.

Three things are synced, each onto its own agent field:

1. **Dynamic variables** — the runtime-injected variables the prompt uses → the
   agent's `dynamic_variables`.
2. **Mock tools** — canned tool responses so simulated test calls don't hit the
   live backend → the agent's `mock_tools`.
3. **The assembled system prompt** — the full prompt the bot runs on, flattened
   from all its scattered sources → the agent's `description`.

The target agent per environment comes from `CEKURA_AGENT_ID` (the same value
the deploy sets on the running service — see the sibling `ci-cd` skill's
"CD half: deploy env wiring"). Each sync sources its three things **from the same
truth the bot runs on** — the just-deployed code for self-hosted bots, or the
platform's config/API for a managed bot — so what ships to Cekura is exactly what
ships to prod.

## Why

Cekura's evaluators and scenario generators read the agent's config — its
variables, its mock tools, and its `description` (the system prompt) — to decide
how to simulate calls and what to grade against. If that config is hand-edited
in the Cekura UI, it **silently drifts** from the bot the moment code changes: a
renamed tool, a new prompt variable, a reworded procedure. Evals then test a
fiction — passing or failing against a bot that no longer exists — and nobody
notices because nothing errors.

The fix is to make **code the source of truth** and push it on every deploy: the
synced config is *derived*, not authored in Cekura. Drift becomes impossible
because the only way to change the agent's config is to change the code and
deploy it — and the deploy fails loudly when code and its curated data disagree
(see the guardrail below).

## The contract (durable — true for any repo/language/domain)

### Three syncs, three agent fields

Each deploy PATCHes the agent once per sync with a single-field payload. These
are ordinary HTTP requests against the Cekura agent API — issue them from
whatever language or tool your deploy uses (an HTTP client, `curl`, your CI's
request step); the shape below is the same regardless:

```
PATCH <agent endpoint>/{agent_id}    {"dynamic_variables": [ {name, description}, … ]}
PATCH <agent endpoint>/{agent_id}    {"mock_tools":        [ {name, description, information: [{input, output}, …]}, … ]}
PATCH <agent endpoint>/{agent_id}    {"description":       "<assembled system prompt text>"}
```

A PATCH **replaces the whole field it carries**: items omitted are deleted,
items whose `name` matches update in place, new names are created. So each
payload must be the *complete* desired set, not a delta.

### Names are the source of truth in the BOT; curated data lives in a config file

For variables and tools, the **set of names** is extracted from wherever the bot
authoritatively declares them — the running code for a self-hosted bot, or the
platform's config/API for a managed bot:

- **Dynamic-variable names** come from the prompt source — every variable the
  prompt *prints*. (Self-hosted: the prompt template(s) in code. Managed
  platform: the variables declared in the platform's prompt/config.)
- **Mock-tool names** come from wherever the agent's callable tools are declared
  — the tool-builder/registry in code, or the tool/function definitions in the
  platform.

But Cekura also needs data that **cannot be derived from that source**: a human
description per variable, and per tool a description + canned **`information`** — a
**list of `{input, output}` example mappings** (NOT a `mock_data` object; verified
live, sending `mock_data` 400s with "Information must be a list of input-output
mappings"). Live handlers return non-deterministic data (random ids, uuids,
datetimes), so these canned examples stand in for sims. That
curated data lives in a **config file (e.g. YAML/JSON) beside the sync script**,
keyed by name.

### The guardrail: drift is rejected in BOTH directions

This is the heart of the skill. A push **fails** (and therefore fails the
deploy) if the names derived from the bot and the curated config don't line up
**either way** ("the bot" = the running code, or the managed platform's config):

- A name present in **the bot** with **no config entry** → fail. (A new
  variable/tool was added but never documented; the push must not ship a
  placeholder or silently drop it.)
- A config entry with **no matching name in the bot** → fail. (A stale entry
  left behind after a rename/removal.)

Both directions matter. Forward-only checking lets dead config rot in place;
reverse-only checking lets undocumented names ship blank. Rejecting both forces
the engineer to edit the bot's source **and** config together, every time.
(Tools that
legitimately have no mock data — call-control / transfer functions handled
elsewhere — go on an explicit **denylist** in code so they're excluded rather
than demanding a fixture.)

### Idempotent: diff, skip, `--force`

Before each PATCH, the script **GETs the live agent and diffs** the desired set
against it, comparing only the fields the sync owns (ignore server-added keys
like `id` and list ordering). If nothing changed, it prints "nothing to push"
and makes **no write**. So a deploy that didn't touch prompts/tools is a cheap
no-op. A `--force` flag overrides the diff and pushes regardless.

### Failure must not roll back the live service

The sync runs **after** the new revision is healthy and serving. A sync failure
(e.g. a new tool with no fixture) **fails the workflow loudly** but does **not**
roll back the running app — the bot stays up; the operator fixes the config and
re-runs. Never gate the deploy's go-live on the sync; gate only the workflow's
green check.

### A separate dry-run path

Each sync supports a **dry-run** that prints what it would extract/push, makes no
API calls, and never fails on missing config — so engineers can iterate locally
before a deploy ever runs.

## Adapt to your stack (checklist)

Work through these for your repo — the answers wire the contract above into your
pipeline:

- **Where are your dynamic variables defined?** Wherever the prompt is authored
  — a template in code (Jinja/Handlebars/f-strings/a DSL/JSON), or the prompt
  field of a managed platform. The variables the prompt *prints* (not
  control-flow-only flags) are your name source of truth.
- **Where are your tools built?** The function/registry/schema list the agent
  exposes to the model — in a self-hosted tool-builder, or the platform's
  tool/function definitions. That declaration is the mock-tool name source of
  truth. Tools with no mockable return (transfer/hangup) → denylist them.
- **Where is your prompt assembled from?** One file, or base + partials +
  conditional branches, or a platform-rendered prompt? Produce the **full** text
  Cekura holds as `description`. If branches are mutually exclusive at runtime,
  emit **all** of them side by side — it's reference material, not an executed
  prompt (see flattening below). Leave runtime/dynamic values as visible
  placeholders.
- **How/when does your deploy run a post-deploy step?** CI job, `postDeploy`
  hook, k8s Job, one-shot container `run`, a `curl` step, or a platform webhook.
  It must run **after** the health check, and should read its three things from
  the **same truth that just shipped** (the built artifact for self-hosted code,
  or the platform's live config/API for a managed bot).
- **What language/tool issues the API calls?** Anything that can make HTTP
  requests — your deploy script's language, `curl`, or your CI's request step.
  The sync is just `GET`/`PATCH` against the Cekura agent API; pick whatever your
  pipeline already speaks.
- **How do you inject creds into that step?** It needs `CEKURA_API_KEY` and the
  per-environment `CEKURA_AGENT_ID`, passed as env/secrets (see `ci-cd`'s
  "CD half: deploy env wiring"). Resolve the agent id from `CEKURA_AGENT_ID` (or an
  explicit `--agent-id`) so prod→prod agent, dev→dev.

### Stack notes (where the three things come from)

The contract is identical across stacks; only the *source* of the three things
changes. In every case the sync ends in the same `GET`/`PATCH` HTTP calls.

- **Custom / self-hosted code (any language — Python, Node/TS, Go, …).** Extract
  variable names from your prompt template(s) and tool names from your
  tool-builder, then call the Cekura agent API from your deploy script (or a
  `curl` step). The reference implementation below is one such script in Python.
- **LiveKit Agents / Pipecat.** Same as self-hosted code — your prompt and tools
  live in your repo. Run the same extraction + API calls as a **post-deploy
  step**, written in whatever language your deploy already uses; nothing requires
  it to be Python.
- **Managed platform (Vapi / Retell / ElevenLabs).** Your prompt, tools, and
  variables may live in the platform rather than your repo, so **source the three
  things from the platform's config/API** (fetch the assistant/agent definition),
  then `PATCH` them into the Cekura agent exactly the same way. Curated data
  (descriptions, `information` examples) still lives in your config file beside the sync.

## Reference implementation (example voice agent — Python/Jinja2/GitHub Actions/Cloud Run; example, adapt don't copy)

Everything in this section is **ONE illustration in ONE language** — a Python +
Jinja2 + GitHub Actions + Cloud Run instantiation of the stack-neutral contract
above. The steps and contract stand on their own without it; read this only for a
concrete worked example, and translate the *ideas* (extract names → validate
against curated config → diff → `GET`/`PATCH`) into your own stack rather than
porting the Python. The repo has `scripts/cekura_sync/` with three CLI modules
plus a shared client; everything below is Python/Jinja specific.

### Shared client so the three syncs can't drift

`_client.py` holds the agent-id resolution and GET/PATCH plumbing once;
`patch_agent` takes a payload dict so each sync just supplies its one field:

```python
# scripts/cekura_sync/_client.py
# Base url is env-sourced; the agent-patch path is API-version-specific —
# confirm it against the current Cekura API docs (or discover it from the API)
# rather than hard-coding a version that may have moved.
CEKURA_BASE_URL = os.environ.get("CEKURA_BASE_URL", "https://api.cekura.ai")
# Version-specific — confirm against the current API docs. As of this writing the
# v2 agent endpoint is "/test_framework/v2/aiagents/{agent_id}/" (auth header
# X-CEKURA-API-KEY); a PATCH there REPLACES the whole field it carries.
AGENT_PATCH_PATH = "/test_framework/v2/aiagents/{agent_id}/"  # confirm version; see API docs

def resolve_agent_id(explicit: int | None = None) -> int:
    # --agent-id wins, else CEKURA_AGENT_ID (the value the deploy set on the service)
    if explicit is not None:
        return explicit
    return int(os.environ["CEKURA_AGENT_ID"])  # raises if unset → fail loudly

def patch_agent(agent_id: int, payload: dict, api_key: str) -> dict:
    # payload is e.g. {"dynamic_variables": [...]} / {"mock_tools": [...]} / {"description": ...}
    url = CEKURA_BASE_URL + AGENT_PATCH_PATH.format(agent_id=agent_id)
    resp = httpx.patch(url, headers={"X-CEKURA-API-KEY": api_key}, json=payload, timeout=30.0)
    resp.raise_for_status()
    return resp.json()
```

### Diff-and-skip (idempotent push)

Each sync builds a name-keyed *signature* of only the fields it owns, diffs
against the live agent, and skips the write when nothing changed:

```python
# _signature(items) -> {name: comparable-view}, ignoring server fields & order.
# ... in main(), before patching:
if not args.force:
    current = fetch_agent(agent_id, api_key).get("dynamic_variables") or []
    added, removed, changed = diff_variables(current, desired)
    if not (added or removed or changed):
        print(f"✓ agent {agent_id}: already up to date; nothing to push")
        return 0
patch_agent(agent_id, {"dynamic_variables": desired}, api_key)
```

### The both-directions guardrail (YAML curation)

`build_dynamic_variables` raises on either direction of drift; `mock_tools.py`'s
`validate_fixtures` mirrors it. Names come from code, descriptions from YAML:

```python
problems = []
for n in sorted(n for n in names if not descriptions.get(n)):
    problems.append(f"{n}: no description in {YAML}")                       # code w/o YAML
for n in sorted(set(descriptions) - names):
    problems.append(f"{n}: description has no matching variable (renamed/removed?)")  # YAML w/o code
if problems:
    raise ValueError("descriptions are invalid — fix " + YAML + ":\n  " + "\n  ".join(problems))
```

Names are extracted by parsing the Jinja AST — a variable counts only if it's
*printed* (`{{ x }}`), not merely used in `{% if %}`/`{% for %}`; mock-tool names
come from `build_gemini_tools()` minus a `MOCK_TOOL_DENYLIST` of
control/transfer tools (`end_call`, `transfer_to_*`).

### The `_FlatteningLoader` idea (assembling the full prompt)

The real prompt is `system_prompt.jinja2` + nine `{% include %}` partials + a
dozen `{% if config_flag %}` branches. Cekura needs the **context**, not the
runtime branching, so `agent_prompt.py` emits **every** branch body:

```python
class _FlatteningLoader(FileSystemLoader):
    """Strip if/elif/else/for control tags from the template AND every partial,
    so one render emits ALL branch bodies side by side. {% include %} is kept,
    so partials still inline (and get the same stripping when served)."""
    def get_source(self, environment, template):
        source, filename, uptodate = super().get_source(environment, template)
        return _CONTROL_TAG_RE.sub("", source), filename, uptodate
```

Dynamic + per-call runtime vars render as visible `{{ name }}` placeholders (via
a truthy `_Placeholder`); structured/loop vars fall through to a chainable
`_PathPlaceholder` that prints its dotted `{{ path }}`. The result is
deliberately **not a runnable prompt** — it can hold "transfer IS available" and
"transfer is NOT available" together — because it's reference material that is
location/tenant-agnostic and reads no real config.

### Deploy-workflow wiring (post-deploy, inside the built image)

The agent id is declared once at the top of the workflow and consumed both by
the service env and by the sync step, so they can't drift:

```yaml
env:
  CEKURA_AGENT_ID: "<your-prod-agent-id>"   # prod; dev/sandbox workflows set their own
# ... build, deploy, then: Smoke test /health (sync runs AFTER it passes) ...
- name: Sync Cekura dynamic variables + mock tools + agent prompt
  env:
    CEKURA_API_KEY: ${{ secrets.CEKURA_API_KEY }}
  run: |
    docker run --rm -e CEKURA_API_KEY -e CEKURA_AGENT_ID \
      "${{ steps.image.outputs.tag }}" \
      sh -c "python -m scripts.cekura_sync.dynamic_variables && \
             python -m scripts.cekura_sync.mock_tools && \
             python -m scripts.cekura_sync.agent_prompt"
```

Running the sync inside the just-built image (not the CI checkout) guarantees the
extraction logic and dependencies match exactly what's serving. Because it runs
*after* the health check, a sync failure fails the workflow without rolling back
the live service.

### The packaging fix (`.dockerignore`)

The deploy runs `python -m scripts.cekura_sync.*` **inside the image**, but the
`.dockerignore` excluded `scripts/` wholesale → `ModuleNotFoundError` at deploy.
Re-include just the sync package (and the `scripts/` package marker), keeping the
rest of `scripts/` out:

```dockerignore
# Exclude scripts/ from the runtime image EXCEPT the cekura_sync package: the
# deploy runs `python -m scripts.cekura_sync.*` inside the image. Use
# `scripts/*` not `scripts/` — Docker can't re-include a path whose parent dir
# was excluded wholesale.
scripts/*
!scripts/__init__.py
!scripts/cekura_sync
```

## Verify offline (no deploy needed)

- Run each sync in **`--check`** (validate, no API calls): it runs the
  both-directions guardrail and exits non-zero on drift — this is also the CI/PR
  gate. Then `--dry-run` to eyeball the exact payload it would push.
- After a real push, read the agent back (`aiagents_retrieve` / GET) and diff the
  fields you own against what you sent. Watch the two diff traps below (the server
  reorders JSON keys; the read API omits `freetext_params`) — a correct diff
  should report "nothing to push" on an unchanged re-run.
- Confirm idempotency explicitly: run the full sync **twice**; the second run
  must no-op on all three (vars/tools/prompt).

## Gotchas

- **Packaging (`.dockerignore` / build excludes).** If the sync runs inside the
  deployed artifact, the sync code must be **in** that artifact. A blanket
  ignore of a scripts/tools directory surfaces as `ModuleNotFoundError` only at
  deploy time. Exclude `dir/*`, then re-include exactly the sync package and its
  package marker — a wholesale parent exclude can't be undone by re-including a
  child in some ignore syntaxes.
- **Sync failure must not roll back.** Order: deploy → health check → sync. The
  sync is *post*-deploy verification, not a gate on go-live; a missing fixture
  turns the workflow red, it doesn't take the bot down.
- **Both-directions drift check.** It's tempting to only fail on
  code-without-config. Don't — also fail on config-without-code, or stale
  entries accumulate silently and the config slowly lies again.
- **PATCH replaces, doesn't merge.** Always send the complete set. And diff only
  the fields you own (`name`, `description`, `information`, …) — comparing
  server-added `id`/`url`/order reports spurious changes and never no-ops.
- **The server reorders JSON object keys on read → your diff never no-ops.** The
  agent read API returns nested objects (e.g. each `information` entry `{input, output}`)
  with keys in a DIFFERENT order than you sent. A naive `JSON.stringify` compare
  then reports a change every run and re-pushes forever. Canonicalize before
  comparing: a **key-sorted / stable stringify** of the nested structures, not
  raw serialization.
- **The read API may not echo every field you write (e.g. `freetext_params`).**
  A field accepted on write but absent from the read representation can't be
  diffed — comparing it (present in desired, missing in current) forces a
  perpetual re-push. Diff only fields the GET actually returns; keep sending the
  write-only field, and accept that a change to it alone needs `--force`.
- **The `description` is not runnable.** Flattening every branch produces
  contradictory instructions side by side on purpose — it's context for the
  grader, never executed.

## Common mistakes to avoid

- Hand-editing the agent's variables/mock tools/`description` in the Cekura UI.
  That *is* the drift this skill exists to prevent — change the bot's source
  (code or platform config) and deploy.
- Authoring the names in your config file instead of extracting them from the
  bot. Names must come from the running prompt/tool declarations (code or
  platform); the config file holds only the data that source can't supply
  (descriptions, mock outputs).
- Running the sync against stale truth — e.g. from the CI checkout instead of the
  deployed artifact, or against an old copy of the platform config — so the
  synced config can differ from what's actually serving.
- Gating go-live on the sync, or rolling back the service when the sync fails.
- Sending a delta PATCH (it deletes everything you omitted) or skipping the diff
  and PATCHing on every deploy (noisy writes, no no-op).
- Forgetting the per-environment `CEKURA_AGENT_ID` and syncing dev config onto
  the prod agent — resolve the id from what the deploy set on the service (see
  `ci-cd`'s "CD half: deploy env wiring").
- Treating a no-mock-data control/transfer tool as missing config — denylist it
  in code instead of inventing a fake fixture.
