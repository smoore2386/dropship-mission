# Agent Communication Conventions

## Discord Tag Format
All agents prefix their messages with their role tag:

| Agent | Tag | Emoji |
|-------|-----|-------|
| CEO | [CEO] | 👔 |
| Marketing & Research | [Marketing] | 📈 |
| Engineering | [Engineering] | ⚙️ |
| Sales | [Sales] | 💰 |

## Single Bot Architecture
All agents run through one Discord bot. Tags identify the active agent context.
Splitting into separate bots is an option later if permissions/channels require it.

## Escalation Path
Sales/Marketing/Engineering → CEO → Owner (only for spend >$500, legal, bans)
