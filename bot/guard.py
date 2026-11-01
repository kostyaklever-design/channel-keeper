"""The first minutes after a post, and flooding.

Spam in comments peaks in the first 3–5 minutes after a post: bots watch channels and jump
into the fresh thread. With `first_minutes` on, during that window only people the bot already
knew before the post went out may comment there. Telegram does not let a bot close comments
under one post, so the bot deletes the rest and says why.

Flood: more than `flood.messages` messages within `flood.seconds` -> read-only for a while.
An album of photos counts as one message.
"""
import time
from collections import deque
from datetime import datetime, timezone

from telegram import ChatPermissions
from telegram.ext import ContextTypes

from .runtime import cfg, log, notify_admins, same_thread, settings, state
from .notify import action_text

FRESH = 'fresh_posts'      # bot_data: {thread message id: when the post arrived}
FLOOD = 'flood'            # bot_data: {user id: deque of times}
TOLD = 'told_too_soon'     # bot_data: {(user id, thread)} — say it once per post


async def _delete_later(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id, message_id = ctx.job.data
    try:
        await ctx.bot.delete_message(chat_id, message_id)
    except Exception:
        pass


async def say(ctx, key: str, user_id: int, name: str, msg=None) -> None:
    """A short note that disappears after warn_seconds — in the thread the person wrote in."""
    s = settings()
    try:
        note = await ctx.bot.send_message(cfg.group_id, s.html(key, user_id, name), parse_mode='HTML', **same_thread(msg))
        ctx.job_queue.run_once(_delete_later, s.warn_seconds, data=(cfg.group_id, note.message_id))
    except Exception as e:
        log.info('could not post the %s note: %s', key, e)


def remember_post(ctx, msg) -> None:
    """A channel post just appeared in the group: its comment thread is fresh."""
    fresh = ctx.bot_data.setdefault(FRESH, {})
    fresh[msg.message_id] = time.time()
    for thread, at in list(fresh.items()):          # keep only the last hour
        if time.time() - at > 3600:
            fresh.pop(thread, None)


def _thread(msg) -> int | None:
    if getattr(msg, 'message_thread_id', None):
        return msg.message_thread_id
    reply = getattr(msg, 'reply_to_message', None)
    return reply.message_id if reply else None


async def too_soon(ctx, msg, user_id: int, name: str) -> bool:
    """True when the message was deleted: a comment in a fresh thread by someone the bot did not know."""
    minutes = settings().first_minutes
    thread = _thread(msg)
    posted = ctx.bot_data.get(FRESH, {}).get(thread) if thread else None
    if not minutes or posted is None or time.time() - posted > minutes * 60:
        return False
    since = state.known_since(user_id)
    if since is not None and since < posted:
        return False
    try:
        await msg.delete()
    except Exception:
        return False
    told = ctx.bot_data.setdefault(TOLD, set())
    if len(told) > 5000:
        told.clear()                     # only «told once per post» — losing it after a while costs one extra note
    if (user_id, thread) not in told:
        told.add((user_id, thread))
        await say(ctx, 'first_minutes', user_id, name, msg)
        state.log_action('first_minutes', user_id, name, f'within {minutes} min of a post',
                         msg.text or msg.caption or '')
    return True


async def flood(ctx, msg, user_id: int, name: str) -> bool:
    """True when this message tipped the person over the flood limit (they are now read-only)."""
    f = settings().flood
    if not f.messages:
        return False
    group = getattr(msg, 'media_group_id', None)
    seen_groups = ctx.bot_data.setdefault('flood_albums', {})
    if group:
        if group in seen_groups:
            return False                             # the rest of an album: already counted
        seen_groups[group] = time.time()
        for g, at in list(seen_groups.items()):
            if time.time() - at > 600:
                seen_groups.pop(g, None)
    now = time.time()
    times = ctx.bot_data.setdefault(FLOOD, {}).setdefault(user_id, deque())
    times.append(now)
    while times and now - times[0] > f.seconds:
        times.popleft()
    if len(times) < f.messages:
        return False
    times.clear()
    until = datetime.fromtimestamp(now + f.mute_minutes * 60, timezone.utc)
    try:
        if user_id > 0:
            await ctx.bot.restrict_chat_member(cfg.group_id, user_id, ChatPermissions.no_permissions(), until_date=until)
    except Exception as e:
        log.error('flood: cannot restrict %s: %s', user_id, e)
        return False
    try:
        await msg.delete()
    except Exception:
        pass
    await say(ctx, 'flood', user_id, name, msg)
    reason = f'{f.messages} messages in {f.seconds} s — read-only for {f.mute_minutes} min'
    state.log_action('flood', user_id, name, reason, msg.text or msg.caption or '')
    await notify_admins(ctx, action_text('flood', name, user_id, reason), quiet=True)
    return True
