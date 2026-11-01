"""Feeds in the running bot: check every source each 15 minutes, bring new entries in once.

New source -> everything already in its feed is marked as seen, nothing is posted.
Same news in two feeds (same link or same title) -> brought in once.
own + auto -> straight to the queue; news, or mode: draft -> a draft in admins' private chats.
"""
import dataclasses
import time
from datetime import datetime, timezone

import feedparser
import httpx
from telegram import Update
from telegram.ext import ContextTypes

from . import sources as S
from .draft_flow import send_previews
from .runtime import NO_PREVIEW, current, is_admin, log, settings, state
from .channel_queue import item_post
from .schedule import CAPTION_LIMIT, TEXT_LIMIT

POLL_SECONDS = 900
SEEN_DAYS = 30                 # entries older than MAX_AGE are never posted, so a month of memory is plenty
MAX_BYTES = 5 * 1024 * 1024
HEADERS = {'User-Agent': 'ChannelKeeper (Telegram bot; RSS reader)'}


class FeedError(Exception):
    pass


async def fetch(url: str) -> bytes:
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True, headers=HEADERS) as client:
            r = await client.get(url)
    except httpx.HTTPError as e:
        raise FeedError(f'cannot reach the feed: {e.__class__.__name__}') from e
    if r.status_code != 200:
        raise FeedError(f'the feed answered {r.status_code}' + (' — check the address' if r.status_code == 404 else ''))
    if len(r.content) > MAX_BYTES:
        raise FeedError('the feed is larger than 5 MB')
    return r.content


def read_feed(data: bytes, source: S.Source) -> list[S.Entry]:
    parsed = feedparser.parse(data)
    found = S.entries(parsed, source)
    if not found and parsed.get('bozo'):
        raise FeedError('this address is not an RSS or Atom feed')
    return found


def _day_start(now: datetime) -> float:
    local = now.astimezone(settings().tz)
    return local.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()


async def bring_in(ctx, source: S.Source, entry: S.Entry) -> None:
    limit = CAPTION_LIMIT if entry.image else TEXT_LIMIT
    text = S.render(source, entry, settings().read_more)
    if len(text) > limit:
        # Too long (a long custom template): shorten the title, never cut through the HTML of the link.
        cut = max(20, len(entry.title) - (len(text) - limit) - 1)
        text = S.render(source, dataclasses.replace(entry, title=entry.title[:cut] + '…'), settings().read_more)
    pid = entry.post_id(source.id)
    status = 'draft' if source.mode == 'draft' else 'queued'
    item_id = state.item_add(pid, source.id, source.name, source.label, text, status, html=True, image=entry.image,
                             material=entry.material, link=entry.link, publisher=entry.source)
    state.log_action('feed_new', reason=f'{source.name}: {"draft" if status == "draft" else "queued"}', excerpt=text)
    log.info('feed %s: new %s %s', source.id, status, pid)
    if status == 'draft':
        draft_id = state.draft_create(pid)
        await send_previews(ctx, draft_id, item_post(state.item(item_id)), '')


async def check_source(ctx, source: S.Source, now: datetime, data: bytes | None = None) -> None:
    """One source, one check. `data` lets tests pass a feed without the network."""
    feed = state.feed(source.id)
    if feed is None:
        state.feed_primed(source.id, '')          # a row to keep the status in; not primed yet
        feed = state.feed(source.id)
    try:
        found = read_feed(data if data is not None else await fetch(source.url), source)
    except FeedError as e:
        state.feed_checked(source.id, str(e))
        log.warning('feed %s: %s', source.id, e)
        return
    if feed.signature != source.signature:
        for entry in found:
            state.mark_seen(entry.keys())
        state.feed_primed(source.id, source.signature)
        state.feed_checked(source.id)
        log.info('feed %s ready: %d existing entries marked as seen, only new ones will come', source.id, len(found))
        return
    new = skipped = 0
    since = _day_start(now)
    for entry in found:
        keys = entry.keys()
        if not keys:
            continue
        if state.is_seen(keys):
            state.mark_seen(keys)             # still in the feed: keep remembering it
            continue
        state.mark_seen(keys)
        if S.too_old(entry, now) or state.items_today(source.id, since) >= source.per_day \
                or state.item_by_post(entry.post_id(source.id)):
            skipped += 1
            continue
        await bring_in(ctx, source, entry)
        new += 1
    state.feed_checked(source.id, '', new, skipped)


async def poll(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    now = datetime.now(timezone.utc)
    for source in current['sources']:
        try:
            await check_source(ctx, source, now)
        except Exception as e:      # one broken source must not stop the others
            log.error('feed %s failed: %s', source.id, e)
    state.forget_seen(time.time() - SEEN_DAYS * 86400)


def sources_text(now: datetime | None = None) -> str:
    srcs = current['sources']
    if not srcs:
        return 'No sources. Add them to sources.yaml — see docs/SOURCES.md.'
    zone = settings().tz
    fmt = lambda ts: datetime.fromtimestamp(ts, timezone.utc).astimezone(zone).strftime('%d.%m %H:%M')
    out = [f'Sources: {len(srcs)}, checked every {POLL_SECONDS // 60} min']
    for s in srcs:
        f = state.feed(s.id)
        out.append(f'\n• {s.name} — {s.type}, {s.label}, {s.mode}')
        if f is None or not f.checked:
            out.append('  waiting for the first check')
        elif f.error:
            last = f'; last good {fmt(f.ok)}' if f.ok else ''
            out.append(f'  ⚠️ {fmt(f.checked)}: {f.error}{last}')
        elif f.signature != s.signature:
            out.append(f'  checked {fmt(f.checked)}, getting ready')
        else:
            out.append(f'  ✓ {fmt(f.checked)} · brought in {f.found} · skipped {f.skipped}')
    return '\n'.join(out)


async def cmd_sources(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Feeds and how their last check went. Admins, private chat."""
    if not await is_admin(ctx, update.effective_user.id):
        return
    await update.effective_message.reply_text(sources_text(), link_preview_options=NO_PREVIEW)
