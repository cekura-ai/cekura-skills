# Self-Hosted — Database Sub-Flavor

Database-flavor agents store their system prompt (and optionally tool definitions) as a row in a database the user owns. The Cekura record's `description` and `llm_system_prompt` are not authoritative — the **live** prompt is the value returned by a SELECT against the user's DB, and the running agent reads from that same row on each request (or on a refresh cadence the user controls).

This sub-flavor reads the current prompt by running the user's SELECT query, lets Diagnose / Apply operate on it the same way every other mode does, and (when the user provides a write query) lands the new prompt by running their UPDATE / equivalent statement. When no write query is provided, the sub-flavor degrades to render-only — the skill prints the rewritten prompt and the user updates the DB themselves.

Use this reference together with the main SKILL.md and [`overview.md`](overview.md).

## When to pick this sub-flavor

Pick `database` when:

- The user's agent code reads the system prompt from a DB row (e.g., `SELECT system_prompt FROM agents WHERE id = $1` at request time, or on a periodic refresh).
- The user has already told you "our prompts live in our database" / "we store prompts in Postgres" / "the prompt is fetched from a table at runtime."
- The Cekura record's `assistant_provider` is `self_hosted` / `custom` / empty AND there is no source file on disk to edit AND the user has DB access they're willing to expose to the skill.

If the prompt is a string constant in a file (the file may itself be in a repo whose state is tracked in a DB, but the runtime reads the file), that is still **websocket / `file`** — pick that sub-flavor instead. If the prompt is stored on the Cekura agent record and the live code reads it from there, pick **pipecat**.

## Database-flavor gate (Phase 1.2 — provider clarification)

When `assistant_provider` is `self_hosted` / `custom` / `agentforce` / empty / unrecognized AND the user has not yet picked a sub-flavor, ask which surface holds the live prompt:

```
This skill can iterate the prompt against several backends. Which one matches
your setup?

  • "vapi"       → Managed VAPI assistant (skill PATCHes via VAPI API).
  • "elevenlabs" → Managed ElevenLabs Conversational AI agent (skill PATCHes
                   via the ElevenLabs API).
  • "pipecat"    → Pipecat pipeline reading prompt from the Cekura agent record.
  • "websocket"  → Custom websocket server whose prompt is a string constant in
                   a source file you can point me at.
  • "database"   → Your prompt is stored as a row in a database (Postgres / MySQL
                   / MongoDB / SQLite / SQL Server / etc.) and your runtime reads
                   it from there.
  • "offline"    → No live target — I'll render the rewritten prompt and you'll
                   re-run your tests externally.

Reply with one of the above.
```

If the user answers `database`, record `mode: self_hosted`, `self_hosted_flavor: database` on the run and continue to the database setup questions below. If they answer something else, route per the existing sub-flavor docs.

## Database setup questions (collect once at Setup Step 1.3d)

Ask all three in one message; do not pre-fetch anything until the user has answered. The questions are mandatory — the skill cannot read the prompt without them.

```
Database sub-flavor confirmed. To read (and optionally write) the live prompt,
I need three things:

1. Database type — which engine? (postgresql / mysql / mariadb / sqlite /
   mssql / mongodb / other — name it so I can pick the right client.)

2. Credentials — how should I connect? Preferred shapes, in order:
     • A connection-string env var already on this machine (e.g.,
       "use $DATABASE_URL", "use $PROD_PROMPTS_DSN"). I will NOT echo the
       value back; I'll pass it through to the client.
     • A connection string you paste once here (e.g.,
       "postgresql://user:pass@host:5432/dbname"). I will use it for this
       run only and will not log or persist it.
     • Field-by-field: host, port, database, user, password. Same handling
       as above.
   If your DB requires SSL / a CA cert / an SSH tunnel / an IAM token, tell
   me how you normally connect (psql command line, .pgpass file, ~/.my.cnf,
   etc.) and I'll match that.

3. Fetch query — the exact statement that returns the current prompt as a
   single value. Examples:
     • Postgres / MySQL: SELECT system_prompt FROM agents WHERE id = 42;
     • Postgres with bind: SELECT system_prompt FROM agents WHERE id = $1;
       (give me the parameter value too)
     • Mongo: db.agents.findOne({_id: "42"}, {system_prompt: 1})
   The query MUST return exactly one prompt string (or one row whose
   prompt column I can identify). If your schema stores the prompt in
   multiple chunks (header + body + footer), give me a query that
   concatenates them, or tell me how to assemble them and I'll do it.

4. (Optional) Write query — if you want me to land edits automatically,
   give me the statement that updates the prompt. Use a clear placeholder
   for the new prompt value — examples:
     • Postgres: UPDATE agents SET system_prompt = :new_prompt,
       updated_at = NOW() WHERE id = 42;
     • MySQL:    UPDATE agents SET system_prompt = :new_prompt
       WHERE id = 42;
     • Mongo:    db.agents.updateOne({_id: "42"},
       {$set: {system_prompt: :new_prompt}})
   If you skip this, I'll render the rewritten prompt each iteration and
   you'll update the DB yourself — the loop still works, you just unblock
   each iteration manually.
```

