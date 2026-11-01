"""Posts through the bot's private chat: send text or one photo -> preview -> Publish now,
in an hour, tomorrow morning, a time you type, or cancel. No GitHub, no YAML.

Only people listed in ADMIN_IDS may post: an admin of the discussion group is not
automatically an admin of the channel. These posts are yours, like posts.yaml: they go out at
their time and are never held by the channel rules (but they count toward the daily limit).
"""
import json
import re
import time
from datetime import datetime, timedelta, timezone

from telegram import ForceReply, Update
from telegram.ext import ContextTypes

from .dm_rules import (AD, CANCEL, DELETE, DELETE_CYCLE, EDIT, LINKS, NOW, PICK, PIN, PIN_CYCLE, buttons, hours_label,
                       next_in, parse_links, parse_when, quick_time, scheduled_buttons, too_long, with_label)
from .runtime import (ALBUMS, FAILED, ai, cfg, end_wait, failed, log, markup, notify_admins, publish, send_post,
                      settings, state, under, wait_for, waited, why_failed)
from .schedule import GRACE, Post



def as_post(p) -> Post:
    """The post as it goes to the channel: the ad label on top when on, the link buttons under it."""
    links = tuple(tuple(x) for x in json.loads(p.links)) if p.links else ()
    media = tuple(tuple(x) for x in json.loads(p.media)) if p.media else ()
    return Post(f'dm:{p.id}', datetime.fromtimestamp(p.at or p.created, timezone.utc),
                with_label(p.text, settings().ad_label, bool(p.ad)), photo_id=p.photo_id, html=True, links=links,
                media=media)


def fmt(at: float | datetime) -> str:
    when = at if isinstance(at, datetime) else datetime.fromtimestamp(at, timezone.utc)
    return when.astimezone(settings().tz).strftime('%d.%m %H:%M')


# ---------- Telegram ----------
def owner(user_id: int) -> bool:
    return user_id in cfg.admin_ids


async def _under(ctx, p, text: str, buttons_=None) -> None:
    """Update the preview's buttons and say what happened under it."""
    if p.preview_id:
        try:
            await ctx.bot.edit_message_reply_markup(chat_id=p.admin_id, message_id=p.preview_id,
                                                    reply_markup=markup(buttons_) if buttons_ else None)
        except Exception:
            pass
    await ctx.bot.send_message(p.admin_id, text, disable_notification=True, **under(p.preview_id))


