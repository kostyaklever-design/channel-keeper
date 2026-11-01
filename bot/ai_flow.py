"""The AI in Telegram: a second opinion on newcomers' comments, and an editor in the private chat.

Hard rule: the AI never acts on its own. It does not publish — what it writes becomes a preview
with buttons in the owner's private chat. It does not delete or ban — a doubtful comment comes to
the owners with «Delete / Keep», and the comment stays until someone presses. A test checks that
this module cannot reach the channel.
"""
import html
import re

import httpx
from telegram import Update
from telegram.ext import ContextTypes

from . import ai as A
from . import review
from .dm_posts import offer
from .runtime import ai, cfg, end_wait, log, settings, state, waited

SPAM_THRESHOLD = 0.7
MIN_LENGTH = 25            # «спасибо», «+», «👍» are not worth a request
URL = re.compile(r'https?://\S+')


# ---------- a second opinion on comments ----------
def worth_checking(text: str, user_id: int) -> bool:
    """Only first messages of people the bot does not know yet, and only real text: keeps the bill small."""
    return (ai.c.on and settings().ai_moderation and len((text or '').strip()) >= MIN_LENGTH
            and state.known_since(user_id) is None)


async def second_opinion(ctx, msg, user_id: int, name: str) -> bool:
    """True when the AI finds the comment doubtful: owners are asked, the comment stays for now
    and the person is not marked as known."""
    text = msg.text or msg.caption or ''
    try:
        # Short timeout: moderation must not stall the chat; a late answer = no second opinion this time.
        p, why = A.read_spam(await ai.ask(A.SPAM_SYSTEM, A.spam_prompt(text), max_tokens=60, timeout=8))
    except A.AIError as e:
        log.info('ai moderation skipped: %s', e)
        return False
    if p < SPAM_THRESHOLD:
        return False
    await review.ask_owners(ctx, msg, user_id, name, f'🤖 Looks like spam ({int(p * 100)}%: {why or "no reason given"}).',
                            'ai')
    state.log_action('ai_flag', user_id, name, why or f'{int(p * 100)}%', text)
    return True


# ---------- the editor in the private chat ----------
async def read_page(url: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True,
                                     headers={'User-Agent': 'ChannelKeeper (Telegram bot)'}) as client:
            r = await client.get(url)
    except httpx.HTTPError as e:
        raise A.AIError(f'Cannot open the link ({e.__class__.__name__}).') from e
    if r.status_code != 200 or 'html' not in r.headers.get('content-type', 'text/html'):
        raise A.AIError(f'Cannot read the link (answer {r.status_code}).')
    return A.page_text(r.text[:2_000_000])


