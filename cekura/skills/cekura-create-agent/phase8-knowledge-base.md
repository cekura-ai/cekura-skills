# Phase 8 — Knowledge Base

Upload any documents the agent references so Cekura can use them for evaluator generation and hallucination detection.

---

## 8a. Does the agent use knowledge base documents?

Ask: "Does your agent reference any knowledge base documents? (FAQs, product guides, policy docs)"

If no → skip to [Phase 9](phase9-dynamic-variables.md).

---

## 8b. Upload files

```bash
curl -X POST https://api.cekura.ai/test_framework/v2/aiagents/{id}/upload_knowledge_base/ \
  -H "X-CEKURA-API-KEY: $CEKURA_API_KEY" \
  -F "files=@faq.pdf" \
  -F "files=@product-guide.pdf"
```

Supported formats: PDF, text files, documents. Uploaded files appear in Agent Settings → Agent's Knowledge.

Or use `mcp__cekura__aiagents_upload_knowledge_base` if available in the session.

---

## 8c. Link to hallucination detection (optional)

After upload, note the file IDs from the response and link them to the hallucination metric:

```bash
curl -X PATCH https://api.cekura.ai/test_framework/v2/aiagents/{id}/ \
  -H "X-CEKURA-API-KEY: $CEKURA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"hallucination_metric_kb_files": [<file_id_1>, <file_id_2>]}'
```

---

## 8d. What KB files enable

- More accurate evaluator generation — Cekura knows what the agent should and shouldn't say
- Hallucination detection — agent responses compared against KB content
- Richer test scenarios that exercise knowledge retrieval

---

## Phase 8 Gate

**Confirm files are uploaded (or none needed). If linked to hallucination detection, confirm the PATCH succeeded.**

Move to [Phase 9 — Dynamic Variables](phase9-dynamic-variables.md).
