# Phase 5 — Orchestrate Local Bot Runs

Wire the Cekura scenarios to the local bot so they can run as a CI gate. This phase is entirely driven by how the bot actually works — use the Q9 workflow description from `/tmp/infra-workflow-descriptions.md` (written by Phase 2) for the start command, env vars, and connection injection mechanism. Fall back to the raw Phase 1 Q9 answer or ask the user if the file doesn't have what's needed.

---

## 5a. Find the local run instructions

Check in this order:

1. **`CLAUDE.md` and `memory.md`** — read both if they exist. They may already document exactly how to start the bot and connect it to a test run.
2. **Phase 1 Q9 answer** — use what was discovered about the start command, env vars, and config override mechanism.
3. **Ask the user** if neither source has what's needed:

> "How do I run the bot locally for testing? I need: the start command, any required env vars or flags, and how to tell the bot which endpoint to connect to for a given Cekura run."

Write whatever the user provides into `memory.md` before continuing.

---

## 5b. Understand the connection model

Based on Q1 and the local run instructions, determine how Cekura connects to the bot:

**Cekura calls the bot (inbound to bot):**
- Cekura dials the bot's phone number or SIP endpoint
- The bot must be reachable at a stable address before the run starts
- The run script starts the bot first, waits for it to be ready, then triggers the Cekura run

**Bot calls Cekura (outbound from bot):**
- Cekura provides a number or endpoint for the bot to dial
- The run script triggers the Cekura run first to get the connection details, then starts the bot with those details injected

**WebRTC / WebSocket:**
- Cekura may provide a room URL, token, or WebSocket endpoint
- The run script extracts the connection details from the Cekura run response and passes them to the bot

Identify which model applies — it determines the ordering of steps in the run script.

---

## 5c. Add a connection detail injection mechanism (if not already present)

For each scenario run, Cekura assigns fresh connection details (phone number, SIP URI, room URL, token, etc.). The bot must receive these dynamically — hardcoding them breaks CI.

Choose the mechanism that fits how the bot already reads config:
- **Environment variable** — pass connection details as an env var when spawning the bot
- **Config file** — write a temporary file the bot reads at startup; delete it after the run
- **CLI argument** — pass the connection detail as a command-line argument
- **API / webhook** — if the bot exposes a control endpoint, POST the details before starting the call

Do not override broad config objects wholesale — only inject the specific fields that change per run.

---

## 5d. Write the run script

The run script logic depends on the connection model from 5b, but the overall structure is the same for every bot:

```
For each scenario:
  1. Trigger the Cekura run → get connection details for this run
  2. Inject connection details into the bot (mechanism from 4c)
  3. Start the bot (or signal it to dial, if already running)
  4. Wait for the bot to establish the connection
  5. Poll Cekura until the run status is completed or timeout is reached
  6. Record pass / fail (evaluation_status == "success")
  7. Stop the bot and clean up injected config
```

Use the start command, env vars, and override mechanism from steps 5a–5c. Adapt the polling interval and startup wait to the bot's actual startup time — a bot that takes 5s to connect needs a shorter wait than one that dials out over SIP and needs transport negotiation.

---

## 5e. Verify before running the full suite

Run one scenario end-to-end before committing the script:

1. Trigger a single scenario run
2. Confirm the bot connects to Cekura's testing agent
3. Confirm the run moves through `pending → in_progress → completed`
4. Confirm the result reflects a real pass or a meaningful failure — not a timeout or connection error

Fix any connection or timing issues at this point. A timeout is not a test result — it means the bot didn't connect.

---

## Phase 5 Complete

The suite is ready as a CI gate. Run the script before merging a PR — every scenario must pass.

**Next steps:**
- To add behavioral (non-infra) test coverage → **cekura-eval-design**
- To debug a failing production call → **cekura-fixing-prod-issues**
