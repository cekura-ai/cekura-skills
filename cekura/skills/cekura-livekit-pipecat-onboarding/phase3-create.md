# Phase 3 — Create the agent (LiveKit / Pipecat)

> **Start:** Announce the step in plain words ("Creating your agent in Cekura") — never a phase number.

**This is the point of the whole flow: the agent is created before any secret exists, so no secret is ever typed into chat.** The runtime denies `aiagents_create` until this file has been read in full — the payload shapes and the two rules below (dispatch name is real; tracing stays off) are here and nowhere else.

## 3a. Create the agent with placeholder credentials

**This is the point of the whole flow: the agent is created before any secret exists, so no secret is ever typed into chat.** Use these exact values — the user reads them off the agent page, and their whole job is to be unmistakably not-a-real-key at a glance. An invented dummy (`abc123`, `test`) looks like a value somebody meant to set.

**LiveKit needs three placeholders** — API key, API secret, server URL:

```json
{
  "name": "<derived from the repo — see phase2; never asked>",
  "description": "<the COMPLETE system prompt — multi-line>",
  "project": <project_id>,
  "language": "<from the scan — never a guess>",
  "agent_speaks_first": <true | false | null — from the scan; null = auto-detect>,
  "provider": {
    "type": "livekit",
    "credentials": {
      "api_key": "CEKURA_PLACEHOLDER_REPLACE_ME",
      "config": {
        "api_secret": "CEKURA_PLACEHOLDER_REPLACE_ME",
        "url": "wss://REPLACE-ME.livekit.cloud",
        "agent_name": "<the REAL dispatch name from the repo — never a placeholder>",
        "tracing_enabled": false
      }
    },
    "chat_agent_details": { "type": "" }
  }
}
```

**Pipecat needs exactly one** — the API key. It has no `url` and no `api_secret`; do not invent either:

```json
{
  "name": "<derived from the repo — see phase2; never asked>",
  "description": "<the COMPLETE system prompt — multi-line>",
  "project": <project_id>,
  "language": "<from the scan — never a guess>",
  "agent_speaks_first": <true | false | null — from the scan; null = auto-detect>,
  "provider": {
    "type": "pipecat",
    "credentials": {
      "api_key": "CEKURA_PLACEHOLDER_REPLACE_ME",
      "config": {
        "pipecat_agent_name": "<the REAL agent name from pcc-deploy.toml — never a placeholder>",
        "tracing_enabled": false
      }
    },
    "chat_agent_details": { "type": "" }
  }
}
```

- **Never ask for the agent's name.** It is in the repo — repository name, project metadata, deploy manifest, or the dispatch name — and a name is trivially editable afterwards, so a derived one that is slightly off costs the user nothing while a question costs a turn. Say which one you used ("calling it Acme Support Bot, after the repo") and move on. Only ask if there is genuinely no repo to read (GitHub declined) AND the user never named it.
- **The dispatch agent name is an identifier, not a secret — never placeholder it.** It is public, it is in the repo, and it is what the provider matches the dispatch against; a dummy there produces an agent that looks configured and can never connect. Take it from the repo, or ask for it inline in a `<clarification>` (that ask is fine — it is not a credential).
- **`chat_agent_details: {"type": ""}` — send it, on both providers.** Without it a LiveKit agent is created with **LiveKit chat selected**: the platform seeds the chat runtime from the voice provider whenever that provider can also chat, and LiveKit can. Nobody asked for a chat agent, nothing is configured behind it, and the user opens the agent page to find a channel switched on that they never chose. An explicit empty type overrides the seed. Pipecat does not seed today, but send it there too — this flow configures voice and nothing else, and the payload should say so rather than depend on a platform table staying as it is.
- **`tracing_enabled: false` at create.** It only becomes `true` after the SDK is integrated AND the user confirms they finished the deploy steps — see [phase5-sdk-pr.md](phase5-sdk-pr.md). Set `true` early and every run waits on a webhook that never arrives.
- **Language: take it from the scan; ask only if the scan is genuinely silent, and then ask it ALONE.** STT/TTS config usually settles it (`language=`, a locale in the model name), and the prompt's own language is good evidence. Never bundle it with a name question — "What is the agent's name and primary language?" is two asks wearing one coat, and the name half should not have been asked at all.
- **`agent_speaks_first`** drives evaluator generation: `true` makes every generated evaluator wait for the agent's greeting (`first_message` empty); `false` has the testing agent open. `null` lets the platform decide from the description. Set it from the scan; never ask.
- The description still has to pass the acceptance check in [phase1-github.md](phase1-github.md) 1b, whether it came from the repo or a paste.