Record on the run:

- `db_type` — lowercased engine name (`postgresql`, `mysql`, `mariadb`, `sqlite`, `mssql`, `mongodb`, etc.).
- `db_connection` — connection string OR env-var name. Treat as a secret: never echo it back to the user, never include it in summaries, never write it to a file. When invoking a CLI client, pass it via env var or stdin rather than a positional arg that shows up in `ps`.
- `db_fetch_query` — the SELECT statement (or Mongo find equivalent).
- `db_fetch_bind_values` — list of parameter values for bind placeholders, if any.
- `db_write_query` — the UPDATE statement (or Mongo updateOne equivalent), or `null` if the user opted into render-only.
- `db_write_placeholder` — the placeholder token used in `db_write_query` (default `:new_prompt`; can be `?`, `$1`, etc. — match what the user wrote).
- `prompt_column` — when the fetch query returns multiple columns, which column holds the prompt. Ask once if it's not obvious from the query.

If credentials are clearly missing (e.g., the user pasted a connection string with `<password>` placeholder), pause and ask for the real value before continuing. Do not guess.

## Phase 1.3d — Fetch the live prompt

1. **Pick the client.** Run a quick `which` check via the Bash tool to confirm the right CLI is installed:
   - `postgresql` → `psql`
   - `mysql` / `mariadb` → `mysql`
   - `sqlite` → `sqlite3`
   - `mssql` → `sqlcmd` (or `mssql-cli`)
   - `mongodb` → `mongosh` (or `mongo` legacy)
   - other → ask the user how they normally connect.

   If the CLI is missing, surface the gap and ask the user to install it or to provide an alternative (e.g., a Python one-liner using their existing virtualenv). Do not silently fall through to render-only.