async def cmd_ai(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/ai <what you want> — e.g. «/ai 3 posts from https://…», «/ai what to post tomorrow?». Owners only."""
    msg, user = update.effective_message, update.effective_user
    if user.id not in cfg.admin_ids:
        return
    request = ' '.join(ctx.args or []).strip()
    if not request:
        await msg.reply_text('Tell me what you need, for example:\n/ai 3 short posts from https://example.com/article\n'
                             '/ai a post about our new feature: …\n/ai what should we post tomorrow?')
        return
    if not ai.c.on:
        await msg.reply_text('AI is off. Add AI_API_KEY to the server variables — see docs/AI.md.')
        return
    from .channel_queue import queue_text       # what is planned: lets the AI answer «what to post tomorrow?»
    try:
        link = URL.search(request)
        material = await read_page(link.group(0)) if link else ''
        answer = await ai.ask(A.EDITOR_SYSTEM, A.editor_prompt(request, material, queue_text()), max_tokens=1500)
    except A.AIError as e:
        await msg.reply_text(str(e))
        return
    posts = A.split_posts(answer)
    if not posts:
        await msg.reply_text('The AI returned nothing usable. Try asking differently.')
        return
    await msg.reply_text(f'✨ {len(posts)} draft{"s" if len(posts) > 1 else ""} below. Nothing goes to the channel '
                         f'until you press a button; edit them with ✨ or write your own.')
    for text in posts:
        await offer(ctx, user.id, html.escape(text), note='✨ Draft from the AI:')


def waiting_edit(ctx, user_id: int) -> bool:
    return waited(ctx, user_id, 'ai_edit') is not None


async def on_edit_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """The answer to «What should the AI change?» -> a new preview; the old one stays as it was."""
    msg, user = update.effective_message, update.effective_user
    if not (msg.text or '').strip():
        await msg.reply_text('Write in words what to change — for example «shorter».')
        return
    post_id = waited(ctx, user.id, 'ai_edit')
    end_wait(ctx, user.id)
    p = state.dm(post_id) if post_id else None
    if p is None:
        await msg.reply_text('That post is gone — nothing changed.')
        return
    original = re.sub(r'<[^>]+>', '', p.text)
    try:
        answer = await ai.ask(A.EDITOR_SYSTEM, f'Rewrite this post. Change: {msg.text}\n\nPost:\n"""\n{html.unescape(original)}\n"""',
                              max_tokens=900)
    except A.AIError as e:
        await msg.reply_text(str(e))
        return
    posts = A.split_posts(answer, limit=1)
    if not posts:
        await msg.reply_text('The AI returned nothing usable.')
        return
    old = (' The old version is still scheduled — cancel it with 🗑 under it if you use this one.'
           if p.status == 'scheduled' else ' The old one is still above.')
    await offer(ctx, user.id, html.escape(posts[0]), p.photo_id, note=f'✨ New version.{old}', media=p.media)


# ---------- retelling a news item from a feed ----------
async def on_retell(update: Update, ctx: ContextTypes.DEFAULT_TYPE, draft_id: int) -> None:
    """«✨ Retell»: the AI writes 2–3 sentences in its own words from the article; the post becomes
    title + retelling + «Read on …». A new preview comes; nothing is published."""
    from .channel_queue import item_post
    from .draft_flow import retire, send_previews
    from .sources import read_link
    q = update.callback_query
    if q.from_user.id not in cfg.admin_ids:
        await q.answer('Only the owners can do this.', show_alert=True)
        return
    d = state.draft(draft_id)
    item = state.item_by_post(d.post_id) if d else None
    if item is None or d.status not in ('pending', 'approved'):
        await q.answer('This draft is already decided.')
        return
    if not ai.c.on:
        await q.answer('AI is off: add AI_API_KEY to the server variables (docs/AI.md).', show_alert=True)
        return
    material = item.material
    if not material and item.link and 'news.google.' not in item.link:
        try:
            material = (await read_page(item.link))[:8000]
        except A.AIError:
            material = ''
    title = html.unescape(re.sub(r'<[^>]+>', '', item.text.split('\n', 1)[0])).strip()   # stored as HTML: back to plain
    source = item.publisher or item.name
    if material:
        system, prompt, note = (A.RETELL_SYSTEM.format(language=settings().ai_language),
                                A.retell_prompt(title, material), '✨ Retold by the AI — the new preview is below.')
    else:
        # Google News gives only a headline: the AI reports it with attribution and adds general context,
        # and is told never to invent details of the event. The owner checks the preview before anything goes out.
        system, prompt, note = (A.HEADLINE_SYSTEM.format(language=settings().ai_language),
                                A.headline_prompt(title, source),
                                '✨ Written from the headline only (the feed has no article text). Check it before '
                                'publishing — the new preview is below.')
    await q.answer('Retelling…')
    try:
        answer = await ai.ask(system, prompt, max_tokens=500)
    except A.AIError as e:
        await ctx.bot.send_message(q.from_user.id, str(e))
        return
    retold = (A.split_posts(answer, limit=1) or [''])[0]
    retold = re.sub(r'\n{3,}', '\n\n', retold).strip()
    if not retold:
        await ctx.bot.send_message(q.from_user.id, 'The AI returned nothing usable — the draft is unchanged.')
        return
    read = read_link(item.link, source, settings().read_more)
    limit = 1024 if item.image else 4096
    room = limit - len(title) - len(re.sub(r'<[^>]+>', '', read)) - len(d.comment or '') - 8
    text = f'<b>{html.escape(title, quote=False)}</b>\n\n{html.escape(retold[:max(room, 100)], quote=False)}\n\n{read}'
    state.item_set_text(item.id, text)
    state.draft_comment(draft_id, d.comment)          # new text = new preview to approve; the 48 h clock restarts
    state.item_move(item.id, 'draft', ('queued',))   # was approved? not any more — out of the queue until approved
    await retire(ctx, draft_id, note)
    await send_previews(ctx, draft_id, item_post(state.item(item.id)), d.comment)

