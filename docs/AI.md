# AI (optional)

Without a key the bot works exactly as before. With your own key from Anthropic or OpenAI it gets two helpers.
**The AI never acts on its own.** It does not publish: everything it writes is a preview in your private chat, and only your press sends it. It does not delete or ban: a doubtful comment comes to you with **Delete / Keep**, and stays in the chat until you decide. A test in `tests/test_ai.py` fails if the AI code ever gets access to publishing, banning or the channel.

## Turn it on
1. Get a key: console.anthropic.com → **API Keys** (or platform.openai.com → **API keys**).
2. Server variable `AI_API_KEY` = the key. That is all: the bot tells the provider by the key (`sk-ant-…` is Anthropic, any other `sk-…` is OpenAI) and takes its cheapest model — `claude-haiku-5-5` or `gpt-5-nano`. Another model: `AI_MODEL`. If the key is refused, the bot shows the provider's own words.
3. Optional: `AI_MONTHLY_LIMIT` — requests per month, 300 by default. When it is reached, AI features pause until the next month; everything else keeps working.

## A second opinion on comments
The first message of a person the bot does not know yet, if it is longer than a few words and passed the ordinary checks, goes to the AI. If the AI thinks it is spam — a job offer «message me», crypto, a generic AI-written comment promoting someone — you get it with **🗑 Delete** and **✅ Keep**. **Keep** also tells the bot this person is fine; it will not ask about them again. Turn this off with `ai_moderation: false` in `keeper.yaml`.
Cost: one short request per newcomer's first message, not per message.

## The editor
- `/ai <what you need>` — up to 3 drafts as previews. With a link, the AI reads the page and uses only what is written there; with «what to post tomorrow?» it sees your queue.
- **✨ Edit with AI** under any preview — reply with what to change («shorter», «add a question at the end», «in Dutch»): a new preview comes, the old one stays.

## Retelling news
**✨ Retell in my channel's words** under a news draft from a feed: 2–3 sentences in `ai_language` (from `keeper.yaml`), only facts from the article, then a new preview. For Google News, whose feed has only the headline, the AI attributes the news to its source, adds general background, and must not invent details; the preview says so.

## What goes to the AI provider
Only: the text of newcomers' first messages that are checked, your `/ai` requests with the text of the page you linked and the list of planned posts (`/queue`), the posts you ask to edit, and the articles you ask to retell. Not the member list, not ids, not other messages. The provider's own terms apply to that text.
