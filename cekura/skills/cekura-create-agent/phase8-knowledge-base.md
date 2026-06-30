# Phase 8 — Main Agent Knowledge Base

Upload any documents the main agent references so Cekura can use them for evaluator generation.

> **Auto-import providers (VAPI / Retell / ElevenLabs / Synthflow):** If you used `configure_from_provider: true` in Phase 5, skip this phase entirely — knowledge base files were imported automatically. Go directly to [Phase 9](phase9-dynamic-variables.md).

**Rule: if the main agent reads any documents during a conversation, upload them. No exceptions.**

The reason for uploading is so Cekura can generate better test scenarios — not for the main agent's runtime retrieval. The agent's retrieval mechanism (filesystem, vector DB, API, hardcoded) is completely irrelevant to this decision. Do not use the retrieval mechanism as a reason to skip. Do not reason about whether the files "belong" in Cekura's KB system. The only question is: does the agent read documents? If yes, upload them.

---

> **Start:** Announce "Starting Phase 8 — Main Agent Knowledge Base" before doing anything in this phase.

## 8a. Find documents from code

**If code is available**, search broadly — document paths are often not in the main code but in config:

**Check config files and environment first:**
- `.env`, `.env.example`, `.env.local` — look for variables containing file paths or directory names
- `config.py`, `settings.py`, `config.yaml`, `config.json` — any path-like values
- Environment variable names containing `PATH`, `DIR`, `DOCS`, `KB`, `FILES`, `DATA`
- Constants or variables like `DOCS_DIR`, `KB_PATH`, `DOCUMENTATION_PATH`

**Then check the code:**
- Where those config variables are used — what files or directories they point to
- File paths to PDFs, text files, markdown files, policy docs, FAQs, product guides
- Directories the main agent reads from (e.g. `docs/`, `kb/`, `data/`, `documentation/`)
- Filesystem tool calls (Read, Glob, Grep on document directories)
- Vector search / RAG / embedding lookups over document collections
- URLs or API calls fetching document content
- Hardcoded document content embedded in the prompt or config

**Resolve the actual paths** — if a config variable points to `./docs`, find what files are in that directory and upload those files.

**How the main agent reads them does not matter.** Filesystem reads, vector search, API calls, embedded content — all the same. Find the files, upload them.

Then confirm with the user:

> "I found [these documents / this docs/ directory] that the main agent references. I'll upload them to Cekura now."

Do not ask whether to skip. Upload and move on.

**If no code access**, ask:

> "Does your main agent reference any documents — FAQs, policy docs, product guides, or any files it reads during a conversation?"

Only skip if there are genuinely zero documents.

---

## 8b. Upload files via MCP

Use the MCP upload tool to upload all found documents. Upload the actual files — not summaries or descriptions of them.

Supported formats: PDF, text files, markdown, documents.

---

## Phase 8 Gate

**All documents the main agent references must be uploaded before proceeding.**

Announce: "Phase 8 complete." Then immediately begin [Phase 9 — Dynamic Variables](phase9-dynamic-variables.md) without waiting for the user.
