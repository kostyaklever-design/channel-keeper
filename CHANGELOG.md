# Changelog

Newest first. Version format: MAJOR.MINOR.PATCH.

## [2.0.2] — 2026-11-01
### Added — documentation in Russian
- Every page in `docs/` now has a Russian twin (`AI.ru.md`, `COMMANDS.ru.md`, `CONFIG.ru.md`, `INBOX.ru.md`, `MODERATION.ru.md`, `POSTS.ru.md`, `PRIVACY.ru.md`, `SETTINGS.ru.md`, `SOURCES.ru.md`), with the buttons named as the Russian bot shows them. Each page links to its pair; the Russian README lists the Russian pages.
- A guard: every English page must have its Russian pair with the same number of sections, and every link and heading anchor on every page must exist.
### Fixed
- A few stale lines: «needs AI_API_KEY» (a key added in Telegram works too), «the default English settings» after a one-click deploy, and the owners' verdicts that the learning filter already uses.

## [2.0.1] — 2026-11-01
### Fixed — documentation
- SETTINGS, POSTS, AI, SOURCES no longer say the defaults are English: the ad label, «Read on …», the AI retelling language and the chat texts follow the bot's language. PRIVACY lists the stored language.

## [2.0.0] — 2026-11-01
The bot in Russian, part 4 of 4: Channel Keeper speaks English and Russian.
### Added
- What the chat and the channel read by default follows the bot's language too: the warning, ban, flood, first-minutes and probation texts, the captcha text and its «I'm human» button, the «Advertisement» label, «Read on …» under news, and the language of AI retellings. Your own values in `keeper.yaml` stay exactly as written.
- `language: auto | en | ru` in `keeper.yaml` (default auto); `examples/keeper.ru.yaml` sets `ru`.
- A guard: every text the bot sends through reply / send / answer / edit / notify must go through `tr()` — an English literal there fails the tests.
- Both READMEs say the bot is bilingual; the Russian README names the buttons as the Russian bot shows them.
### Checked
- The whole test suite was also run with every text forced to Russian: no text breaks (no missing or mismatched placeholders), only the English wording differs.