2. **Execute the fetch query.** Use the Bash tool with the credential passed through an env var, never as a literal in the command string. Examples (substitute the user's connection string into `DATABASE_URL` first via Bash, never inline in the visible command):

   - Postgres: `psql "$DATABASE_URL" -At -c "SELECT system_prompt FROM agents WHERE id = 42;"`
   - MySQL: `mysql --defaults-extra-file=<(printf '[client]\nuser=...\npassword=...\nhost=...\n') -B -N -e "SELECT system_prompt FROM agents WHERE id = 42;" dbname`
   - SQLite: `sqlite3 /path/to/db.sqlite "SELECT system_prompt FROM agents WHERE id = 42;"`
   - Mongo: `mongosh "$MONGO_URL" --quiet --eval 'JSON.stringify(db.agents.findOne({_id: "42"}, {system_prompt: 1}))'`

   Use the `-At` / `-B -N` / `--quiet` flags (or engine equivalent) to suppress headers, borders, and chrome — you want the raw prompt string, not a formatted table.

3. **Sanity-check the result.**
   - Empty result → fetch query matched zero rows. Pause and ask the user to verify the WHERE clause / bind values.
   - Multiple rows → the query returned more than one prompt. Pause and ask the user to narrow it (or tell you which row is the live agent's).
   - Single value but it's clearly not a prompt (numeric, 1-character, `null`, `<binary>`) → pause and ask what column actually holds the prompt.
   - Single value that looks like a prompt → record `current_prompt` on the run state and continue.

4. **Locate tool definitions if they are also in the DB.** Many setups put prompts in one table and tool definitions in another (or in JSON columns on the same row). Ask once:

   ```
   Do your tool definitions live in the same DB? If yes, give me the fetch
   query for them and (optionally) the write query, same shape as for the
   prompt. If your tools are defined in code (Python, Node, etc.) and only
   the prompt is in the DB, say "prompt only" and I'll skip tool edits.
   ```

   Record `db_tools_fetch_query` / `db_tools_write_query` on the run, or note `tools_in_code: true` and surface the gap during Diagnose if tool edits would otherwise be needed.

#### Phase 1.3 summary template (sub-flavor: `database`)

```
Self-hosted (database) agent: <agent_name> (id: <agent_id>)
  Provider tag: <assistant_provider>
  DB engine: <db_type>
  Connection: <env var name OR "inline (redacted)">
  Fetch query: <query, with bind params shown as ?, $1, etc.>
  Bind values: <list, or "none">
  System prompt: <N> chars (fetched from <table>.<column>)
  Tool definitions: <"in DB at <query>" | "in code (out of scope for DB edits)" | "none">
  Write query: <query OR "not provided — render-only mode">
  Dynamic-variable placeholders detected in prompt: <list of {{...}} or "none">

Note: This skill will SELECT the current prompt at the start of each
iteration and (if a write query is configured) UPDATE the prompt at the
end of each apply step. After each iteration you'll need to make sure
your live agent re-reads the prompt — either it queries the DB on every
request (no action needed) or it caches the prompt and needs a restart
(set redeploy_command at Setup Step 1.4). In render-only mode, I'll print
the new prompt and you'll update the DB yourself before re-validation.
```

## Setup Step 1.4 — Redeploy command (still applies)

The DB sub-flavor inherits the same Setup Step 1.4 hard gate as every other self-hosted live target. The redeploy command is independent of the DB write:

- If the live agent reads the prompt from the DB on **every request**, the prompt is "live" the moment the UPDATE commits — set `redeploy_command: "noop"` (or `"manual"` if you'd rather pause) and validation can start immediately.
- If the live agent **caches** the prompt at startup (or on a periodic refresh), the cached copy is stale until the agent restarts or the refresh fires. Collect the restart command the same way as every other self-hosted mode (e.g., `kubectl rollout restart deployment/agent`, `docker compose restart agent`).
- If the live agent has a "reload prompts" endpoint or signal (e.g., `curl -X POST .../admin/reload-prompts`), record that as `redeploy_command` — it's the right primitive here.

When in doubt, ask: "Does your agent re-read the prompt from the DB on every request, or does it cache it?" The answer dictates whether `redeploy_command` is `"noop"` or a real restart command.

## Phase 4.1e — Apply (DB write)

Run after Diagnose hands off the approved edit set. Two variants:

### Variant: write query provided

1. Render the new prompt as a single string (combine early-end-call edits + diagnose edits — same as every other mode).
2. Execute the user's `db_write_query` with the new prompt bound to `db_write_placeholder`. Pass the prompt via stdin or an env var, never as a positional CLI arg (multi-line prompts will break shell quoting and the prompt itself often contains characters that need escaping). Examples:

   - Postgres (psql, prompt via env var):
     ```
     NEW_PROMPT="$(cat /tmp/new_prompt.txt)" psql "$DATABASE_URL" \
       -v new_prompt="$NEW_PROMPT" \
       -c "UPDATE agents SET system_prompt = :'new_prompt', updated_at = NOW() WHERE id = 42;"
     ```
   - MySQL (stdin redirect, prompt as `LOAD_FILE` is unreliable — prefer Python / official driver if shell escaping gets hairy):
     ```
     mysql --defaults-extra-file=... dbname <<SQL
     UPDATE agents SET system_prompt = '<<<escaped prompt>>>' WHERE id = 42;
     SQL
     ```
   - Mongo (via mongosh eval, prompt via env var):
     ```
     NEW_PROMPT="$(cat /tmp/new_prompt.txt)" mongosh "$MONGO_URL" --quiet \
       --eval 'db.agents.updateOne({_id: "42"}, {$set: {system_prompt: process.env.NEW_PROMPT}})'
     ```

3. Capture exit code and any stderr. On non-zero exit, treat the same as a non-zero `redeploy_command` exit: surface the error, do NOT proceed to Sync, ask whether to retry / edit the query / abort.

4. If tool definitions are also in the DB and the iteration's edits include tool changes, run `db_tools_write_query` the same way — one row update per tool, or one bulk update if the user's schema supports it. If tools are in code and an iteration produced tool edits, surface as a hand-off (the skill cannot reach the user's tool code in this sub-flavor).

5. Run the recorded `redeploy_command` (Step APPLY.2) — same semantics as every other self-hosted mode. `"noop"` is treated like `"manual"` with auto-confirmation: skip the pause, proceed to Sync immediately.

### Variant: no write query (render-only)

Same behavior as websocket `offline`:

1. Render the new prompt to the user as a single fenced block, with a one-line preamble: `New prompt — paste into <table>.<column> for agent <id>, then restart the agent (or wait for the next refresh cycle) before I re-validate.`
2. In `auto_mode: true`, do NOT pause for the user to confirm the paste — surface the paste-and-restart hypothesis after the fact via the Eval no-change detector.
3. In `auto_mode: false`, pause and wait for `applied` / `done` / `updated` before proceeding to Sync.

## Phase 4.2 — Sync (re-fetch via DB)

Re-run `db_fetch_query` after the apply step. Compare the returned prompt to the prompt the skill intended to write:

- Match → proceed to Overfitting Gate.
- Mismatch on whitespace only → log and proceed (most DBs preserve whitespace; some clients normalize line endings — flag it but don't roll back).
- Mismatch on content (the DB still has the pre-edit prompt, or has a different prompt entirely) → drift. Roll back to Apply. Likely causes:
  - The write query targeted the wrong row (WHERE clause is off — bind values stale or hardcoded ID changed).
  - A trigger / view rewrote the value on insert.
  - The user has multiple environments (dev / staging / prod) and the fetch query and write query are pointing at different ones — pause and ask.
  - In render-only mode, the user hasn't updated the DB yet — re-render and wait.

For the tool side, re-run `db_tools_fetch_query` if tools were edited this iteration.

## What is NOT in scope for the database sub-flavor

- **Schema changes.** The skill writes to existing columns; it does not add columns, change types, or migrate data. If the user's schema can't hold the new prompt (e.g., a `VARCHAR(2000)` column overflowing), surface the gap — don't paper over it with truncation.
- **Multi-row / multi-tenant fan-out.** The skill edits exactly one prompt at a time (the one matched by `db_fetch_query`). If the user wants to roll an edit out across many rows, that's their migration to write — the skill can sanity-check the SQL on request but won't run a multi-row UPDATE without explicit confirmation.
- **Credential management.** The skill uses the credentials the user provides for the run, in-memory only. It does not write them to `.env` files, save them to its memory store, or share them across runs. Re-collect each new run.
- **Connection-pool / driver tuning.** If a query is slow or times out, surface it; do not retry with different connection parameters silently.
- **Destructive statements.** The write query MUST be an UPDATE / `updateOne` / equivalent — never a DELETE, DROP, TRUNCATE, or schema-altering statement. If the user provides one of those, pause and confirm explicitly before executing, even in auto mode. This is the same posture as the "destructive `redeploy_command`" check in [`overview.md`](overview.md) § "What this skill will NOT do".

## Security posture

- Credentials are passed via env vars or `.netrc`-style config files (`.pgpass`, `~/.my.cnf`), never as command-line arguments visible to `ps`.
- Credentials are never echoed back to the user, never written to summaries or reports, never persisted to disk by the skill.
- When the user pastes a connection string inline, treat it as a one-time secret: use it for the run, do not surface it in any subsequent user-facing output, do not store it in memory across iterations beyond what is needed to re-run the fetch and write queries.
- If a query result is logged for debugging (e.g., "fetched prompt is N chars"), log only the length / hash — never log the raw prompt to the user unless the user has asked to see it.

## Edge cases

- **Bind-placeholder mismatch.** The user writes `WHERE id = $1` in Postgres but doesn't give a bind value. Pause and ask. Don't try to inline-interpolate into the query.
- **JSON / JSONB columns.** The prompt may live inside a JSON column (e.g., `config->>'system_prompt'`). The fetch query should already extract the string; the write query needs `jsonb_set(...)` or equivalent. If the user provides the wrong shape, the sync re-fetch will catch it — roll back and ask.
- **Encrypted columns.** Some setups store prompts encrypted at rest. The user's fetch / write queries must include the decrypt / encrypt steps (e.g., `pgp_sym_decrypt` / `pgp_sym_encrypt`). The skill won't infer the encryption scheme — ask the user to make their queries do the right thing.
- **Versioning / audit tables.** If the user's schema has a separate `agent_prompt_versions` table that the live code reads from "latest version," the write query must insert a new version row (not UPDATE the latest). Ask the user how their versioning works at Setup; don't assume.
- **Read replicas.** If the fetch query hits a replica and the write query hits the primary, replication lag will cause Sync drift detection to false-positive. Add a short sleep (5–10s) between Apply and Sync when the user mentions replicas, or have them point both queries at the primary.
