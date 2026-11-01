"""The queue: posts from feeds wait here until the channel rules let them out.

Order is first in, first out. A news held by the 1 : 3 rule lets your own posts behind it
go first; quiet hours, the daily limit and the gap hold everything.
"""
from datetime import datetime, timezone

from telegram import Update
from telegram.ext import ContextTypes

from . import dm_posts
from . import drafts as D
from .hygiene import RATIO, blocker
from .i18n import tr
from .runtime import current, failed, is_admin, log, markup, under, name_of, notify_admins, publish, settings, state, why_failed
from .schedule import Post
from .state import Item

QUEUE_TTL = 72 * 3600          # news waiting longer than this is stale and leaves the queue
ANYWAY, SKIP = 'any', 'skip'


def item_post(item: Item) -> Post:
    return Post(item.post_id, datetime.fromtimestamp(item.created, timezone.utc), item.text,
                status='draft', label=item.label, source=item.name, photo_id=item.image or None, html=bool(item.html))


def find_post(post_id: str) -> Post | None:
    """A post by id: from posts.yaml, or one a feed brought in."""
    post = next((p for p in current['posts'] if p.id == post_id), None)
    if post is None:
        item = state.item_by_post(post_id)
        post = item_post(item) if item else None
    return post


def why_not_now(label: str, from_queue: bool = True, now: datetime | None = None):
    s = settings()
    return blocker(s.rules, now or datetime.now(timezone.utc), s.timezone, state.history(), label, from_queue)


def buttons(item_id: int) -> list[tuple[str, str]]:
    return [(tr('✅ Publish anyway'), f'q:{ANYWAY}:{item_id}'), (tr('🗑 Skip'), f'q:{SKIP}:{item_id}')]


def parse_button(data: str) -> tuple[str, int] | None:
    parts = (data or '').split(':')
    if len(parts) != 3 or parts[0] != 'q' or parts[1] not in (ANYWAY, SKIP) or not parts[2].isdigit():
        return None
    return parts[1], int(parts[2])


async def _retire(ctx, item_id: int, text: str) -> None:
    for admin, message_id in state.item_pop_msgs(item_id):
        try:
            await ctx.bot.edit_message_reply_markup(chat_id=admin, message_id=message_id, reply_markup=None)
            await ctx.bot.send_message(admin, text, disable_notification=True, **under(message_id))
        except Exception as e:
            log.info('could not update queue notice for %s: %s', admin, e)


async def tell_held(ctx, item: Item, reason: str, to: list[int] | None = None) -> None:
    """Admins learn once that a post is waiting, and may push it out anyway."""
    text = tr('⏸ «{name}» waits in the queue: {why}.', name=item.name, why=reason) + f'\n\n{item.text[:300]}'
    if to is None:
        sent = await notify_admins(ctx, text, buttons(item.id), quiet=True)
    else:
        sent = []
        for admin in to:
            try:
                m = await ctx.bot.send_message(admin, text, reply_markup=markup(buttons(item.id)))
                sent.append((admin, m.message_id))
            except Exception as e:
                log.info('could not tell %s about the queue: %s', admin, e)
    for admin, message_id in sent:
        state.item_add_msg(item.id, admin, message_id)
    state.item_notified(item.id)


async def publish_item(ctx, item: Item) -> bool:
    """Send one queued item to the channel. Only one caller wins, so it never goes out twice."""
    if not state.item_move(item.id, 'publishing', ('queued',)):
        return False
    post = item_post(item)
    draft = state.draft_for(post.id)
    ok = await publish(ctx, post, D.compose(post, draft.comment if draft else ''))
    state.item_move(item.id, 'published' if ok else 'queued', ('publishing',))
    if ok and draft:
        state.draft_move(draft.id, 'published', ('approved', 'publishing'))
    return ok


