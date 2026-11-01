# Moderation of the discussion group

The bot checks every new message in the group. Admins and the channel's own posts are never checked.

## What counts as a violation
- A link: `http(s)://`, `www.`, `t.me/`, `wa.me/`, `bit.ly/`, addresses on common domains (.com, .io, .ru, .xyz and others) and hidden links in text.
- A forward from another channel.
- A spam word from `keeper.yaml` (see [SETTINGS](SETTINGS.md)) — also when disguised: look-alike letters from other alphabets (`kаzино`, `ка3ино`), letters split by spaces or dots (`к а з и н о`), invisible characters inside a word, fancy fonts (`𝐜𝐚𝐬𝐢𝐧𝐨`).
- A disguised link such as `т.mе/…` written with Cyrillic letters.

## What the bot does
1. Deletes the message.
2. First violation — a warning in the chat that disappears after `warn_seconds`. The person is mentioned, so Telegram notifies them. The bot cannot write to them privately: Telegram allows that only after they press Start.
3. Second violation — ban. Warnings reset.
4. "X joined / X left" messages are deleted to keep the chat clean.

## Newcomers' probation
Until someone has written `probation.messages` real messages (2 by default; «+», «ok» and other messages shorter than `min_length` do not count), the bot removes what spammers send first and honest people rarely need on day one: pictures or videos without words, forwards, contacts, messages with buttons from inline bots, stories. Text is not limited. The person is told once. People the bot knew before 1.3 are not on probation; **✅ Keep** on a review ends it at once.

## Profile check
On a newcomer's first message the bot reads their profile description. A link or a spam word there is the signature of AI-written comments: the text is clean, the ad sits in the profile. The bot does **not** delete or ban for it — the message stays, and owners get it with **🗑 Delete / ✅ Keep**. Turn off with `profile_check: false`.

## Edited messages
A message later edited into a link or a spam word is treated like a new one: deleted, warning, then ban. The reason in `/log` says «added by editing».

## The learning filter
The bot learns what spam looks like **in your group**: from every **Delete / Keep** you press on a review, and from the start of messages the rules removed (as kept in `/log`). Once it has at least 20 examples of each kind, a newcomer's message that looks like what you deleted before (90%+) comes to you with **Delete / Keep** — it is never deleted by the filter itself. Each verdict teaches it right away. `/report` shows how far it is (`learning — 12/20 spam, 3/20 kept`). Ordinary chat messages are never stored, so «Keep» examples come only from your reviews — it learns slowly, and that is on purpose. Turn off with `learning_filter: false`.

## Owners' verdicts
Every **Delete / Keep** on a review (profile check or AI) is kept on your server with the message text — the material for a spam filter that learns from your own choices in a later version. Nothing leaves the server; `/forget` deletes a person's verdicts too.

## Flood
`flood.messages` messages within `flood.seconds` (5 in 10 seconds by default) — the last message is deleted and the person can only read for `flood.mute_minutes` (10). An album of photos counts as one message. Admins are never limited. It shows in `/log` and comes to admins as a quiet notification.

## The first minutes after a post
Spam in comments peaks in the first 3–5 minutes after a post. With `first_minutes: 5` in `keeper.yaml`, during the first 5 minutes of a new post only people the bot already knew **before** the post may comment under it. Others' comments there are deleted with a short note (once per post); after the window they write as usual, and elsewhere in the chat nothing changes.
The bot «knows» a person after they wrote a message that passed all the checks (pressing the captcha button only proves they are a person: their first real message still goes through the newcomer checks — profile, learning filter, AI). That is why the rule is **off by default**: turn it on after the bot has run for a week or so and has seen your regulars. Telegram does not let a bot close comments under one post — this is the closest a bot can do.

## Join requests
If the group has **Approve new members** on (Group → Edit → Group type → Approve new members), the check happens before someone is even in:
- `join_requests: captcha` (default) — the person gets a button in a private chat with the bot; pressed within 4 minutes → approved and remembered as a person (no second captcha in the group); not pressed → declined, they may ask again.
- A link or spam word in their profile, or `join_requests: owners` — owners get the request with **Approve / Decline**.
- If the bot cannot write to the person, owners get the request too.
The bot needs the **Add users** right in the group to approve requests. `off` leaves requests to you in the Telegram app.

## Captcha
On by default; turn it off with `enabled: false` in `keeper.yaml` ([settings](SETTINGS.md#captcha)). Everyone except admins proves once that they are a person:

- **Newcomers** — right when they join.
- **People who were in the group before** — on their first message after the bot started checking. Telegram does not give bots the member list, so this is the only moment the bot can check them.

What happens (in the comment thread under a post, or in the main chat — wherever the person wrote): the message (if any) is deleted, the person can only read, and the chat shows a mention with **✅ I'm human**. Only that person can press it.
- Pressed — they write as before, and the bot remembers them forever.
- Not pressed within `seconds` (120 by default) — removed from the group and the button message disappears. They may join again and try once more. It shows in `/log`.

Bots, admins and the channel's own posts are never checked. Captcha comes before the spam checks: a person who has not pressed yet cannot post links at all.

If the bot lacks the **Ban users** right, it cannot restrict anyone: it writes the reason to the log and lets messages through to the ordinary spam checks, instead of deleting them with no way to pass.

## Messages on behalf of a channel
A message written «as a channel» is the channel's, not a person's: warnings count per channel, and a ban bans the channel (`/unban -100…` or **Unban** lifts it). By default (`channel_messages: block`) such messages are deleted, because the captcha cannot check a channel. See [settings](SETTINGS.md#messages-on-behalf-of-a-channel).

## Admin notifications
Every warning and ban comes to each admin from `ADMIN_IDS` in a private chat with the bot:
who, why and the start of the deleted message.
- Under a ban — **Unban** (the person can join again, warnings reset).
- Under a warning — **Clear warning** (the next violation is a warning again, not a ban).
- **OK** — just hides the buttons. Buttons work once, so a double tap does nothing twice.
- When a warned person is banned, the old warning notification loses its button and says `→ banned`. When one admin presses a button, the other admins' copies update too.

Each published post comes as a quiet notification too. `/log` shows the last 20 actions.

**Important:** open the bot in Telegram and press **Start** once. Telegram lets a bot write only to people who started it;
until then the log says `admin ... has not started the bot`.

## What it does not do
- It cannot see or clean up existing members — Telegram does not give bots the member list.
- It cannot tell an honest customer's website from spam. A wrong ban is lifted with **Unban** in the notification or `/unban`.

## Rights the bot needs
In the group: admin with **Delete messages** and **Ban users**. In the channel: **Post messages**.
**Ban users** also covers the captcha: in Telegram the same right lets a bot restrict members to read-only. No extra right is needed.
