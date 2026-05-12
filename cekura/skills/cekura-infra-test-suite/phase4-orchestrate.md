# Phase 4 — Orchestrate Local Bot Runs

Wire the scenarios to the local bot so they can run as a CI gate. This phase produces a run script and a config override mechanism.

---

## 4a. Understand how to start the bot locally

From Phase 1 you should already know the start command and any required env vars. If not, check `CLAUDE.md` and `memory.md` now. If still unclear, ask the user:

> "How do I start the bot locally? What command, which env vars, and how do I tell it which SIP URI to dial?"

Write what the user tells you into `memory.md` before continuing.

---

## 4b. Add a config override mechanism (if not already present)

The run script needs to tell the bot which SIP URI to dial for each scenario. Cekura assigns a different outbound number per run — the bot must read it dynamically.

Choose the approach that fits how the bot already reads config:

### Option A — JSON override file

The bot reads a file at startup and applies overrides before dialing:

```python
# In the bot's local run setup (e.g. dial_out_utils.py, local_runner.py)
import json, pathlib

ci_override_path = pathlib.Path(__file__).parent / ".ci_test_config.json"
if ci_override_path.exists():
    overrides = json.load(open(ci_override_path))
    if "sip_uri" in overrides:
        body["dialout_settings"]["sip_uri"] = overrides["sip_uri"]
    # add other override keys as needed
```

The run script writes this file before starting the bot and deletes it after.

### Option B — Environment variable

The bot reads a `SIP_URI` env var (or similar) at startup:

```python
import os
sip_uri = os.environ.get("CI_SIP_URI", default_sip_uri)
```

The run script passes it via `env={**os.environ, "CI_SIP_URI": sip_uri}` when spawning the bot.

**Important — avoid overriding nested config dicts wholesale.** Python's `dict.update()` replaces entire nested structures. Overriding a top-level `configuration` dict wipes nested fields like `model.provider`. Only override specific leaf keys.

---

## 4c. Write the run script

Generate a script tailored to this codebase. Use the start command, env vars, and override mechanism from steps 4a–4b. The outline below is the logical skeleton — adapt it to match how this project actually works.

```python
SCENARIOS = [
    {"id": <cekura_scenario_id>, "name": "S1 — Full Pipeline E2E",       "timeout_s": 400},
    {"id": <cekura_scenario_id>, "name": "S2 — Mid-Speech Interruption",  "timeout_s": 400},
    # ... one entry per confirmed scenario from Phase 2
]

AGENT_ID       = <cekura_agent_id>
BOT_NUMBER     = "<bot_inbound_number>"   # the number Cekura calls to reach the bot
SIP_DOMAIN     = "cekura-pipecat-local.sip.twilio.com"  # or equivalent for this setup
BOT_START_CMD  = ["python", "bot.py"]    # adapt to this project
BOT_ENV_EXTRAS = {"LOCAL_RUN": "1"}      # any required env vars

async def run_scenario(session, scenario):
    # 1. Trigger Cekura run — obtain the testing agent's outbound number
    result = await session.post(
        "https://api.cekura.ai/test_framework/v1/scenarios/run_scenarios/",
        json={"agent_id": AGENT_ID, "scenarios": [scenario["id"]],
              "frequency": 1, "agent_number": BOT_NUMBER, "concurrency_limit": 1}
    )
    data = await result.json()
    run_id     = data["result_id"]
    run_number = data["runs"][0]["number"]
    sip_uri    = f"sip:{run_number}@{SIP_DOMAIN}?X-CallerId={BOT_NUMBER}"

    # 2. Inject SIP URI (Option A or B from step 4b)
    inject_sip_uri(sip_uri)

    # 3. Start bot
    proc = subprocess.Popen(BOT_START_CMD, env={**os.environ, **BOT_ENV_EXTRAS})
    await asyncio.sleep(20)  # wait for transport setup + outbound dial

    # 4. Poll until complete or timeout
    deadline = time.time() + scenario["timeout_s"]
    run_data  = {}
    while time.time() < deadline:
        r = await session.get(f"https://api.cekura.ai/test_framework/v1/runs/{run_id}/")
        run_data = await r.json()
        if run_data.get("status") == "completed":
            break
        await asyncio.sleep(10)
    else:
        print(f"  [poll] Timed out after {scenario['timeout_s']}s")

    # 5. Record result
    passed = run_data.get("evaluation_status") == "success"

    # 6. Cleanup
    proc.terminate()
    clear_sip_uri_injection()

    return passed
```

---

## 4d. Timing notes

| Wait | Why |
|---|---|
| **20s after bot start** | The bot needs time to connect to the WebRTC/SIP transport and initiate the outbound dial to Cekura |
| **10s poll interval** | Short enough to catch completion promptly; long enough not to spam the API |
| **Timeout buffer** | Add 60–90s beyond the expected call duration — evaluations run asynchronously after the call ends |

**Do not start the bot before you have `runs[0].number` from the API response.** The bot will dial before the testing agent is listening.

---

## 4e. Verify the setup

Run one scenario end-to-end manually before committing the script:

1. Start the script for a single scenario
2. Confirm the bot dials out to Cekura's number
3. Confirm the Cekura run moves through `pending → in_progress → completed`
4. Confirm the result shows `evaluation_status = success` or a meaningful failure

If the bot fails to dial (wrong SIP URI, startup timing issue) or the run times out, fix those before running the full suite.

---

## Phase 4 Complete

The suite is ready as a CI gate. To use it:

1. Run the script before merging a PR
2. All scenarios marked `pr_gate: True` must pass
3. A timed-out scenario is a CI failure — investigate whether the bot is dialing correctly

**Next steps:**
- To add behavioral (non-infra) test coverage → **cekura-eval-design**
- To add or tune metrics → **cekura-metric-design**
- To debug a failing production call → **cekura-fixing-prod-issues**