## [1.12.0] — 2026-11-01
The bot in Russian, part 3 of 4.
### Added
- In Russian now: moderation notices to the owners and the reasons in `/log` (link, spam word, flood, probation, profile), `/ban`, `/unban`, `/forget`, `/id`, Unban / Clear warning, reviews (Delete / Keep) and the learning filter, `/report`, `/sources` and feed errors, the AI (`/ai`, editing, retelling, its errors, the second opinion's «why»), and why a post could not be published.
- A person pressing a captcha or join-request button reads the answer in their own Telegram language, whatever the owners' language is; a newcomer asked in a private chat before joining gets their own language too.
### Changed
- Whether a failed post is the channel's problem (rights, no channel) is no longer told by the English words of the reason, so it works in any language.

## [1.11.0] — 2026-11-01
The bot in Russian, part 2 of 4.
### Added
- In Russian now: posts from the private chat (preview, pin, auto-delete, buttons, times, albums, timers), drafts (comments, expiry, `/drafts`), the queue and the channel rules (`/queue`, held and skipped posts, why a post waits), and the inbox (messages and suggested posts, Reply / Approve / Decline).

## [1.10.0] — 2026-11-01
The bot in Russian, part 1 of 4.
### Added
- The bot's own texts can be Russian. The language follows the owner's Telegram (Russian → Russian, anything else → English); `/lang ru`, `/lang en`, `/lang auto` change it; `language:` in `keeper.yaml` wins over both.
- The «Menu» button is set by the bot itself at start — no @BotFather step: the default menu in the owners' language and a Russian one for Russian-language Telegram. `/lang` is in it.
- In Russian already: `/setup` and the AI key, every button under post previews and drafts, the draft headers and outcomes, notifications and `/log` titles.
- `bot/i18n.py` + `bot/texts_ru.py`: the English text in the code is the key. A test fails when a text has no Russian line, when the Russian line uses other `{placeholders}`, or when a Russian line is left for a text the code no longer says.

## [1.9.6] — 2026-11-01
### Added
- **Deploy on Railway** in one click: a published Railway template (`railway.com/deploy/channel-keeper`) — paste the bot token, Railway creates the project and the `/data` volume. The button is in both READMEs and both install guides.
- The icon (`docs/icon.svg`, `docs/logo.png`) at the top of both READMEs.

## [1.9.5] — 2026-11-01
### Added
- The AI key can be added in Telegram: `/setup` ends with **🔑 Add AI key** (also `/ai key`). The bot deletes the message with the key at once, checks the key with one tiny request, and answers ✅ with the provider and model — or the provider's own words, and saves nothing. `/ai off` removes the key. `AI_API_KEY` in the server variables still wins.
- A key pasted into the private chat by mistake is deleted instead of becoming a post preview.
### Changed
- Russian README: buttons are named as the bot shows them (Publish now, Delete / Keep, Reply / Approve / Decline, ✨ Edit with AI).

## [1.9.4] — 2026-11-01
### Changed
- README screenshots: the AI's «Looks like spam» card with Delete / Keep added next to the captcha; the `/log` screenshot removed (hard to read). Member's name and id blurred.

## [1.9.3] — 2026-11-01
### Fixed
- Pressing «I'm human» made a person «known» at once, so the newcomer checks — the AI second opinion, the profile check and the learning filter — never saw anyone who passed the captcha. With the captcha on (the default) they did nothing, and live spammers, who press the button, went straight through. Now the button only proves a person; «known» comes with their first clean message, after those checks. People who passed the captcha before 1.9.3 stay known; `/forget <id>` puts someone back through the checks.

## [1.9.2] — 2026-11-01
### Added
- Two more screenshots in both READMEs: the captcha in a comment thread and a draft from `/ai` (member's name and avatar blurred).

## [1.9.1] — 2026-11-01
### Added
- Screenshots in both READMEs: a post preview and the same post in the channel, `/report`, `/sources`, `/queue`, `/log` (`docs/screenshots/`; members' names blurred).
- The docs guard also checks that every picture in the READMEs exists.

## [1.9.0] — 2026-11-01
The first public release.
### Added
- `README.ru.md` and `docs/INSTALL.ru.md` — the description and the installation in Russian.
- `docs/INSTALL.md` rewritten for a first-time installer: your own private copy (**Use this template**), Railway step by step, the admin rights table, the command menu for @BotFather, and «Something is wrong».
- `examples/keeper.ru.yaml` and `examples/sources.ru.yaml` — ready settings and feeds for a Russian-language channel.
- Guards: links and heading anchors in both READMEs and both install guides must exist; the examples must load.
### Changed
- The AI provider is told by the key: `sk-ant-…` is Anthropic, any other `sk-…` is OpenAI. `AI_PROVIDER` is no longer needed; set against the key, the bot stops at start and says which one to use.
- OpenAI needs no `AI_MODEL` either: `gpt-5-nano` by default.
- When the provider refuses the key, the bot shows the provider's own words instead of a general phrase. Quotes pasted around the key are dropped.

## [1.8.6] — 2026-11-01
A logic review of the whole bot by three independent reviewers; every fix has a test.
### Fixed — safety
- A forgotten **↩️ Reply** could send a later message (a time, a new post) from the channel to a stranger. Now only a reply to the bot's «Your answer» prompt goes out; anything else ends the wait.
- Waits in the private chat (comment, time, buttons, AI edit, reply, setup) never lapsed and piled up. Now one wait per person, replaced by the next prompt, lapsing after 10 minutes.
- `/ban` and `/unban` in a comment thread could hit the channel (the thread «replies» to the channel post). An explicit id always wins; the thread's post is never a target.
### Fixed — moderation
- Someone could stay read-only forever when removal after the captcha or giving rights back failed; now their rights are given back, and owners are told if even that fails.
- **Unban** and `/unban` make a person able to write again: a flood mute and an open captcha are lifted too. `/ban` and `/unban` retire old notifications and reset warnings.
- A forwarded album counted as several violations (instant ban); now one per album. A newcomer's album with a caption is not «pictures without words».
- Warnings older than 30 days are forgotten.
- Reviews nobody answers lapse after 24 hours. When two owners press different buttons, the first decision stands.
- The learning filter no longer learns from profile reviews or messages blocked for being sent as a channel (their text was not the problem).
### Fixed — publishing
- One post that kept failing blocked the whole queue forever. A post that fails 3 times for its own reason is set aside and owners are told why; a channel problem (rights, no channel) is reported at most once an hour and posts wait.
- After a restart nothing stays «publishing»: it is published if it went out, otherwise back where it was.
- Retelling or commenting an approved news draft took effect without a new approval; now it leaves the queue until approved again.
- A missed or skipped post tells owners the real reason instead of «the bot was offline».
- Long feed posts are shortened in the title, never cut through the link's HTML; comment and retelling length checks know about pictures.
- Feed entries still in the feed are not forgotten after 30 days (and no longer come back as new).
- A suggested post handled in the Telegram app closes instead of staying open in the inbox forever.
- «In 1 hour» counts real time, also across the clock change.
### Fixed — setup and memory
- With only CHANNEL_ID (or only GROUP_ID) set, `/setup` asks only for the other one.
- When ADMIN_IDS is set, an owner claimed earlier with `/setup` no longer lingers.
- `/forget` also frees an open captcha and makes the learning filter forget the person's texts at once.
- Finished posts, inbox items, drafts and reviews older than `keep_days` are deleted, not kept forever.
- AI requests are counted before sending (a request that times out may still be billed). The report shows token counts correctly. An empty value in `keeper.yaml` keeps the default instead of becoming the text «None».
### Changed
- `.gitattributes`: all text files use LF line endings on every computer; a test checks it.

## [1.8.5] — 2026-11-01
### Changed
- **✨ Retell** works for Google News too: from the headline alone the AI writes 2–3 short paragraphs — what the source reports (attributed to it), general background, why it matters — and is told never to invent details of the event. The preview says «written from the headline only — check it».

## [1.8.4] — 2026-11-01
### Fixed
- OpenAI: requests use `max_completion_tokens`; reasoning models (gpt-5…, o…) get the lowest reasoning effort and room to think — before, gpt-5 models refused the request, or a short answer came back empty.
- When the AI provider refuses a request, the owner sees its own reason (for example a wrong model name), not just the status code.

## [1.8.3] — 2026-11-01
### Added
- News from feeds end with a short «Read on dev.by →» (`read_more`) instead of a long address; new template field `{read}`.
- Posts from feeds go with the feed's picture when it gives one (YouTube, Habr, most blogs); if Telegram cannot fetch it, the post goes as text.
- **✨ Retell in my channel's words** on news drafts: the AI writes 2–3 sentences in its own words (`ai_language`) from the article — unique text instead of a bare link. Google News feeds have only headlines, so there it says so instead of inventing.
### Changed
- Posts from feeds are Telegram HTML; an admin's comment on them is escaped.

## [1.8.2] — 2026-11-01
### Fixed
- On Railway the bot could not start («attempt to write a readonly database») when the service was still set to build from the `Dockerfile`: the image ran as a separate user, and Railway's volume belongs to root. The image runs as root now, and if the memory folder is not writable the bot says exactly what to change instead of a bare traceback.

## [1.8.1] — 2026-11-01
### Fixed
- In a channel's discussion group people write in the comment thread under a post, but the captcha button, warnings and notes went to the group itself — invisible from the thread. A commenter got «read-only» with no button and was removed a minute later. Everything the bot says about a message now appears in the same thread.
- If the captcha button cannot be shown at all, the person's restriction is lifted instead of removing them for not pressing a button they never saw.

## [1.8.0] — 2026-11-01
### Added
- A learning spam filter: learns from the owners' **Delete / Keep** and from messages the rules removed; after 20 examples of each kind, a newcomer's message that looks like deleted spam goes to the owners — never deleted by the filter. Retrains after every verdict; progress in `/report`; `learning_filter` turns it off. Everything stays on the server.
### Fixed (found by an independent review of the code against the real Telegram API)
- A group message starting with a command («/x buy crypto https://…») skipped every check. Such messages are now moderated before any command runs.
- Service messages in the channel's inbox (suggested post approved, paid, refunded…) no longer reach owners as empty «messages to the channel».
- Answers written by any admin as the channel in the Telegram app are no longer brought back to the owners.
- Editing a channel post no longer restarts its «first minutes» window.
- A newcomer whose message is waiting for the owners' decision does not send the owners a new review with every message.
- An edited `/ban` or `/unban` does not run again; commands do not answer inside the channel's inbox chat.
- The AI second opinion waits at most 8 seconds (was 15): updates are handled one by one, so a slow provider held up the bot.
- `/setup` forgets the previous group's admin list and permissions when you switch groups.

## [1.7.0] — 2026-11-01
### Added
- Join requests: when the group approves new members, the bot sends the person a button in private; pressed in time → approved, not → declined (they may ask again). A link or spam word in the profile, or `join_requests: owners`, sends the request to the owners with **Approve / Decline**. Needs the optional «Add users» right.

## [1.6.0] — 2026-11-01
### Added
- Posts through the private chat can be a video, a GIF, or an album of up to 10 photos and videos; the album's parts are collected into one preview. Pin and auto-delete work for albums too (every part is deleted).

## [1.5.0] — 2026-11-01
### Added
- Messages to the channel (Telegram's channel direct messages) come to the owners' private chat with **↩️ Reply**: the owner's answer goes from the channel into that person's conversation. The bot never answers by itself.
- Suggested posts come with the offered price and **✅ Approve / ❌ Decline**; Telegram publishes an approved post. The bot never edits or deletes it.
- `/setup` and `/report` mention the inbox. Needs the optional «Manage direct messages» right in the channel.
### Note
- Built on Bot API 9.2 as documented; not yet tried on a live channel — the check is part of this version's live test.

## [1.4.0] — 2026-11-01
### Added
- Ad posts through the private chat: up to 3 link buttons under the post, the ad label as the first line (`ad_label`), pin for 24 h / 48 h / 7 days / until unpinned, auto-delete after 24 / 48 / 72 hours. Timers survive restarts.
- `/setup` tells which optional channel rights pin and auto-delete need.
### Changed
- `publish` returns the channel message id, so the bot can pin it and delete it later.

## [1.3.0] — 2026-11-01
### Added
- Newcomers' probation: until 2 real messages, pictures or videos without words, forwards, contacts, inline-bot buttons and stories are removed (`probation` in `keeper.yaml`). Members known before 1.3 are not affected.
- Profile check: a link or spam word in a newcomer's profile sends their message to owners with **Delete / Keep** — never an automatic ban (`profile_check`).
- Edited messages are checked: a message later edited into an ad is deleted with a warning.
- Owners' **Delete / Keep** verdicts are kept on the server with the message text, for a filter that learns from them later.
### Changed
- **Keep** now trusts the person fully: no probation, no more profile or AI checks.
### Fixed
- Editing a message you sent the bot in private no longer creates a second post (it would have, once edits are received).

## [1.2.0] — 2026-11-01
### Changed
- python-telegram-bot 21.6 → 22.8 (Telegram Bot API 7.10 → 10.0). Nothing new for users yet: this opens channel direct messages, suggested posts and the other Telegram features of 2025–2026 for the next versions.
- Replies use the new `reply_parameters`; link previews the new `link_preview_options` — the old parameters are deprecated in 22.x.
### Fixed
- A button under a notification older than 48 hours no longer fails: Telegram sends such a message without its text.
### Added
- A test builds the real application with every handler and fails on any deprecated library call.

## [1.1.2] — 2026-11-01
### Fixed
- Railway build failed after 1.1.1: seeing the new `Dockerfile`, Railway switched to building with Docker and rejected its `VOLUME` line. `railway.json` now pins Railway's own builder (as before), and the `Dockerfile` has no `VOLUME` — `docker run -v` works the same.

## [1.1.1] — 2026-11-01
### Fixed
- When a post cannot be published, the owner sees the reason in plain words with what to do (for example, the bot has no «Post messages» right in the channel), instead of «see the log».
### Changed
- The example `keeper.yaml` has quiet hours off and no gap between queued posts — for testing. Put back `"23:00-08:00"` and `30` after the test.

## [1.1.0] — 2026-11-01
### Added
- Optional AI with your own key (`AI_API_KEY`, Anthropic or OpenAI). Without a key nothing changes.
- A second opinion on comments: a newcomer's first message that passed the ordinary checks goes to the AI; if it looks like spam, owners get it with **Delete / Keep**. The AI never deletes by itself.
- The editor: `/ai <what you need>` → up to 3 drafts as previews (reads a linked page, sees your queue); **✨ Edit with AI** under any preview.
- `/report` and a weekly report every Monday: posts, the 1 : 3 balance, what was cleaned up, AI requests this month. Works without AI.
- `AI_MONTHLY_LIMIT` (300 requests a month by default) protects the bill.
- A guard test: the AI code cannot publish, send posts, ban, restrict or know the channel's id.

## [1.0.0] — 2026-11-01
Feature-complete: everything from 0.3–0.9, and it installs without looking up ids.
### Added
- `/setup`: the bot remembers channels and groups where it is made admin; pick yours with two buttons; it checks its rights and says what is missing. The first person to send `/setup` becomes the owner when `ADMIN_IDS` is empty.
- Only `BOT_TOKEN` is required now. `CHANNEL_ID`, `GROUP_ID`, `ADMIN_IDS` are optional; when set, they win over `/setup`.
- Install three ways: Railway, `Dockerfile` + `docker run`, `install.sh` for your own Debian/Ubuntu server (systemd service, token in a root-only file).
- `docs/PRIVACY.md`: what is stored, for how long, why these rights. `/forget <id>` deletes everything about a person or channel. `keep_days` (90) deletes old log lines.
- The bot tells owners when it loses admin rights in the channel or the group.

## [0.9.0] — 2026-11-01
### Added
- Posts through the private chat: send the bot text or one photo with a caption → a preview exactly as in the channel → **Publish now**, **In 1 hour**, **Tomorrow 10:00**, **Pick a time** (`18:30`, `05.11 10:15`), **Cancel**. Formatting is kept. No GitHub needed.
- Scheduled posts from the private chat show in `/queue`; a post missed while the bot was offline waits for **Publish now** instead of going out late.
- Only people in `ADMIN_IDS` can post this way.
### Changed
- `posts.yaml` stays for planning many posts at once.

## [0.8.0] — 2026-11-01
### Added
- Disguised spam is caught: look-alike letters from other alphabets (`kаzино`, `ка3ино`), letters split by spaces or dots (`к а з и н о`), invisible characters, fancy fonts; links like `т.mе/…` written in Cyrillic.
- Flood limit: more than 5 messages in 10 seconds → read-only for 10 minutes (`flood` in `keeper.yaml`). An album counts as one message.
- The first minutes after a post (`first_minutes`): only members the bot already knew may comment in a fresh post's thread. Off by default — the bot first has to learn your regulars.
- `/log 100`, `/log @name`, `/log <id>`; long logs are split into several messages.
### Changed
- Tests reload the running bot properly between tests (`tests/fresh.py`); before, a module could keep the previous test's memory.

## [0.7.1] — 2026-11-01
### Fixed
- Messages written «on behalf of a channel» skipped the captcha, and a ban for them hit Telegram's service account shared by all channels instead of the channel. Now the channel is the author: warnings count per channel, a ban bans that channel, **Unban** and `/unban -100…` lift it.
### Added
- `channel_messages` in `keeper.yaml`: `block` (default — such messages are deleted, a channel cannot pass the captcha) or `check` (ordinary spam checks).
### Changed
- Captcha time is 120 seconds by default instead of 60: on a slow or throttled connection people need time to even see the button.

## [0.7.0] — 2026-11-01
### Added
- Captcha for everyone except admins: newcomers on join, people who were in the group before on their first message. The person can only read until they press **I'm human**; only they can press it. Pressed — remembered forever. Not pressed in time — removed from the group, free to join again.
- `captcha` in `keeper.yaml`: on/off, seconds, the text and the button label in any language. **On by default.**
- Open captchas are kept in the database: a restart neither forgets them nor leaves anyone read-only forever.
- Without the right to restrict members the bot logs why and lets messages through to the ordinary spam checks.
- Tests on a fake Telegram: only that person can press, the press beats the time-out, admins and bots are never checked, removal happens once.

## [0.6.0] — 2026-11-01
### Added
- Feeds in `sources.yaml`: YouTube channel, any RSS/Atom feed, Google News by a search query, Google Alerts. Checked every 15 minutes.
- Each source: `own` or `news`, `auto` or `draft`, a post template, a daily cap. Other people's news always come as a draft with the title and the link only.
- A new source never dumps its old entries; the same news from two feeds comes once; entries older than 3 days are never posted.
- The queue and channel rules in `keeper.yaml` (`channel_rules`): quiet hours, daily limit, rule 1 : 3 (the 4th news in a row waits for your own post), gap between posts.
- **Publish anyway** and **Skip** for a post held by the rules; Publish now on a feed draft respects the rules too.
- `/sources` — feeds and their last check; `/queue` — what goes out and when (admins, private chat).
- Guards: every action the bot logs has a title in `/log`; every library the code imports is in `requirements.txt`.
### Changed
- New dependency: `feedparser`.
- The bot remembers whether each channel post was own or news, and whether a skipped old post really went out — for the daily limit and the 1 : 3 rule. Existing memory is upgraded on start.

## [0.5.0] — 2026-11-01
### Added
- Drafts: a post with `status: draft` goes to admins' private chats exactly as it will look, with **Publish now**, **Schedule**, **Add comment**, **Reject**. Nothing reaches the channel without a press.
- Add comment: reply with 1–2 lines, they go on top of the post, and a new preview must be approved again.
- One decision wins: the first press decides, other admins' copies update, double presses do nothing.
- A draft without an answer expires after 48 hours.
- `/drafts` — what is waiting (admins, private chat).
- Tests that run the draft flow on a fake Telegram: no publication without a press, one publication per draft, non-admins refused.
### Changed
- Logs are quiet: the scheduler no longer writes two lines every minute; only real events and errors remain.
- Shared parts of the bot moved to `bot/runtime.py`; each feature has its own module. Behaviour of moderation and scheduled posts is unchanged.

## [0.4.1] — 2026-11-01
### Fixed
- The warning and ban messages mention the person by a link to their account, so people without an @username are notified too.
- After a ban, the earlier warning notification loses its «Clear warning» button and says `→ banned`.
- When one admin presses Unban or Clear warning, the other admins' copies of that notification update and lose their buttons.

## [0.4.0] — 2026-11-01
### Added
- Admin notifications in a private chat: every warning and ban with who, why and the start of the message.
- Buttons under them: **Unban**, **Clear warning**, **OK**; only admins can press, and each works once.
- Quiet notification for every published post.
- `/log` — the last 20 actions of the bot (admins, private chat).
### Changed
- The bot's memory moved from `state.json` to SQLite (`/data/keeper.db`). The old file is imported on first start and kept as `state.json.migrated`; nothing is published twice.

## [0.3.0] — 2026-11-01
### Added
- `keeper.yaml`: timezone, spam words, warning time and the bot's messages in the chat, in any language. Optional — English defaults without it.
- Content from a private GitHub repository: `CONTENT_REPO`, `CONTENT_TOKEN`, `CONTENT_BRANCH`. Posts are re-read every 5 minutes; editing a post no longer needs a redeploy.
- The bot keeps the last good `posts.yaml` / `keeper.yaml` when a new edit is broken, and logs why.
- MIT license.
- Guards: no brand name in code or docs; no secret-looking strings (bot tokens, GitHub tokens, API keys) in any file.
### Changed
- The bot is now Channel Keeper: English documentation and messages, nothing tied to one channel.
- Spam words moved from the `SPAM_WORDS` variable to `keeper.yaml`; `POSTS_FILE` replaced by `CONTENT_DIR`.
- Images for posts are read through the same content source (local folder or GitHub).

## [0.2.0] — 2026-10-31
### Added
- `VERSION` file and `/version` command; the version is logged at startup.
- Documentation in `docs/`: commands, variables, posts, moderation.
- Documentation guards (`tests/test_docs.py`).
### Changed
- README trimmed to setup and links.

## [0.1.0] — 2026-10-31
### Added
- Group moderation: links, spam words and forwards from other channels removed; warning, then ban; `/ban`, `/unban`; join/leave messages hidden.
- Scheduled channel posts from `posts.yaml`, 30-minute window.
- `/id` command.
- `posts.yaml` check in GitHub Actions.
