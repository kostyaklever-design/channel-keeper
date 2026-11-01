# What the bot stores, and why it needs its rights

The bot runs on **your** server or your Railway account. Nothing is sent to its authors. It talks only to Telegram, to the feeds in `sources.yaml` you add yourself, and — only if you set `AI_API_KEY` — to the AI provider you chose ([what exactly goes there](AI.md#what-goes-to-the-ai-provider)).

## Rights — and only these
| Where | Right | Why |
|---|---|---|
| Channel | Post messages | to publish your posts |
| Channel (optional) | Edit messages, Delete messages | only to pin ad posts and delete them on a timer |
| Channel (optional) | Manage direct messages | only to bring messages and suggested posts sent to the channel to you |
| Group (optional) | Add users | only to approve join requests after the captcha |
| Group | Delete messages | to remove spam |
| Group | Ban users | to ban spammers; the same right restricts newcomers to read-only for the captcha and the flood limit |

Telegram gives every admin bot the power to ban members, even with the other switches off. That is exactly why you run your own copy: you can read the code that holds this power. Keep a second human admin in the channel and the group.

## What is stored (in `keeper.db` on your disk)
| What | Why | How long |
|---|---|---|
| Ids and names of people the bot warned, banned, muted or removed, with the reason and the first 300 characters of the deleted message | `/log`, Unban buttons | `keep_days` (90 days by default), and at most the last 2000 lines |
| Warning counts per person | second violation = ban | until a ban, **Clear warning** or `/forget` |
| Who pressed «I'm human», and when the bot first saw someone write without trouble | not to ask twice; the first-minutes rule | until `/forget` |
| Messages waiting for an owner's Delete / Keep, and the owners' verdicts with the message text | the review buttons; the learning filter, which runs only on this server | until `/forget` |
| Messages people wrote to the channel and posts they suggested (name, id, text, offered price) | Reply, Approve, Decline | until `/forget` |
| Your posts and drafts, sent posts' ids, feed entries already seen | publish once, never twice | posts: kept; seen feed entries: 30 days |
| The chosen channel and group, owners | `/setup` | until changed |

It does not store ordinary messages of the chat or phone numbers. A newcomer's profile description is read once to look for a link and kept only in memory until a restart.

## Deleting someone's data
`/forget 123456789` (owners, private chat) deletes everything about that person or channel: warnings, captcha, log lines. A ban in Telegram itself is separate — `/unban` lifts it.

## Secrets
The bot token and `CONTENT_TOKEN` live only in the server's environment variables (Railway Variables, `/etc/channel-keeper.env` readable only by root, or `docker run -e`). Never in the repository: a check in `tests/` fails if something that looks like a token gets into the files.
