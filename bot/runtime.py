"""What every part of the running bot shares: settings, memory, content and the ways it talks to admins.

Feature modules (moderation, drafts, feeds…) import from here instead of from
main.py, so main.py only wires handlers together and no feature imports another.
"""
import logging
import time

from telegram import (InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, InputMediaVideo, LinkPreviewOptions,
                      ReplyParameters)
from telegram.error import BadRequest, Forbidden
from telegram.ext import ContextTypes, filters

from .ai import AI
from .config import AIConfig, Config
from .content import ContentError, ContentSource
from .notify import action_text
from .schedule import Post, parse_posts
from .settings import Settings, parse_settings
from .sources import parse_sources
from .state import State

logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', level=logging.INFO)
logging.getLogger('httpx').setLevel(logging.WARNING)
# The scheduler logs every run of every job at INFO — two lines a minute of noise that hide real events.
logging.getLogger('apscheduler').setLevel(logging.WARNING)
log = logging.getLogger('channel-keeper')

cfg = Config.from_env()
state = State(cfg.data_dir)
content = ContentSource(cfg.content_repo, cfg.content_token, cfg.content_branch, cfg.content_dir)
ai = AI(AIConfig.from_env(), state)

# Choices made with /setup fill what the environment left empty. Variables always win:
# whoever set CHANNEL_ID in Railway meant it.
FROM_ENV = {'channel': cfg.channel_id is not None, 'group': cfg.group_id is not None}
if cfg.channel_id is None and state.get('channel_id'):
    cfg.channel_id = int(state.get('channel_id'))
if cfg.group_id is None and state.get('group_id'):
    cfg.group_id = int(state.get('group_id'))
if not cfg.admin_ids:   # ADMIN_IDS, when set, is the whole list: an owner claimed earlier does not linger
    cfg.admin_ids |= {int(x) for x in (state.get('owners') or '').split(',') if x}

# Messages from the discussion group. Built once at start; /setup adds the group it picks.
GROUP = filters.Chat(chat_id=cfg.group_id) if cfg.group_id else filters.Chat(chat_id=[], allow_empty=False)


def configured() -> bool:
    return cfg.channel_id is not None and cfg.group_id is not None


def save_setup(channel_id: int, group_id: int) -> None:
    if cfg.group_id and cfg.group_id != group_id:
        GROUP.remove_chat_ids(cfg.group_id)
    cfg.channel_id, cfg.group_id = channel_id, group_id
    state.put('channel_id', str(channel_id))
    state.put('group_id', str(group_id))
    GROUP.add_chat_ids(group_id)
    log.info('setup: channel %s, group %s', channel_id, group_id)


def claim_owner(user_id: int) -> None:
    """No ADMIN_IDS and nobody claimed the bot yet: the first person to send /setup owns it."""
    cfg.admin_ids.add(user_id)
    state.put('owners', ','.join(str(x) for x in sorted(cfg.admin_ids)))
    log.info('setup: %s is the owner now', user_id)
ADMIN_CACHE_SECONDS = 600

# Last good copy of the content. A broken edit or GitHub being down keeps the
# bot running on what worked before instead of stopping moderation or posting.
current = {'settings': Settings(), 'posts': [], 'sources': [], 'loaded': False}


def settings() -> Settings:
    return current['settings']


async def refresh_content(ctx: ContextTypes.DEFAULT_TYPE | None = None) -> None:
    """Re-read keeper.yaml, posts.yaml and sources.yaml. Each file falls back to its last good copy on error."""
    try:
        current['settings'] = parse_settings(await content.read_text('keeper.yaml'))
    except (ContentError, ValueError) as e:
        log.error('keeper.yaml not applied, keeping previous settings: %s', e)
    try:
        current['posts'] = parse_posts(await content.read_text('posts.yaml'), current['settings'].timezone)
    except (ContentError, ValueError) as e:
        log.error('posts.yaml not applied, keeping previous posts: %s', e)
    try:
        current['sources'] = parse_sources(await content.read_text('sources.yaml'))
    except (ContentError, ValueError) as e:
        log.error('sources.yaml not applied, keeping previous sources: %s', e)
    if not current['loaded']:
        current['loaded'] = True
        log.info('content from %s: %d posts, %d sources, timezone %s', content.describe(),
                 len(current['posts']), len(current['sources']), current['settings'].timezone)


