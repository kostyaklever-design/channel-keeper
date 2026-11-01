# Channel settings — keeper.yaml

Settings that are not secrets. The file is optional: without it the bot uses English defaults.
Edit it on GitHub (pencil icon) → **Commit**. The bot applies changes within 5 minutes.
If the file has a mistake, the bot keeps the previous settings and writes the reason to the log; the GitHub check also turns red.

```yaml
timezone: Europe/Amsterdam   # default timezone for posts.yaml

spam_words:                  # messages containing any of these are removed
  - casino
  - crypto

warn_seconds: 60             # how long the warning stays in the chat (5–3600)

messages:                    # the bot's words in the chat, any language
  warn: "{name}, links and ads are not allowed here. Next time it is a ban."
  ban: "{name} was removed for repeated spam."

channel_rules:               # for posts from feeds, see SOURCES.md
  daily_limit: 6             # posts a day in the channel, all kinds; 0 = no limit
  quiet_hours: "23:00-08:00" # nothing from the queue at night; off = none. Quotes are required
  news_in_a_row: 3           # rule 1 : 3 — the 4th news waits for your own post; 0 = off
  gap_minutes: 30            # between two posts from the queue; 0 = off

captcha:                     # see MODERATION.md
  enabled: true              # everyone except admins presses «I'm human» once; false = off
  seconds: 120               # time to press (15–600), then the person is removed (may rejoin)
  text: "{name}, press the button within {seconds} seconds to write in this chat."
  button: "I'm human"

channel_messages: block      # messages «on behalf of a channel»: block or check, see MODERATION.md

flood:                       # off = no flood limit
  messages: 5                # this many messages ...
  seconds: 10                # ... within this time -> read-only
  mute_minutes: 10

first_minutes: 0             # 5 = in a new post's comments, only known members for the first 5 minutes; 0 = off

keep_days: 90                # log lines older than this are deleted (7–3650)

ai_moderation: true          # with AI_API_KEY: newcomers' first comments get a second opinion (see AI.md)

probation:                   # off = no probation
  messages: 2                # real messages before pictures without words, forwards, contacts are allowed
  min_length: 15             # shorter messages do not count

profile_check: true          # a link or spam word in a newcomer's profile -> owners decide (Delete / Keep)

ad_label: Advertisement      # the first line of a post marked as an ad (📣 under the preview)

join_requests: captcha       # when the group approves new members: captcha | owners | off (see MODERATION.md)

learning_filter: true        # learns from your Delete / Keep; only asks you, never deletes (see MODERATION.md)

read_more: "Read on {source} →"   # the short link under news from feeds; {source} = the site
ai_language: English         # the language of AI retellings
```

- `messages` also has `flood`, `first_minutes` and `probation` — the notes for those rules.
- `{name}` becomes a mention of the person (their @username or first name, linked to the account), so Telegram notifies them even without a username. No other placeholders.
- `spam_words` replaces the built-in list completely — copy the defaults you want to keep.
- Unknown settings are rejected, so a typo does not silently do nothing.

## Channel rules
`channel_rules` decide when posts from feeds leave the queue ([how the queue works](SOURCES.md#the-queue-and-the-channel-rules)). Without the block the values above apply. Times are in `timezone`. Posts you write in `posts.yaml` are never held by these rules, but they are counted.

## Captcha
On by default. It touches every member: newcomers when they join, old members on their first message — expect a wave of buttons in the first hours. `text` may use `{name}` (a mention that notifies the person) and `{seconds}`; any language works. How it behaves — [MODERATION](MODERATION.md#captcha).

## Messages on behalf of a channel
Telegram lets anyone write in a discussion group «as» a channel they own. Spammers love it: a channel cannot press the captcha button and has no personal account to ban.
- `block` (default) — every such message is deleted; the first time with a warning, the second time the channel is banned from the group. Your own channel and anonymous admins are never touched.
- `check` — such messages are checked like everyone else's: only links, forwards and spam words are removed. Use it if honest bloggers comment as their channels.
