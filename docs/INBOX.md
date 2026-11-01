# Messages to the channel and suggested posts

Since 2025 Telegram lets anyone write to a channel and suggest a post — free, or offering Stars. Both arrive in the channel's direct messages. The bot brings them to the owners' private chat, so you see them next to everything else.

## Turn it on
1. Channel → Edit → **Direct messages** → on (and a price, if you want one).
2. Channel → Administrators → the bot → also turn on **Manage direct messages**.
3. `/setup` shows ✅ or what is missing.

## What you get
- **✉️ A message to the channel** — with **↩️ Reply**. The bot asks «Your answer…»: **reply to that message** and the bot delivers your answer into that person's conversation, as the channel. Anything you write that is not a reply to it is never sent there — it is handled as usual (a new post, for example). You can also answer in the Telegram app as usual.
- **📝 A suggested post** — the text, who sent it and what they offer — with **✅ Approve** and **❌ Decline**. Telegram itself publishes an approved post and handles the payment.

## What the bot never does
- It never answers people by itself, with or without AI: only your own words go out. Automatic answers are a separate, optional connector.
- It never edits, pins on a timer or deletes a suggested post. A paid one must stay in the channel 24 hours untouched, or the owner is not paid — so the bot keeps its hands off.

Your own messages in that chat (written in the Telegram app) are not forwarded back to you. Messages to the channel and suggested posts are kept on your server for the buttons; `/forget` deletes a person's.