# ---------- people ----------
async def is_admin(ctx: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    if user_id in cfg.admin_ids:
        return True
    if cfg.group_id is None:
        return False
    cache = ctx.bot_data.get('admins')
    if not cache or time.time() - cache[0] > ADMIN_CACHE_SECONDS:
        admins = await ctx.bot.get_chat_administrators(cfg.group_id)
        cache = (time.time(), {a.user.id for a in admins})
        ctx.bot_data['admins'] = cache
    return user_id in cache[1]


def name_of(user) -> str:
    return f'@{user.username}' if user.username else user.first_name


def under(message_id: int | None) -> dict:
    """Reply to a message if it is still there; send as a plain message if it was deleted."""
    if not message_id:
        return {}
    return {'reply_parameters': ReplyParameters(message_id=message_id, allow_sending_without_reply=True)}


NO_PREVIEW = LinkPreviewOptions(is_disabled=True)

# ---------- what the bot waits for in a private chat ----------
# One wait per person: a new prompt («your comment», «the time», «your answer»…) replaces the previous one,
# and a wait lapses after 10 minutes. Before 1.8.6 waits piled up and never lapsed — a forgotten «Reply» could
# send a later message (a time, a new post) from the channel to a stranger.
WAITS = 'waits'
WAIT_SECONDS = 600


def wait_for(ctx, user_id: int, kind: str, value) -> None:
    ctx.bot_data.setdefault(WAITS, {})[user_id] = (kind, value, time.time())


def waited(ctx, user_id: int, kind: str):
    """The value of this person's current wait of this kind, or None (other kind, none, or lapsed)."""
    w = ctx.bot_data.get(WAITS, {}).get(user_id)
    if not w or w[0] != kind:
        return None
    if time.time() - w[2] > WAIT_SECONDS:
        ctx.bot_data[WAITS].pop(user_id, None)
        return None
    return w[1]


def end_wait(ctx, user_id: int) -> None:
    ctx.bot_data.get(WAITS, {}).pop(user_id, None)


def same_thread(msg) -> dict:
    """Where to answer so the person sees it: in a channel's discussion group people write in the comment
    thread under a post, and a message sent to the group itself never shows up there. Replying to the thread's
    first message puts the bot's message into that thread. No thread -> the group as usual."""
    if msg is None:
        return {}
    root = getattr(msg, 'message_thread_id', None)
    if not root:
        reply = getattr(msg, 'reply_to_message', None)
        root = getattr(reply, 'message_id', None)
    return under(root)


URL_PREFIXES = ('https://', 'http://', 'tg://')


def markup(buttons) -> InlineKeyboardMarkup | None:
    """[(label, data), …] -> one row of buttons; [[…], […]] -> several rows.
    data starting with https:// (or tg://) makes a link button; anything else is a press the bot handles."""
    if not buttons:
        return None
    rows = buttons if isinstance(buttons[0], list) else [buttons]
    return InlineKeyboardMarkup([[InlineKeyboardButton(l, url=d) if d.startswith(URL_PREFIXES)
                                  else InlineKeyboardButton(l, callback_data=d) for l, d in row] for row in rows])


def _unreachable(ctx, admin: int) -> None:
    # Telegram lets a bot write only to people who pressed Start in its chat.
    if admin not in ctx.bot_data.setdefault('unreachable', set()):
        ctx.bot_data['unreachable'].add(admin)
        log.warning('admin %s has not started the bot: open it in Telegram and press Start', admin)


async def notify_admins(ctx: ContextTypes.DEFAULT_TYPE, text: str, buttons=(), quiet: bool = False) -> list:
    """Tell every admin from ADMIN_IDS in a private chat; returns [(admin_id, message_id)] delivered.
    Never raises: moderation must not fail because a notification could not be delivered."""
    sent = []
    for admin in cfg.admin_ids:
        try:
            m = await ctx.bot.send_message(admin, text, reply_markup=markup(buttons), disable_notification=quiet)
            sent.append((admin, m.message_id))
        except Forbidden:
            _unreachable(ctx, admin)
        except Exception as e:
            log.error('notification to admin %s failed: %s', admin, e)
    return sent


async def retire_notes(ctx: ContextTypes.DEFAULT_TYPE, user_id: int, outcome: str) -> None:
    """Older notifications about this user lose their buttons and say what happened next,
    so a stale «Clear warning» is never pressed after a ban."""
    for admin, message_id, text in state.pop_notes(user_id):
        try:
            await ctx.bot.edit_message_text(f'{text}\n\n{outcome}', chat_id=admin, message_id=message_id,
                                            reply_markup=None)
        except Exception as e:   # deleted by the admin, too old, or unchanged — nothing to fix
            log.info('could not update notification %s for admin %s: %s', message_id, admin, e)


# ---------- the channel ----------
FAILED: dict[str, str] = {}      # post id -> why the last attempt failed, in words an owner can act on


def explain(e: Exception) -> str:
    """Telegram's error in plain words, with what to do."""
    text = str(e)
    low = text.lower()
    if 'not enough rights' in low or 'need administrator rights' in low or 'have no rights' in low:
        return f'the bot has no right to post in the channel — channel → Administrators → the bot → «Post messages» ({text})'
    if 'chat not found' in low or 'bot is not a member' in low or 'forbidden' in low:
        return f'the bot is not an admin of the channel, or CHANNEL_ID is wrong ({text})'
    if "can't parse entities" in low:
        return f'the formatting of the text is broken ({text})'
    if 'retry after' in low or 'flood' in low:
        return f'Telegram asked to slow down — try again in a minute ({text})'
    return text


def why_failed(post_id: str) -> str:
    return FAILED.get(post_id, 'unknown error — see the log')


MAX_TRIES = 3
GLOBAL_PROBLEMS = ('not an admin', 'no right', 'no channel chosen', 'slow down')   # not the post's fault
ALERT_EVERY = 3600


async def failed(ctx, post_id: str, what: str) -> bool:
    """Called after a failed publication. True = give this post up (it failed MAX_TRIES times for its own
    reason; the owners are told). A problem with the channel itself (rights, no channel) is never the post's
    fault: the owners are told at most once an hour and the post waits."""
    reason = why_failed(post_id)
    if any(p in reason for p in GLOBAL_PROBLEMS):
        last = ctx.bot_data.get('channel_alert', 0)
        if time.time() - last > ALERT_EVERY:
            ctx.bot_data['channel_alert'] = time.time()
            await notify_admins(ctx, f'⚠️ Cannot publish to the channel: {reason}. Posts wait until this is fixed.')
        return False
    key = f'fail:{post_id}'
    tries = int(state.get(key) or 0) + 1
    if tries < MAX_TRIES:
        state.put(key, str(tries))
        return False
    state.db.execute('DELETE FROM kv WHERE key=?', (key,))
    await notify_admins(ctx, f'⚠️ {what} was not published after {MAX_TRIES} tries: {reason}. It is set aside.')
    return True
async def send_post(ctx: ContextTypes.DEFAULT_TYPE, chat_id: int, post: Post, text: str, buttons=()) -> int | None:
    """Send a post (with its picture, if any) to a chat; returns the message id, None when the picture is missing."""
    mode = 'HTML' if post.html else None
    # The post's own link buttons first, then the bot's buttons (only in previews).
    rows = [[(label, url)] for label, url in post.links]
    if buttons:
        rows += buttons if isinstance(buttons[0], list) else [list(buttons)]
    buttons = rows
    if post.media:
        return await _send_media(ctx, chat_id, post, text, mode, buttons)
    if post.photo_id:
        try:
            m = await ctx.bot.send_photo(chat_id, photo=post.photo_id, caption=text, parse_mode=mode,
                                         reply_markup=markup(buttons))
            return m.message_id
        except BadRequest as e:
            if not post.photo_id.startswith('https://'):
                raise
            # A picture from a feed that Telegram cannot fetch (gone, too big, not an image): the post goes as text.
            log.info('post %s: picture %s not usable (%s), sending text', post.id, post.photo_id, e)
    if post.image:
        photo = await content.read_bytes(post.image)
        if photo is None:
            log.error('post %s: image %s not found', post.id, post.image)
            return None
        m = await ctx.bot.send_photo(chat_id, photo=photo, caption=text, parse_mode=mode, reply_markup=markup(buttons))
    else:
        m = await ctx.bot.send_message(chat_id, text, parse_mode=mode, reply_markup=markup(buttons))
    return m.message_id


ALBUMS: dict[int, list[int]] = {}    # first message id of a sent album -> all its message ids (to delete later)
SENDERS = {'photo': 'send_photo', 'video': 'send_video', 'animation': 'send_animation'}
INPUT = {'photo': InputMediaPhoto, 'video': InputMediaVideo}


async def _send_media(ctx, chat_id: int, post: Post, text: str, mode, buttons) -> int:
    """One video / GIF / photo with its caption and buttons, or an album. An album cannot carry buttons, so in a
    preview they come in a message right under it — and that message's id is returned (it holds the buttons)."""
    if len(post.media) == 1:
        kind, file_id = post.media[0]
        m = await getattr(ctx.bot, SENDERS[kind])(chat_id, file_id, caption=text, parse_mode=mode,
                                                 reply_markup=markup(buttons))
        return m.message_id
    group = [INPUT[kind](file_id, caption=text if i == 0 else None, parse_mode=mode if i == 0 else None)
             for i, (kind, file_id) in enumerate(post.media)]
    sent = await ctx.bot.send_media_group(chat_id, group)
    ids = [m.message_id for m in sent]
    if len(ALBUMS) > 500:          # previews fill it too; only the latest albums matter
        ALBUMS.clear()
    ALBUMS[ids[0]] = ids
    if buttons:
        m = await ctx.bot.send_message(chat_id, '⬆️ The album above', reply_markup=markup(buttons))
        return m.message_id
    return ids[0]


async def publish(ctx: ContextTypes.DEFAULT_TYPE, post: Post, text: str | None = None) -> int | None:
    """Publish to the channel, remember it, tell admins quietly. The channel message id when it went out."""
    text = post.text if text is None else text
    if cfg.channel_id is None:
        log.warning('post %s waits: no channel yet — send /setup to the bot', post.id)
        FAILED[post.id] = 'no channel chosen yet — send /setup'
        return None
    try:
        message_id = await send_post(ctx, cfg.channel_id, post, text)
        if message_id is None:
            FAILED[post.id] = f'the picture {post.image} is missing'
            return None
    except Exception as e:
        log.error('post %s failed: %s', post.id, e)
        FAILED[post.id] = explain(e)
        return None
    FAILED.pop(post.id, None)
    state.mark_sent(post.id, post.label)
    log.info('published post %s', post.id)
    state.log_action('post', reason=post.id, excerpt=text)
    await notify_admins(ctx, action_text('post', reason=post.id, excerpt=text), quiet=True)
    return message_id