## 3a-bis. Start evaluator generation NOW, before you say anything about credentials

The moment `aiagents_create` returns, fire **`scenarios_generate_bg`** — the payload is in [phase4-evaluators-run.md](phase4-evaluators-run.md) 4a. **Fire it and move on; do not wait for it here.**

Generation takes two to three minutes and depends only on the agent's description — not on its credentials, which are still placeholders. Run it after the credential handover and the user sits watching an idle chat for three minutes. Run it before, and those three minutes happen while they are in the provider console fetching keys, which is time they were going to spend anyway. Same work, same order of results, none of the waiting.

Say nothing about it yet. The next message is the credential handover, and it must not arrive with a second topic attached.

## 3b. Hand over the link, say why, and say what a wrong value costs

Give them the agent page, name the exact fields, and ask them to confirm when they're done. All three parts matter — the link without the field names leaves them guessing, and the ask without the warning leaves a wrong key looking like a broken agent later.

> "Created — here's your agent: {dashboard_url}/agents/{agent_id}
> It has placeholder credentials in it right now. Open that page and replace the **API key**, **API secret** and **server URL** with the real ones from LiveKit Cloud → Settings → Keys.
> **I'm deliberately not asking you for them here** — a key pasted into a chat is a key in a transcript; the agent page writes it straight to encrypted storage instead.
> Tell me once they're in. Worth knowing: nothing validates these until a call is placed, so if any of them is wrong or mistyped, the runs simply won't connect — and that failure looks like a broken agent rather than a bad key."

Name the fields that actually apply: **three for LiveKit** (API key, API secret, server URL), **one for Pipecat** (API key — it has no URL and no secret). Never list a field the provider doesn't have.

Then ask for the confirmation as a real `<clarification>` — options `["Done — they're updated", "Not yet"]`. Prose does not pause the turn, so a prose "let me know when you're done" runs straight on into evaluator generation while the agent still holds placeholders.


## 3c. Proceed on their confirmation

**"Done" is what you act on.** Nothing reads the credentials back — they are write-only, so there is no check to run and no flag to inspect. Do not claim to have verified them, do not say "confirmed" or "validated", and do not re-ask. Say what is actually true and move on:

> "Great — I started generating evaluators while you were doing that. The first test call will be the real check on those credentials."

**Do not claim the evaluators are ready.** Someone who has done this before is back in under a minute, and generation takes two to three — so more often than not they are still being written. [phase4-evaluators-run.md](phase4-evaluators-run.md) 4a-bis handles that case; it needs you not to have promised otherwise.

**"Not yet"** — this is fallback **F3** in SKILL.md. Ask what they want: `["Done — they're updated now", "Generate evaluators anyway — I'll add the keys before the run", "Pause here"]`. *Generate anyway* → [phase4-evaluators-run.md](phase4-evaluators-run.md), and re-ask about the credentials before the run. *Pause* → exit to the closing summary ([phase6-close.md](phase6-close.md)) with "placeholder credentials" as the open item.

**The first run is the verification**, and that is the honest framing to give: if it fails to connect, a wrong or mistyped credential is the first thing to check ([phase4-evaluators-run.md](phase4-evaluators-run.md) 4d covers diagnosing it).


---

## Phase 3 Gate

`aiagents_create` succeeded, the user has the agent link, and they answered "Done" to the replacement question (or chose *Generate anyway* under F3). Then [phase4-evaluators-run.md](phase4-evaluators-run.md) — **observability variant: skip phase4 and go to [phase5-sdk-pr.md](phase5-sdk-pr.md)**.
