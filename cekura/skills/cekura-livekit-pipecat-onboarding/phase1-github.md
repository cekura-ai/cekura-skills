# Phase 1 — Check GitHub (LiveKit / Pipecat)

> **Start:** Announce the step in plain words ("Let me check whether GitHub is connected — your agent's config lives in its repo") — never a phase number; the numbering is internal navigation only.

Your provider is LiveKit or Pipecat, so nothing auto-imports: the system prompt, the agent's name, the dispatch name, the language and who speaks first all live in the user's repository. This phase decides whether you can read them or must ask for them. **No provider key, secret or URL is asked for in chat on either path** — those are created as placeholders in [phase3-create.md](phase3-create.md) and replaced by the user on the agent page.

## 1a. Check GitHub immediately

Check the connection before anything else. Do not announce a plan, do not ask for credentials, do not ask for the system prompt yet.

- **In the Cekura dashboard chat:** call **`github_connection_status`**. It takes no arguments and reports the connection fresh on every call, so it is also how you re-check later.
- **In a local session (Claude Code, Cursor, Codex) with the repo already on disk:** you have the code directly — skip this whole file and go to [phase2-scan.md](phase2-scan.md). There is nothing to connect.

**Not connected** — the tool's own result spells out the question to ask; ask exactly that, and nothing else in the same block:

> "Would you like to connect your organization's GitHub so Cekura can read your agent's details straight from its code?"
> Options: `["Yes, I'll connect it", "No — I'll provide the details myself"]`

**This is the user's choice, not yours.** Never answer it for them ("GitHub isn't connected, so I'll just collect the details"), never call it optional or "not required", and never put a second question — least of all the agent's name — in the same block. A question written as prose renders as a passing remark: the flow runs on without them, and the bottom-bar prompt they actually look at never appears.

**"Yes, I'll connect it"** — give them the address **on its own line** so it can be opened in a new tab, then ask the follow-up in the same reply:

```
https://<dashboard host>/settings/org/integrations
```

Take the host from the workspace line (`[Current workspace: … dashboard_url=…]`) — the only place it appears, and not always a `cekura.ai` one. **Never guess a host**: a guessed one is stripped out of your reply and the user gets a link-less sentence. No `dashboard_url` in the workspace line ⇒ name the page in words and drop the URL. Mention that connecting needs an org admin, and that they also pick which repositories to share.

Then the second `<clarification>`, alone — the flow always resumes on a claim, so it needs its own question rather than a guess about when they are back:

> "Have you connected GitHub yet?"
> Options: `["Yes, I've connected it", "Not yet — still working on it", "I'll paste the details instead"]`

- **Yes** → **call `github_connection_status` again** before believing them; their word is not evidence, the tool is. Three outcomes below.
- **Not yet** → say you'll wait and ask the same question again; do not start collecting fields in the meantime.
- **I'll paste the details instead** → the paste path in 1b.

Three outcomes on the re-check, three different replies:

| Re-check says | Say |
|---|---|
| Connected, repos listed | Name the repos you can see, then ask the scan question below before reading anything. |
| Connected, **no repos shared** | The App is installed but the repository picker is empty — Cekura sees nothing. Ask them to add repositories to the installation at the same settings page, then re-check again. Do NOT tell them to connect GitHub; they already did. |
| Still not connected | Say so plainly and offer the choice once more, or take the paste path in 1b. Never claim it worked. |

**Connected, with repos** (on the first call or the re-check) — skip the connect ask entirely; asking someone to connect what they already connected reads as not listening. Ask the scan question instead, alone, naming the repositories you can see:

> "Want me to read `<repo>` and pull your agent's details out of the code?"
> Options: `["Scan it", "No — I'll paste the details"]`

**Declined either question** — take the paste path in 1b. Then go straight to [phase3-create.md](phase3-create.md) with the same placeholder credentials. **Never re-offer GitHub in this conversation.** Asking twice reads as not listening.


## 1b. The paste path — when GitHub is declined, unshared or unavailable

You stay in this skill. Collect **only** what phase2's scan would have found, one question per turn, in this order, skipping anything the user already said:

1. **The complete system prompt.** Ask for it the one way that works:

   > "Paste your agent's **complete system prompt** — the actual prompt your bot runs with, however long. It lives wherever you configure the agent: your agent code (the string passed to your LLM) or your framework's config. Paste it here or attach the file."

   **Offer NO alternative to the complete prompt, in any wording** — no "or a short description", no "a sentence or two", no one-line example. The moment the question offers a lighter option, users take it, and a summary produces junk evaluators.

   **Hard acceptance check before you use it.** It fails if ANY of these hold: it is a summary rather than a prompt (a few sentences, under ~15 lines); reading it leaves obvious open questions (which flows? which rules? what happens on failure/escalation? which tools?); it describes the *business* ("handles support for an e-commerce store") rather than the *agent's instructions*. On failure, push back once, concretely — name 2–3 specific questions it leaves open — and re-ask. Do not create the agent with a summary. (The platform rejects short descriptions anyway.)

2. **The dispatch agent name** — LiveKit: the `agent_name=` the worker registers with; Pipecat: `agent_name` in `pcc-deploy.toml`. An identifier, not a secret; fine to ask inline. Blocking — the provider matches dispatches against it.

3. **Language**, only if the prompt's own language doesn't settle it. Ask it alone.

The agent's **display name** is not a question: derive it from the prompt's persona ("You are Alex, a support agent for Acme" → "Acme Support Agent") or from what the user already called it, and say which. **Who speaks first**: leave `agent_speaks_first` as `null` (auto-detect) rather than asking.

Then go to [phase3-create.md](phase3-create.md).

---

## Phase 1 Gate

**Either** the repo is checked out (or is the local working directory) and you are going to [phase2-scan.md](phase2-scan.md), **or** the paste path has produced an accepted system prompt and the dispatch name and you are going to [phase3-create.md](phase3-create.md). A GitHub question is asked at most once per conversation.