async def queue_tick(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Every minute: at most one post from the queue, when the rules allow."""
    now = datetime.now(timezone.utc)
    for item in state.items_in('queued'):
        if item.label == 'news' and now.timestamp() - item.created > QUEUE_TTL:
            if state.item_move(item.id, 'expired', ('queued',)):
                draft = state.draft_for(item.post_id)
                if draft:
                    state.draft_move(draft.id, 'expired', ('approved',))
                log.info('queued news %s expired after 72 h', item.post_id)
                await _retire(ctx, item.id, tr('⌛ Left the queue: older than 72 hours.'))
    for item in state.items_in('queued'):
        why = why_not_now(item.label, now=now)
        if why is None:
            if await publish_item(ctx, item):
                await _retire(ctx, item.id, tr('✅ Went out on its own — the rules allowed it.'))
            elif await failed(ctx, item.post_id, tr('«{name}» from the queue', name=item.name)):
                # Set aside so the posts behind it are not blocked forever.
                state.item_move(item.id, 'failed', ('queued',))
                draft = state.draft_for(item.post_id)
                if draft:
                    state.draft_move(draft.id, 'failed', ('approved',))
            return
        code, reason = why
        if code != RATIO:
            return                    # quiet hours, daily limit, gap: nothing goes now
        if not item.notified:
            await tell_held(ctx, item, reason)


async def on_queue_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE, action: str, item_id: int) -> None:
    q = update.callback_query
    if not await is_admin(ctx, q.from_user.id):
        await q.answer(tr('Only admins can do this.'), show_alert=True)
        return
    item = state.item(item_id)
    if item is None or item.status != 'queued':
        await q.answer(tr('Already decided.'))
        try:
            await q.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
        return
    who = name_of(q.from_user)
    if action == ANYWAY:
        await q.answer(tr('Publishing…'))
        if not await publish_item(ctx, item):
            await ctx.bot.send_message(q.from_user.id, tr('Could not publish «{id}»: {why}. It stays in the queue.',
                                                          id=item.name, why=why_failed(item.post_id)))
            return
        state.log_action('queue_forced', reason=item.post_id, by_admin=q.from_user.id)
        await _retire(ctx, item.id, tr('✅ Published anyway by {who}.', who=who))
    else:
        if not state.item_move(item.id, 'skipped', ('queued',)):
            await q.answer(tr('Already decided.'))
            return
        draft = state.draft_for(item.post_id)
        if draft:
            state.draft_move(draft.id, 'rejected', ('approved',), by=q.from_user.id)
        state.log_action('queue_skipped', reason=item.post_id, by_admin=q.from_user.id)
        await q.answer()
        await _retire(ctx, item.id, tr('🗑 Skipped by {who}.', who=who))


def queue_text(now: datetime | None = None) -> str:
    """What waits and why; then the next posts from posts.yaml."""
    now = now or datetime.now(timezone.utc)
    s = settings()
    lines = []
    queued = state.items_in('queued')
    first_free = True
    for n, item in enumerate(queued, 1):
        why = why_not_now(item.label, now=now)
        if why is None:
            status = tr('next, within a minute') if first_free else tr('after the posts above')
            first_free = False
        else:
            status = why[1]
        label = tr('news') if item.label == 'news' else tr('own')
        lines.append(f'{n}. «{item.name}» ({label}) — {status}\n   {item.text.splitlines()[0][:80]}')
    head = tr('Queue: {n}', n=len(queued)) if queued else tr('Queue: empty')
    rules = s.rules
    today = sum(1 for at, _ in state.history() if at.astimezone(s.tz).date() == now.astimezone(s.tz).date())
    info = [tr('Today in the channel: {n} of {limit}', n=today, limit=rules.daily_limit) if rules.daily_limit
            else tr('Today in the channel: {n}', n=today)]
    if rules.quiet:
        info.append(tr('Quiet hours: {start}–{end}', start=f'{rules.quiet[0]:%H:%M}', end=f'{rules.quiet[1]:%H:%M}'))
    if rules.news_in_a_row:
        info.append(tr('Rule 1 : {n}: at most {n} news in a row', n=rules.news_in_a_row))
    upcoming = [p for p in current['posts'] if p.at > now and not state.is_sent(p.id)][:5]
    sched = [f'• {D.when(p, s.timezone)} «{p.id}»' + (' ' + tr('(draft)') if p.status == 'draft' else '') for p in upcoming]
    out = [head] + lines + [''] + info
    if sched:
        out += ['', tr('Next from posts.yaml:')] + sched
    own = dm_posts.upcoming()
    if own:
        out += ['', tr('Scheduled from the private chat:')] + own
    return '\n'.join(out)


async def cmd_queue(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """What goes out and when. Admins, private chat."""
    if not await is_admin(ctx, update.effective_user.id):
        return
    await update.effective_message.reply_text(queue_text())
