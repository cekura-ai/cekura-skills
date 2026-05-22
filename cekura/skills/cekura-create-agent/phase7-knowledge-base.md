# Phase 7 — Knowledge Base

Upload any documents the agent references so Cekura can use them for evaluator generation.

---

> **Start:** Announce "Starting Phase 7 — Knowledge Base" before doing anything in this phase.

## 7a. Determine from code first

**If code is available**, look for signals that the agent uses a knowledge base:

- References to KB lookup functions, vector search calls, or document retrieval APIs
- File paths or URLs pointing to PDFs, FAQs, policy docs, or product guides
- RAG (retrieval-augmented generation) patterns — embedding lookups, similarity search
- Config variables naming knowledge base files or endpoints
- Comments or prompts mentioning "refer to the knowledge base", "check the FAQ", "based on the document"

Then confirm with the user:

> "I [found / didn't find] any knowledge base references in the code — [brief reason]. Does this agent use any KB documents like FAQs, policy docs, or product guides that I should upload?"

**If no code access**, ask directly:

> "Does your agent reference any knowledge base documents? (FAQs, policy docs, product guides)"

If no → skip to [Phase 8](phase8-dynamic-variables.md).

---

## 7b. Upload files

```bash
curl -X POST https://api.cekura.ai/test_framework/v2/aiagents/{id}/upload_knowledge_base/ \
  -H "X-CEKURA-API-KEY: $CEKURA_API_KEY" \
  -F "files=@faq.pdf" \
  -F "files=@product-guide.pdf"
```

Supported formats: PDF, text files, documents.

---

## Phase 7 Gate

**Confirm files are uploaded (or none needed).**

Announce: "Phase 7 complete." Then immediately begin [Phase 8 — Dynamic Variables](phase8-dynamic-variables.md) without waiting for the user.
