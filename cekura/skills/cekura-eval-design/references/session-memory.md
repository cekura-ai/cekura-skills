# Session Memory Document

A session memory document is a file that captures the decisions behind a
multi-session eval project — eval strategy, mock-tool approach, profile
mappings — so a later session does not have to rediscover them.

**It needs somewhere durable to live, and only some clients have one.** In an
editor or a terminal, the user's working directory persists and the file is
worth having. In a hosted chat (the Cekura dashboard assistant, or anything
running in a per-conversation sandbox) the filesystem is discarded when the
conversation ends: a file written there is invisible to the user, unreadable
next session, and every update to it costs a round that produces nothing. In
that setting the conversation itself is the memory — put the decisions in your
reply, where the user can see them and the thread keeps them.

**Create the file only when both hold:** the user has a persistent working
directory, AND they have asked for session notes. Do not offer it unprompted —
an unasked question early in a session displaces the work the user actually
came for, and this one is not needed to do any of that work.

**When you do create it**, use this structure:

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

**Updating it:** batch the updates. Rewrite the file when a phase of work
finishes, not after each individual decision — a write between every tool call
is what turns a working session into a narrated one.

**In future sessions:** if the user says "continue from last session" or "pick
up where we left off", check for this document before re-deriving anything.
