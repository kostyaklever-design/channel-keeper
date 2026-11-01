# Install

[Русская версия](INSTALL.ru.md)

Three ways; each needs only the bot token from @BotFather. After any of them: make the bot an admin, send `/setup` ([steps 3–5 below](#after-any-way-admin-rights-setup-commands)).

## Railway
No server of your own, everything in the browser. Railway is paid by usage; see railway.com/pricing.

**In one click:** [![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/deploy/channel-keeper) → sign in → paste the token into `BOT_TOKEN` → **Deploy**. Railway creates the project and the `/data` volume by itself. Then go on with [the steps below](#after-any-way-admin-rights-setup-commands).
The bot then uses its default settings, in its language (English or Russian, from your Telegram). To change them (spam words, the bot's words in the chat, Russian texts from `examples/keeper.ru.yaml`), keep `keeper.yaml` in a small private repository of your own and point `CONTENT_REPO` to it ([CONFIG](CONFIG.md#content-in-a-separate-private-repository-optional)).

**By hand**, if you want your own copy of the code (to edit `posts.yaml` and `keeper.yaml` on GitHub):

**1. Your own copy of the code on GitHub** — private, because `posts.yaml` is your content plan.
- On this repository's page press **Use this template → Create a new repository**, pick **Private**, **Create repository**.
- No such button? Download the archive from **Releases**, then GitHub → **New repository** → **Private** → **Create** → **uploading an existing file** → drag in everything from the archive → **Commit changes**.

**2. A Railway project from that repository.**
Railway → **New Project → Deploy from GitHub repo** → allow access to that repository → pick it. The first deploy starts; it may fail without the token — that is expected.

**3. The token.**
Click the service → **Variables → New Variable** → name `BOT_TOKEN`, value — the token from @BotFather → **Add**.

**4. The bot's memory — required.**
Right-click the service on the project canvas (or press **Ctrl/⌘ K**) → **Attach Volume** → mount path **`/data`**. Without it the bot forgets everything on each deploy, including `/setup`.

**5. Deploy.**
Press **Deploy** (Railway shows it after changes). In **Deployments → View logs** you should see `Channel Keeper v… starting, not set up yet`. Go on with [the steps below](#after-any-way-admin-rights-setup-commands).

## Docker
```
docker build -t channel-keeper .
docker run -d --name channel-keeper --restart unless-stopped \
  -e BOT_TOKEN=123456:ABC... \
  -v channel-keeper-data:/data \
  channel-keeper
```
- The volume `channel-keeper-data` keeps the bot's memory between updates.
- Logs: `docker logs -f channel-keeper`.
- Update: `docker build -t channel-keeper .`, then `docker rm -f channel-keeper` and the same `docker run` — the memory stays in the volume.
- Your `posts.yaml`, `keeper.yaml`, `sources.yaml`: edit them in the folder before `docker build`, or keep them in a separate repository with `CONTENT_REPO` ([CONFIG](CONFIG.md)).

## Your own server
Debian or Ubuntu, with sudo.
```
unzip channel-keeper-*.zip -d channel-keeper && cd channel-keeper
sudo bash install.sh
```
The script installs Python, creates a system user `keeper`, puts the code in `/opt/channel-keeper`, asks for the token (hidden) and keeps it in `/etc/channel-keeper.env` readable only by root, and starts the service `channel-keeper`.
- Logs: `journalctl -u channel-keeper -f`.
- Update: unpack the new version and run `sudo bash install.sh` again — the token and the memory in `/var/lib/channel-keeper` stay.
- Settings: edit `/opt/channel-keeper/keeper.yaml` and the other content files; the bot re-reads them within 5 minutes.

## After any way: admin rights, /setup, commands

**3. Make the bot an admin.** Your channel must have a discussion group (Channel → Edit → **Discussion**).
- **Channel** → Administrators → **Add Admin** → find the bot → leave only **Post messages** on → Save.
- **Discussion group** → Administrators → **Add Admin** → the bot → only **Delete messages** and **Ban users** → Save.

Optional, only if you use these features:
| Feature | Where | Right |
|---|---|---|
| Pin ad posts, delete them on a timer | Channel | Edit messages, Delete messages |
| Messages and suggested posts sent to the channel | Channel | Manage direct messages |
| Captcha before joining (group with «Approve new members») | Group | Add users |

**4. `/setup`.** Open the bot in a private chat → **Start** → `/setup`. The first person to do it becomes the owner. Press your channel, then your group: the bot checks its rights and lists what is missing. Send `/setup` again any time to re-check.

**5. Language and the command menu.** Nothing to do: the bot sets its «Menu» button itself and speaks Russian when your Telegram is in Russian, English otherwise. Change it with `/lang ru`, `/lang en` or `/lang auto`.

**First post:** send the bot any text in the private chat → **✅ Publish now**.

**Next, if you want:**
- your settings and the bot's words in the chat — `keeper.yaml` ([SETTINGS](SETTINGS.md)); a Russian-language example is in `examples/keeper.ru.yaml`;
- your YouTube, blog and news — `sources.yaml` ([SOURCES](SOURCES.md));
- the AI — `/setup` → **🔑 Add AI key**, paste your OpenAI or Anthropic key ([AI](AI.md)).

## Something is wrong
| You see | Do |
|---|---|
| `Forbidden: bot is not a member of the channel chat` in the logs | Add the bot as an admin of the **channel**, not only of the group. |
| After each deploy the bot asks for `/setup` again | No volume at `/data` (Railway, step 4). |
| `Cannot write the bot's memory in /data` | The process may not write the folder. On Railway: service → **Settings → Build → Builder** = Railpack, then redeploy. |
| The bot is silent in the private chat | Only owners can post. `/id` shows your id; `ADMIN_IDS` must contain it, or nobody has sent `/setup` yet. |
| «The AI provider refused the key: …» | The provider's own words follow. Usually a key copied with a missing part, or a key without access to models. |
| A post waits in `/queue` | The reason is written next to it: quiet hours, the daily limit, the gap, or 3 news in a row. |
