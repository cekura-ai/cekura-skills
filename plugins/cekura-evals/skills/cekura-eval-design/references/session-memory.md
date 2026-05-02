# Session Memory Document

When working on a multi-session eval project, offer to create a **session memory document** for the user. This persistent file captures key decisions made during the session so future conversations can pick up where you left off.

**Ask early in the session:** "Would you like me to create a session memory doc? It logs key decisions (eval strategy, mock tool approach, test profile mappings, etc.) so future sessions don't have to rediscover this context."

**If yes, create a file** in the user's working directory (or wherever they prefer) with this structure:

```markdown
# [Project Name] — Eval Session Notes

## Key Decisions
- **Tool strategy:** [A/B/C — with rationale]
- **Mock tool approach:** [auto-fetch / manual / N/A]
- **Default personality:** [ID and name]
- **Default run mode:** [text / voice]
- **Folder structure:** [how scenarios are organized]

## Test Profiles Created
| Profile | ID | Key Fields | Used By |
|---------|----|-----------| --------|

## Scenarios Created
| Name | ID | Type | Status |
|------|----|----|--------|

## Mock Tool Mappings
[Summary of what data exists for which tools]

## Open Items
- [Things to do next session]

## Session Log
- [Date]: [What was done]
```

**Update throughout the session:** As decisions are made, scenarios created, or mock data configured, append to the relevant section. At the end of the session, summarize what was accomplished.

**In future sessions:** Read this file first to restore context. If the user says "continue from last session" or "pick up where we left off", check for this document.
