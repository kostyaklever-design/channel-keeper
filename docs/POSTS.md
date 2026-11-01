# Scheduled posts

Every minute the bot publishes posts from `posts.yaml` whose time has come.
It re-reads the file every 5 minutes — from this repository or from `CONTENT_REPO` (see [CONFIG](CONFIG.md)).

## Post through the private chat (easiest)
Open the bot in Telegram and send it the post: text; a photo, a video or a GIF with a caption; or an album (up to 10 photos and videos — the caption goes on the first). Bold, italics and links stay as you wrote them.
The bot answers with a preview — exactly how it will look in the channel — and buttons:
- **✅ Publish now**
- **🕐 In 1 hour**, **🌅 Tomorrow 10:00**
- **🗓 Pick a time** — reply with `18:30` (today, or tomorrow if that time has passed), `05.11 10:15` or `05.11.2026 10:15`. Times are in `timezone` from `keeper.yaml`.
- **🗑 Cancel**

A scheduled post keeps **Publish now** and **Cancel** under its preview, and shows in `/queue`. If the bot was offline at that time and missed it by more than 30 minutes, it does not post late on its own: you get a message with **Publish now**.
Only people in `ADMIN_IDS` can post this way — an admin of the discussion group is not automatically an admin of the channel. These posts are yours: the channel rules never hold them, but they count toward the daily limit.
Albums: Telegram does not allow buttons under an album, so 🔗 Buttons works only for a single photo, video or GIF; GIFs cannot be in an album. Files and voice messages are not posts.

### Ad posts: buttons, label, pin, auto-delete
Under every preview there are four more buttons:
- **🔗 Buttons** — reply with up to 3 lines `Button text - https://link`; they appear under the post. `-` removes them.
- **📣 Ad label** — puts `ad_label` from `keeper.yaml` («Advertisement» by default; for a Russian channel `Реклама`) in bold as the first line. If the advertiser or an erid must be shown, write them in the text yourself — the bot does not file anything anywhere and does not promise that a post meets any law.
- **📌 Pin** — off → 24 h → 48 h → 7 days → until you unpin. Needs «Edit messages» for the bot in the channel; without it the post still goes out and you are told.
- **⏱ Delete** — off → 24 h → 48 h → 72 h (the 1/24, 2/48 formats). Never less than 24 hours. Needs «Delete messages» in the channel.

Each press shows the updated preview. Timers survive restarts.

## Add a post in posts.yaml (for planning many posts at once)
1. On GitHub open `posts.yaml` → pencil icon.
2. Add a block at the end of the `posts:` list (indent with spaces, as in the example):
   ```yaml
     - id: post-2-how-it-works
       at: 2026-11-03 10:00
       image: posts/how-it-works.png
       text: |
         Post text...
   ```
3. Upload the image to the `posts` folder (open the folder → **Add file → Upload files**).
4. **Commit changes.**
5. **Actions** tab: green check — fine. Red cross — a mistake in the file (date, repeated id, text length). Open it to see what is wrong.

## Drafts
Add `status: draft` to a post and it never goes to the channel by itself:

```yaml
  - id: news-ai-receptionists
    at: 2026-11-04 10:00
    status: draft
    text: |
      Post text...
```

1. Within 5 minutes every admin gets it in a private chat with the bot — exactly as it will look in the channel.
2. Under it four buttons:
   - **✅ Publish now** — goes out at once.
   - **🗓 Schedule** — goes out at `at` (at once if that time has passed).
   - **✏️ Add comment** — reply with 1–2 lines; they go on top of the post and you get a new preview to approve.
   - **🗑 Reject** — never published.
3. Only admins can press. The first press decides; other admins' copies update. A double press does nothing twice.
4. A draft nobody answers within 48 hours expires. To send it again, give it a new `id`.
5. `/drafts` lists what is waiting.

Drafts also come from feeds: news always, your own sources when they have `mode: draft`. For them the second button is **🗓 To queue** instead of **Schedule** — see [SOURCES](SOURCES.md).

## Rules
- Every post has its own `id`, never reused: that is how the bot remembers what it already sent.
- `status` is `scheduled` (default) or `draft`.
- Time is in the `timezone` at the top of `posts.yaml` (or from `keeper.yaml`), format `YYYY-MM-DD HH:MM`.
- With an image the text is up to 1024 characters, without — up to 4096 (Telegram limits).
- A post more than 30 minutes overdue is skipped, never sent late.
- A broken `posts.yaml` does not stop the bot: it keeps the last good list and logs the reason.
- The bot cannot edit a published post — edit it in Telegram by hand.