async def on_new_post(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    msg, user = update.effective_message, update.effective_user
    if not owner(user.id):
        return       # the bot never talks to members in private; only owners post
    item = media_of(msg)
    if getattr(msg, 'media_group_id', None) and item:
        await _collect(ctx, msg, user.id, item)        # an album arrives as several messages
        return
    if item:
        text, length = msg.caption_html or '', len(msg.caption or '')
    elif msg.text:
        text, length = msg.text_html, len(msg.text)
    else:
        await msg.reply_text('A post is text, a photo, a video, a GIF, or an album of photos and videos.')
        return
    problem = too_long(length, bool(item))
    if problem:
        await msg.reply_text(problem)
        return
    if item and item[0] == 'photo':
        await offer(ctx, user.id, text, item[1])
    else:
        await offer(ctx, user.id, text, media=json.dumps([item]) if item else '')


def media_of(msg) -> tuple[str, str] | None:
    """(kind, file_id) of the message's picture or video, the largest photo size."""
    if getattr(msg, 'photo', None):
        return 'photo', msg.photo[-1].file_id
    for kind in ('video', 'animation'):
        thing = getattr(msg, kind, None)
        if thing:
            return kind, thing.file_id
    return None


ALBUM_WAIT = 2.0       # seconds: Telegram sends an album's parts one by one, right after each other
ALBUM_MAX = 10


async def _collect(ctx, msg, owner_id: int, item) -> None:
    albums = ctx.bot_data.setdefault('albums', {})
    gid = msg.media_group_id
    first = gid not in albums
    album = albums.setdefault(gid, {'owner': owner_id, 'items': [], 'caption': '', 'length': 0})
    if item[0] == 'animation':
        album['bad'] = 'GIFs cannot be in an album — send the GIF on its own.'
    album['items'].append(item)
    if msg.caption:
        album['caption'], album['length'] = msg.caption_html, len(msg.caption)
    if first:
        ctx.job_queue.run_once(_album_done, ALBUM_WAIT, data=gid)


async def _album_done(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    album = ctx.bot_data.get('albums', {}).pop(ctx.job.data, None)
    if not album:
        return
    owner_id = album['owner']
    problem = album.get('bad') or (f'Up to {ALBUM_MAX} photos and videos in an album.'
                                   if len(album['items']) > ALBUM_MAX else too_long(album['length'], True))
    if problem:
        await ctx.bot.send_message(owner_id, problem)
        return
    await offer(ctx, owner_id, album['caption'], media=json.dumps(album['items']))


async def offer(ctx, owner_id: int, text_html: str, photo: str | None = None,
                note: str = '👀 Preview — exactly how it will look in the channel:', media: str = '') -> int:
    """A post waiting in the owner's private chat: preview + buttons. Nothing goes out without a press."""
    pid = state.dm_add(owner_id, text_html, photo, media)
    await ctx.bot.send_message(owner_id, note)
    await _show(ctx, state.dm(pid))
    return pid


async def _show(ctx, p) -> None:
    post = as_post(p)
    mid = await send_post(ctx, p.admin_id, post, post.text, buttons(p.id, ai.c.on, p))
    if mid:
        state.dm_set_preview(p.id, mid)


async def _refresh(ctx, post_id: int, what: str) -> None:
    """An option changed: the old preview loses its buttons, a new one shows the post as it is now."""
    p = state.dm(post_id)
    if p.preview_id:
        try:
            await ctx.bot.edit_message_reply_markup(chat_id=p.admin_id, message_id=p.preview_id, reply_markup=None)
        except Exception:
            pass
    await ctx.bot.send_message(p.admin_id, f'{what} — the updated preview:')
    await _show(ctx, p)


async def _publish(ctx, p, who_pressed: bool = True) -> bool:
    if not state.dm_move(p.id, 'publishing', ('new', 'scheduled', 'missed')):
        return False
    post = as_post(p)
    message_id = await publish(ctx, post, post.text)
    state.dm_move(p.id, 'published' if message_id else p.status, ('publishing',))
    if message_id:
        await _after_publish(ctx, p, message_id)
    return bool(message_id)


async def _after_publish(ctx, p, message_id: int) -> None:
    """Pin it and set its timers. A failure here never undoes the publication — the owner is told what to fix."""
    notes = []
    if p.pin_hours:
        try:
            await ctx.bot.pin_chat_message(cfg.channel_id, message_id, disable_notification=True)
            notes.append(f'📌 pinned ({hours_label(p.pin_hours)})')
            if p.pin_hours > 0:
                state.timer_add(message_id, 'unpin', time.time() + p.pin_hours * 3600, f'dm:{p.id}')
        except Exception as e:
            notes.append(f'⚠️ not pinned: the bot needs «Edit messages» in the channel ({e})')
    if p.delete_hours:
        for part in ALBUMS.pop(message_id, [message_id]):          # an album: every photo goes
            state.timer_add(part, 'delete', time.time() + p.delete_hours * 3600, f'dm:{p.id}')
        notes.append(f'⏱ goes away in {p.delete_hours} h (the bot needs «Delete messages» in the channel for that)')
    if notes:
        await ctx.bot.send_message(p.admin_id, ' · '.join(notes), disable_notification=True)


async def timers_tick(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Unpin and delete channel posts whose time has come."""
    for message_id, action, post_id in state.timers_due(time.time()):
        if not state.timer_done(message_id, action):
            continue
        try:
            if action == 'unpin':
                await ctx.bot.unpin_chat_message(cfg.channel_id, message_id)
            else:
                await ctx.bot.delete_message(cfg.channel_id, message_id)
            log.info('%s %s (post %s)', action, message_id, post_id)
        except Exception as e:
            log.warning('could not %s post %s: %s', action, post_id, e)
            await notify_admins(ctx, f'⚠️ Could not {action} post {post_id} in the channel: {e}. '
                                     f'Check the bot\'s rights there (Edit / Delete messages).')


async def on_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE, action: str, post_id: int) -> None:
    q = update.callback_query
    if not owner(q.from_user.id):
        await q.answer('Only the channel owners can do this.', show_alert=True)
        return
    p = state.dm(post_id)
    if p is None or p.status in ('published', 'cancelled', 'publishing'):
        await q.answer('Already done.')
        return
    now = datetime.now(settings().tz)
    if action == NOW:
        await q.answer('Publishing…')
        if await _publish(ctx, p):
            await _under(ctx, state.dm(post_id), '✅ Published.')
        else:
            await ctx.bot.send_message(q.from_user.id, f'Could not publish: {why_failed(f"dm:{post_id}")}. The post is still here.')
    elif action == CANCEL:
        state.dm_move(post_id, 'cancelled', ('new', 'scheduled', 'missed'))
        await q.answer()
        await _under(ctx, p, '🗑 Cancelled — nothing goes to the channel.')
    elif action == LINKS and is_album(p):
        await q.answer('Telegram does not allow buttons under an album. Send one photo or video for a post with buttons.',
                       show_alert=True)
    elif action == LINKS:
        wait_for(ctx, q.from_user.id, 'links', post_id)
        await q.answer()
        await ctx.bot.send_message(q.from_user.id, 'Buttons under the post, one per line (up to 3):\n'
                                                   'Buy now - https://example.com/shop\nSend «-» to remove them.',
                                   reply_markup=ForceReply(selective=True, input_field_placeholder='Text - https://…'))
    elif action in (PIN, DELETE):
        field, cycle = ('pin_hours', PIN_CYCLE) if action == PIN else ('delete_hours', DELETE_CYCLE)
        value = next_in(cycle, getattr(p, field))
        state.dm_set(post_id, **{field: value})
        await q.answer(f'{"Pin" if action == PIN else "Delete"}: {hours_label(value)}')
        await _refresh(ctx, post_id, f'{"📌 Pin" if action == PIN else "⏱ Delete"}: {hours_label(value)}')
    elif action == AD:
        on = not p.ad
        body = re.sub('<[^>]+>', '', with_label(p.text, settings().ad_label, on))
        problem = too_long(len(body), bool(p.photo_id or p.media)) if on else None
        if problem:
            await q.answer(problem, show_alert=True)
            return
        state.dm_set(post_id, ad=int(on))
        await q.answer()
        await _refresh(ctx, post_id, f'📣 Ad label {"on" if on else "off"}')
    elif action == EDIT:
        wait_for(ctx, q.from_user.id, 'ai_edit', post_id)
        await q.answer()
        await ctx.bot.send_message(q.from_user.id, 'What should the AI change? For example: shorter, add a question '
                                                   'at the end, in Dutch.',
                                   reply_markup=ForceReply(selective=True, input_field_placeholder='shorter'))
    elif action == PICK:
        wait_for(ctx, q.from_user.id, 'time', post_id)
        await q.answer()
        await ctx.bot.send_message(q.from_user.id, f'When? For example 18:30 or {now + timedelta(days=1):%d.%m} 09:00 '
                                                   f'({settings().timezone}).',
                                   reply_markup=ForceReply(selective=True, input_field_placeholder='18:30'))
    else:
        at = quick_time(action, now)
        await q.answer()
        await _schedule(ctx, p, at)


async def _schedule(ctx, p, at: datetime) -> None:
    if state.dm_move(p.id, 'scheduled', ('new', 'scheduled', 'missed'), at=at.timestamp()):
        log.info('dm post %s scheduled for %s', p.id, at)
        await _under(ctx, p, f'🗓 Goes out {fmt(at)}. It is in /queue; the buttons above still work.',
                     scheduled_buttons(p.id))


def is_album(p) -> bool:
    return bool(p.media) and len(json.loads(p.media)) > 1


def waiting_links(ctx, user_id: int) -> bool:
    return waited(ctx, user_id, 'links') is not None


async def on_links_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    msg, user = update.effective_message, update.effective_user
    post_id = waited(ctx, user.id, 'links')
    p = state.dm(post_id) if post_id else None
    if p is None or p.status not in ('new', 'scheduled', 'missed'):
        end_wait(ctx, user.id)
        await msg.reply_text('That post is already done — nothing changed.')
        return
    links = parse_links(msg.text or '')
    if isinstance(links, str):
        await msg.reply_text(links)
        return
    end_wait(ctx, user.id)
    state.dm_set(post_id, links=json.dumps(links, ensure_ascii=False) if links else '')
    await _refresh(ctx, post_id, f'🔗 {len(links)} button{"s" if len(links) != 1 else ""}')


def waiting_time(ctx, user_id: int) -> bool:
    return waited(ctx, user_id, 'time') is not None


async def on_time_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    msg, user = update.effective_message, update.effective_user
    post_id = waited(ctx, user.id, 'time')
    p = state.dm(post_id) if post_id else None
    if p is None or p.status not in ('new', 'scheduled', 'missed'):
        end_wait(ctx, user.id)
        await msg.reply_text('That post is already done — nothing changed.')
        return
    at = parse_when(msg.text or '', datetime.now(settings().tz))
    if isinstance(at, str):
        await msg.reply_text(at)
        return
    end_wait(ctx, user.id)
    await _schedule(ctx, p, at)


async def dm_tick(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Scheduled posts from the private chat whose time has come. Missed by more than 30 minutes
    (the bot was down) -> not sent late without asking: the owner decides."""
    now = datetime.now(timezone.utc).timestamp()
    for p in state.dm_in('scheduled'):
        if p.at is None or p.at > now:
            continue
        if now - p.at > GRACE.total_seconds():
            if state.dm_move(p.id, 'missed', ('scheduled',)):
                why = why_failed(f'dm:{p.id}') if f'dm:{p.id}' in FAILED else 'the bot was offline'
                await _under(ctx, p, f'⚠️ It was due {fmt(p.at)} and did not go out ({why}). Publish it now?',
                             scheduled_buttons(p.id))
            continue
        if await _publish(ctx, p):
            await _under(ctx, state.dm(p.id), '✅ Published on time.')
        elif await failed(ctx, f'dm:{p.id}', 'Your scheduled post'):
            if state.dm_move(p.id, 'missed', ('scheduled',)):
                await _under(ctx, p, f'⚠️ Not published: {why_failed(f"dm:{p.id}")}. Fix it and press Publish now.',
                             scheduled_buttons(p.id))


def upcoming(limit: int = 5) -> list[str]:
    return [f'• {fmt(p.at)} «{re.sub("<[^>]+>", "", p.text)[:40] or "photo"}» (from the private chat)'
            for p in state.dm_in('scheduled')[:limit]]
