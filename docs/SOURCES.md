# Feeds — sources.yaml

The bot checks your feeds every 15 minutes and brings new entries into the channel: your YouTube videos and blog posts, news by a search query, Google Alerts, any RSS or Atom feed.
The file is optional. Edit it on GitHub (pencil icon) → **Commit**; the bot applies changes within 5 minutes. A mistake keeps the previous sources and turns the GitHub check red.

```yaml
sources:
  - id: my-youtube              # small letters, digits, - or _
    type: youtube
    channel: UCxxxxxxxxxxxxxxxxxxxxxx
    name: Our YouTube           # what you see in drafts and /sources

  - id: blog
    type: rss
    url: https://example.com/feed.xml
    mode: draft                 # ask me first

  - id: ai-news
    type: google_news
    query: "AI agents"          # what you would type into Google News
    lang: en                    # language of the news
    country: US
    per_day: 3                  # at most 3 drafts a day from this source

  - id: alerts
    type: google_alerts
    url: https://www.google.com/alerts/feeds/00000000000000000000/0000000000000000000
```

## Fields

| Field | Required | What it does |
|---|---|---|
| `id` | yes | Your name for the source. Changing it makes a new source. |
| `type` | yes | `youtube`, `rss`, `google_news` or `google_alerts`. |
| `channel` | youtube | The channel id, 24 characters starting with `UC` (see below). |
| `url` | rss, google_alerts | The feed address, starting with `https://`. |
| `query`, `lang`, `country` | google_news | Search words; language and country of the results (default `en`, `US`). |
| `label` | no | `own` — your content; `news` — other people's articles. Default: `own` for youtube and rss, `news` for Google News and Alerts. |
| `mode` | no | `auto` — straight to the queue; `draft` — a preview in your private chat first. Default: `auto` for own, and news is **always** `draft`. |
| `template` | no | How the post looks. Fields: `{title}`, `{link}` (the address), `{source}`, `{read}` (a short «Read on dev.by →» with the address hidden in it — wording from `read_more` in `keeper.yaml`). `{link}` or `{read}` is required. Default for own: title, empty line, link (Telegram shows the video or page card). For news: title, empty line, `{read}`. |
| `per_day` | no | At most this many entries a day from the source (1–50). Default: 10 for own, 3 for news. More are skipped. |
| `name` | no | How the source is called in messages. Default: the id. |

**Where to find a YouTube channel id:** YouTube → your channel → **About** (or the channel description) → **Share channel** → **Copy channel ID**. A handle like `@name` does not work: the feed needs the id.

**Where to find a Google Alerts feed:** google.com/alerts → create an alert → **Show options** → **Deliver to: RSS feed** → **Create alert** → the RSS icon next to it → copy the address.

## Pictures and retelling
- If the feed gives a picture for an entry (YouTube thumbnails, most blogs, Habr), the post goes with it. If Telegram cannot fetch the picture, the post goes as text.
- On a news draft, **✨ Retell in my channel's words** (needs `AI_API_KEY`): the AI reads the article and writes 2–3 sentences in its own words in `ai_language`; the post becomes title + retelling + «Read on …», and you get a new preview. Unique text, nothing copied. Google News gives only a headline in its feed: there the AI writes from the headline — what the source reports (attributed to it), general background and why it matters — and is told not to invent details of the event. The preview warns you to check it before publishing.

## What the bot promises
- **Nothing old is dumped into the channel.** When a source is new — or its address changes — everything already in its feed is marked as seen. Only entries that appear after that come.
- **Nothing twice.** The same news from two feeds (same link, or same title) is brought in once. Entries older than 3 days are never posted.
- **Other people's news only with your press.** News is never published by itself: you get a draft with the title, the link and room for your comment ([drafts](POSTS.md#drafts)). The bot never copies the text of someone else's article.
- **One broken feed does not stop the others.** The error shows in `/sources` and in the log.

## The queue and the channel rules
Posts from feeds go to the queue and leave it one at a time, when the channel rules allow. The rules live in `keeper.yaml` under `channel_rules` ([settings](SETTINGS.md#channel-rules)):

- **Quiet hours** — nothing from the queue at night.
- **Daily limit** — at most N posts a day in the channel, all kinds counted.
- **Rule 1 : 3** — at most 3 news from others in a row; the next news waits for your own post. The channel stays yours, not a news aggregator.
- **Gap** — at least N minutes between two posts from the queue.

When a news waits because of the 1 : 3 rule, you get one quiet message with **✅ Publish anyway** and **🗑 Skip**. If you do nothing, it goes out by itself after your next own post. News that waits more than 72 hours leaves the queue.

On a draft from a feed, **✅ Publish now** also respects the rules: if a rule holds the post, it goes to the queue and you get **Publish anyway** — breaking a rule always takes a second, deliberate press. **🗓 To queue** puts it in the queue.

Posts you write in `posts.yaml` are yours: they go out at their time and are never held, but they count toward the daily limit and break a run of news.

`/queue` shows what waits and why; `/sources` shows how each feed is doing.
