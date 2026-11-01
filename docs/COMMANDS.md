# Bot commands

[Русская версия](COMMANDS.ru.md)

Every command the bot knows is described here. The guard `tests/test_docs.py` checks this list against the code.

## /ban
Where: the discussion group. Who: admins.
Reply to a spammer's message with `/ban` — the bot bans the author and deletes the message.

## /unban
Where: the discussion group. Who: admins.
Reply to a message with `/unban`, or send `/unban 123456789` (a user id) or `/unban -100123456789` (a channel that wrote on its own behalf). Lifts the ban and resets warnings.

## /id
Where: anywhere. Who: everyone.
Shows the current chat id and your user id. Handy for `CHANNEL_ID`, `GROUP_ID` and `ADMIN_IDS`.

## /version
Where: anywhere. Who: everyone.
Shows which version of the bot is running.

## /lang
Where: a private chat with the bot. Who: owners.
The bot's language for the owners: `/lang ru`, `/lang en`, or `/lang auto` — the language of your Telegram (the default). `language:` in `keeper.yaml` wins over it. The command menu follows.

## /log
Where: a private chat with the bot. Who: admins.
What the bot did, with time and reason: warnings, bans, captcha, flood, published posts.
- `/log` — the last 20; `/log 100` — the last 100 (up to 100).
- `/log @name` or `/log 123456789` — only that person or channel (`/log -100…`).

## /drafts
Where: a private chat with the bot. Who: admins.
Drafts waiting for your decision or approved and waiting for their time. See [POSTS](POSTS.md#drafts).

## /sources
Where: a private chat with the bot. Who: admins.
Every feed from `sources.yaml`: type, own or news, auto or draft, when it was last checked, how many entries it brought in or skipped, and the error if the last check failed. See [SOURCES](SOURCES.md).

## /queue
Where: a private chat with the bot. Who: admins.
Posts from feeds waiting for the channel rules, in order, each with the reason it waits; how many posts went out today; the next posts from `posts.yaml`.

## /setup
Where: a private chat with the bot (and once in the group, if the bot does not list it). Who: owners; with no owners yet — the first person to send it becomes the owner.
Pick the channel and the discussion group with buttons; the bot checks its rights there and says what is missing. Send it again any time to check.

## /forget
Where: a private chat with the bot. Who: owners.
`/forget 123456789` — delete everything the bot keeps about that person or channel. See [PRIVACY](PRIVACY.md).

## /ai
Where: a private chat with the bot. Who: owners. Needs your AI key ([AI](AI.md)).
`/ai 3 short posts from https://…`, `/ai a post about our new feature: …`, `/ai what should we post tomorrow?` — the AI writes up to 3 drafts; each comes as a preview with the usual buttons. Nothing goes to the channel until you press.
`/ai key` — add or replace your AI key (the same as **🔑 Add AI key** in `/setup`); `/ai off` — remove it.

## /report
Where: a private chat with the bot. Who: owners.
The channel's week: posts (yours and others' news), the 1 : 3 balance, what the bot cleaned up, drafts waiting, AI requests this month. Also comes by itself every Monday morning.
