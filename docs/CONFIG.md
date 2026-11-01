# Environment variables (Railway → service → Variables)

Only `BOT_TOKEN` is required: the channel, the group and the owners can be chosen in Telegram with `/setup`. If you set them here, the variables win. Everything else — timezone, spam words, the bot's words in chat — is in [keeper.yaml](SETTINGS.md).
Every variable the bot reads is listed below; the guard `tests/test_docs.py` checks this table against the code.

| Variable | Required | What it is | Example |
| --- | --- | --- | --- |
| `BOT_TOKEN` | yes | Bot token from @BotFather. Never share it. | `123456:ABC...` |
| `CHANNEL_ID` | no | Id of the channel. Empty — chosen with `/setup` | `-1001234567890` |
| `GROUP_ID` | no | Id of the discussion group. Empty — chosen with `/setup` | `-1009876543210` |
| `ADMIN_IDS` | no | Owners' Telegram user ids, comma-separated. Empty — the first person to send `/setup` becomes the owner | `123456789` |
| `DATA_DIR` | no | Folder for the bot's memory. Default `/data` — mount a Railway volume there | `/data` |
| `CONTENT_REPO` | no | Private GitHub repository with `posts.yaml`, `keeper.yaml` and images. Empty — files from this repository | `yourname/channel-content` |
| `CONTENT_TOKEN` | with `CONTENT_REPO` | Fine-grained GitHub token: only that repository, only **Contents: Read** | `github_pat_...` |
| `CONTENT_BRANCH` | no | Branch of the content repository. Default `main` | `main` |
| `AI_API_KEY` | no | Your key from Anthropic or OpenAI. Empty — no AI, the bot works as before. See [AI](AI.md) | `sk-ant-...` |
| `AI_PROVIDER` | no | `anthropic` or `openai`. Empty — told by the key (`sk-ant-…` = anthropic) | `openai` |
| `AI_MODEL` | no | Model name. Default: `claude-haiku-5-5` (anthropic), `gpt-5-nano` (openai) | `gpt-5-nano` |
| `AI_MONTHLY_LIMIT` | no | At most this many AI requests per calendar month (default 300) — protects your bill | `300` |
| `CONTENT_DIR` | no | Local folder with content when `CONTENT_REPO` is empty. Default — repository root | `.` |

## Content in a separate private repository (optional)
Keeps your content plan private even when the bot's code is public, and edits do not redeploy the bot.

1. GitHub → **New repository** → name e.g. `channel-content` → **Private** → Create.
2. Upload `posts.yaml`, `keeper.yaml` and the `posts` folder with images.
3. GitHub → your avatar → **Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token**.
   Repository access: **Only select repositories** → `channel-content`. Permissions → **Contents: Read-only**. Generate, copy.
4. Railway → Variables: `CONTENT_REPO` = `yourname/channel-content`, `CONTENT_TOKEN` = the token.
5. Within 5 minutes the bot reads content from there. The log says `content from github:...`.
