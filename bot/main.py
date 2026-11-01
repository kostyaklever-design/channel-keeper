"""Channel Keeper: moderates a channel's discussion group, publishes scheduled posts and posts from feeds."""
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.ext import (Application, ApplicationHandlerStop, CallbackQueryHandler, ChatJoinRequestHandler,
                          ChatMemberHandler, CommandHandler, ContextTypes, MessageHandler, TypeHandler, filters)

from . import __version__
from . import ai_flow, captcha, dm_posts, dm_rules, guard, inbox, joins, language, probation, report, review, setup
from . import drafts as D
from .channel_queue import cmd_queue, on_queue_button, queue_tick
from .channel_queue import parse_button as parse_queue_button
from .draft_flow import cmd_drafts, drafts_tick, on_draft_button, on_private_text, waiting_comment
from .feeds import POLL_SECONDS, cmd_sources, poll
from .i18n import tr
from .moderation import spam_reason
from .notify import FORGIVE, OK, UNBAN, action_text, buttons_for, log_text, parse_button
from .runtime import (FAILED, GROUP, cfg, configured, current, failed, same_thread, why_failed, is_admin, log, notify_admins, publish, refresh_content, retire_notes,
                      settings, state)
from .runtime import name_of as _name
from .schedule import due_posts
from .settings import Settings

CONTENT_REFRESH_SECONDS = 300


async def _delete_later(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id, message_id = ctx.job.data
    try:
        await ctx.bot.delete_message(chat_id, message_id)
    except Exception:  # already gone — fine
        pass


# ---------- moderation ----------
def channel_name(chat) -> str:
    return f'@{chat.username}' if chat.username else (chat.title or str(chat.id))


def author(msg) -> tuple[int, str] | None:
    """Who wrote this: (id, name). A message «on behalf of a channel» comes from Telegram's
    service account Channel_Bot; the real author is the channel (a negative id) —
    warnings and bans must hit the channel, not the service account shared by every channel."""
    if msg.sender_chat:
        return msg.sender_chat.id, channel_name(msg.sender_chat)
    if msg.from_user:
        return msg.from_user.id, _name(msg.from_user)
    return None


async def ban(ctx, actor_id: int) -> None:
    if actor_id < 0:
        await ctx.bot.ban_chat_sender_chat(cfg.group_id, actor_id)
    else:
        await ctx.bot.ban_chat_member(cfg.group_id, actor_id)


async def unban(ctx, actor_id: int) -> None:
    """Able to write again — not only «not banned»: a flood mute or an open captcha is lifted too."""
    if actor_id < 0:
        await ctx.bot.unban_chat_sender_chat(cfg.group_id, actor_id)
        return
    await ctx.bot.unban_chat_member(cfg.group_id, actor_id, only_if_banned=True)
    taken = state.captcha_take(actor_id)
    if taken and taken[0]:
        try:
            await ctx.bot.delete_message(cfg.group_id, taken[0])
        except Exception:
            pass
    state.mark_human(actor_id)
    await captcha.release(ctx, actor_id)


def reply_target(msg):
    """The message an admin replied to — unless it is the channel post the comment thread hangs on
    (in a thread every message «replies» to it): then there is no real target."""
    target = getattr(msg, 'reply_to_message', None)
    if target is None or getattr(target, 'is_automatic_forward', False):
        return None
    sender = getattr(target, 'sender_chat', None)
    if sender is not None and sender.id in (cfg.channel_id, cfg.group_id):
        return None
    return target


async def on_group_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> bool:
    """True when the bot stopped the message (deleted, held, sent to owners); False when it went through."""
    msg = update.effective_message
    if msg is None:
        return False
    if msg.is_automatic_forward:
        if getattr(update, 'edited_message', None) is None:
            guard.remember_post(ctx, msg)   # a new channel post mirrored into the group: its thread is fresh
        return False
    if msg.sender_chat and msg.sender_chat.id in (cfg.channel_id, cfg.group_id):
        return False  # channel itself or anonymous admin
    who = author(msg)
    if who is None:
        return False
    actor_id, actor_name = who
    s: Settings = settings()
    # An edit is checked for spam only: a clean message later turned into an ad is a known trick.
    edited = getattr(update, 'edited_message', None) is not None
    if actor_id > 0:
        if actor_id == ctx.bot.id or await is_admin(ctx, actor_id):
            return False
        if edited:
            pass
        elif await captcha.gate(update, ctx):
            return True  # not confirmed as a person yet: message deleted, button shown
        elif await guard.too_soon(ctx, msg, actor_id, actor_name):
            return True  # a stranger in the first minutes of a fresh post
        elif await guard.flood(ctx, msg, actor_id, actor_name):
            return True
        elif await probation.check(ctx, msg, actor_id, actor_name, guard.say):
            return True  # a newcomer's picture without words, forward, contact…

    entity_types = [str(e.type) for e in (msg.entities or ())] + [str(e.type) for e in (msg.caption_entities or ())]
    origin = msg.forward_origin
    from_channel = origin is not None and str(origin.type) == 'channel'
    if actor_id < 0 and s.channel_messages == 'block':
        # A channel cannot press the captcha button, so «block» is the captcha for channels.
        reason = tr('message on behalf of a channel')
    else:
        reason = spam_reason(msg.text or msg.caption or '', entity_types, s.spam_words, from_channel)
    if not reason:
        if actor_id > 0 and not edited:
            text = msg.text or msg.caption or ''
            if state.review_open(actor_id):
                return True                  # owners have not decided about this person yet: do not ask again
            if state.known_since(actor_id) is None:
                why = await probation.profile_problem(ctx, actor_id)
                if why:
                    await review.ask_owners(ctx, msg, actor_id, actor_name, tr('👤 Newcomer with {why}.', why=why), 'profile')
                    state.log_action('profile_flag', actor_id, actor_name, why, text)
                    return True              # owners decide; not «known» until then
            if state.known_since(actor_id) is None and await review.learned_check(ctx, msg, actor_id, actor_name):
                return True                  # looks like what the owners deleted before: they decide
            if ai_flow.worth_checking(text, actor_id) and await ai_flow.second_opinion(ctx, msg, actor_id, actor_name):
                return True                  # owners decide; not «known» until then
            state.mark_known(actor_id, probation.counts(text))  # a regular for first minutes and probation
        return False
    if edited:
        reason = tr('{reason} (added by editing)', reason=reason)

    excerpt = msg.text or msg.caption or ''
    await msg.delete()
    group_id = getattr(msg, 'media_group_id', None)
    if group_id:
        punished = ctx.bot_data.setdefault('punished_albums', {})
        if group_id in punished:
            return True                 # the rest of an album already counted as one violation
        if len(punished) > 500:
            punished.clear()
        punished[group_id] = time.time()
    warns = state.add_warning(actor_id)
    if warns >= 2:
        await ban(ctx, actor_id)
        state.clear_warnings(actor_id)
        kind = 'ban'
    else:
        kind = 'warn'
    note = await ctx.bot.send_message(cfg.group_id, s.html(kind, actor_id, actor_name), parse_mode='HTML',
                                      **same_thread(msg))   # in the comment thread, where the person is
    log.info('%s %s (%s): %s', kind, actor_id, actor_name, reason)
    ctx.job_queue.run_once(_delete_later, s.warn_seconds, data=(cfg.group_id, note.message_id))
    state.log_action(kind, actor_id, actor_name, reason, excerpt)
    if kind == 'ban':
        await retire_notes(ctx, actor_id, tr('→ banned after a second violation'))
    text = action_text(kind, actor_name, actor_id, reason, excerpt)
    for admin, message_id in await notify_admins(ctx, text, buttons_for(kind, actor_id)):
        state.add_note(actor_id, admin, message_id, text)
    return True


async def moderate_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """A command-shaped message in the group: checked like any other; if it was stopped, no command runs."""
    if await on_group_message(update, ctx):
        raise ApplicationHandlerStop


async def on_service_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Newcomers get the captcha; then 'X joined / X left' is hidden to keep the chat clean."""
    msg = update.effective_message
    if msg.new_chat_members:
        await captcha.on_join(ctx, msg.new_chat_members)
    try:
        await update.effective_message.delete()
    except Exception:
        pass


# ---------- admin commands ----------
async def cmd_ban(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if not await is_admin(ctx, update.effective_user.id):
        return
    target = reply_target(msg)
    who = author(target) if target else None
    if who is None:
        await msg.reply_text(tr("Reply to the spammer's message with /ban."))
        return
    await ban(ctx, who[0])
    state.clear_warnings(who[0])
    await retire_notes(ctx, who[0], tr('→ banned by an admin'))
    await target.delete()
    await msg.delete()
    log.info('manual ban %s by %s', who[0], update.effective_user.id)
    state.log_action('manual_ban', who[0], who[1], tr('by /ban'),
                     target.text or target.caption or '', by_admin=update.effective_user.id)


async def cmd_unban(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if not await is_admin(ctx, update.effective_user.id):
        return
    target = reply_target(msg)
    who = author(target) if target else None
    if ctx.args and ctx.args[0].lstrip('-').isdigit():
        uid = int(ctx.args[0])                 # an id given explicitly always wins
    elif who:
        uid = who[0]
    else:
        await msg.reply_text(tr('Use /unban <user or channel id> or reply to a message with /unban.'))
        return
    await unban(ctx, uid)
    state.clear_warnings(uid)
    await retire_notes(ctx, uid, tr('→ unbanned by an admin'))
    state.log_action('unban', uid, '', tr('by /unban'), by_admin=update.effective_user.id)
    await msg.reply_text(tr('Channel {id} can write again.', id=uid) if uid < 0 else tr('User {id} can write again.', id=uid))


async def cmd_version(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Shows which version is running."""
    await update.effective_message.reply_text(f'Channel Keeper v{__version__}')


async def cmd_id(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Setup helper: shows chat id and your user id."""
    msg = update.effective_message
    await msg.reply_text(tr('chat id: {chat}\nyour user id: {user}', chat=update.effective_chat.id, user=update.effective_user.id))


LOG_MAX = 100


async def cmd_log(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """What the bot did: /log (last 20), /log 100, /log @name or /log 123456 (one person or channel)."""
    if not await is_admin(ctx, update.effective_user.id):
        return
    arg = (ctx.args or [''])[0].strip()
    if arg.isdigit() and len(arg) <= 3:
        actions = state.recent_actions(min(max(int(arg), 1), LOG_MAX))
    elif arg:
        actions = state.recent_actions(LOG_MAX, who=arg)
    else:
        actions = state.recent_actions(20)
    text = log_text(actions, current['settings'].timezone)
    for chunk in split_text(text):
        await update.effective_message.reply_text(chunk)


def split_text(text: str, limit: int = 4000) -> list[str]:
    """Telegram allows 4096 characters per message; long logs go in several, cut at line ends."""
    chunks, cur = [], ''
    for line in text.split('\n'):
        if len(cur) + len(line) + 1 > limit and cur:
            chunks.append(cur)
            cur = ''
        cur = f'{cur}\n{line}' if cur else line[:limit]
    return chunks + [cur] if cur else chunks


async def on_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Every button press: the captcha, drafts, the queue, or Unban / Clear warning / OK under an admin notification."""
    q = update.callback_query
    human = captcha.parse_button(q.data)
    if human is not None:
        await captcha.on_button(update, ctx, human)
        return
    join = joins.parse_button(q.data)
    if join:
        await joins.on_button(update, ctx, *join)
        return
    mail = inbox.parse_button(q.data)
    if mail:
        await inbox.on_button(update, ctx, *mail)
        return
    verdict = review.parse_button(q.data)
    if verdict:
        await review.on_button(update, ctx, *verdict)
        return
    picked = setup.parse_button(q.data)
    if picked:
        await setup.on_button(update, ctx, *picked)
        return
    own = dm_rules.parse_button(q.data)
    if own:
        await dm_posts.on_button(update, ctx, *own)
        return
    draft = D.parse_button(q.data)
    if draft and draft[0] == D.RETELL:
        await ai_flow.on_retell(update, ctx, draft[1])
        return
    if draft:
        await on_draft_button(update, ctx, *draft)
        return
    held = parse_queue_button(q.data)
    if held:
        await on_queue_button(update, ctx, *held)
        return
    parsed = parse_button(q.data)
    if parsed is None:
        await q.answer()
        return
    if not await is_admin(ctx, q.from_user.id):
        await q.answer(tr('Only admins can do this.'), show_alert=True)
        return
    action, uid = parsed
    original = getattr(q.message, 'text', None) or ''   # an «inaccessible» old message has no text
    if action != OK:
        # The pressed message is edited below; every other copy (other admins, older notes) retires here.
        state_notes = [n for n in state.pop_notes(uid) if not (q.message and (n[0], n[1]) == (q.message.chat.id, q.message.message_id))]
    else:
        state_notes = []
    if action == UNBAN:
        await unban(ctx, uid)
        state.clear_warnings(uid)
        state.log_action('unban', uid, state.name_of(uid), tr('button'), by_admin=q.from_user.id)
        done = tr('✅ Unbanned by {who} — they can join again.', who=_name(q.from_user))
    elif action == FORGIVE:
        state.clear_warnings(uid)
        state.log_action('forgive', uid, state.name_of(uid), tr('button'), by_admin=q.from_user.id)
        done = tr('✅ Warning cleared by {who}.', who=_name(q.from_user))
    else:
        done = ''
    for admin, message_id, text in state_notes:
        try:
            await ctx.bot.edit_message_text(f'{text}\n\n{done}', chat_id=admin, message_id=message_id, reply_markup=None)
        except Exception:
            pass
    await q.answer()
    try:
        # Buttons go away after one press, so a second press cannot repeat the action.
        await q.edit_message_text(f'{original}\n\n{done}' if done else original, reply_markup=None)
    except Exception:
        pass


# ---------- scheduled posts ----------
async def tick(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not configured():
        return            # nothing to publish to until /setup picks the channel
    now = datetime.now(ZoneInfo('UTC'))
    send, skip = due_posts(current['posts'], now, state.is_sent)
    for p in skip:
        log.warning('skipped old post %s (was due %s)', p.id, p.at)
        state.mark_sent(p.id, p.label, published=False)
        why = why_failed(p.id) if p.id in FAILED else tr('the bot was offline')
        await notify_admins(ctx, tr('⚠️ «{id}» from posts.yaml was due {at} and did not go out ({why}). It is skipped — '
                                    'change its id and time to send it again.', id=p.id, at=f'{p.at:%d.%m %H:%M}', why=why),
                            quiet=True)
    for p in send:
        if not await publish(ctx, p) and await failed(ctx, p.id, tr('«{id}» from posts.yaml', id=p.id)):
            state.mark_sent(p.id, p.label, published=False)
    await drafts_tick(ctx)
    await queue_tick(ctx)
    await dm_posts.dm_tick(ctx)
    await dm_posts.timers_tick(ctx)


async def on_private(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """A private message: a draft comment or a time the bot asked for; otherwise a new post."""
    uid = update.effective_user.id
    if await setup.on_key(update, ctx):          # first: a pasted key must never become a post or a reply
        return
    if await setup.on_forward(update, ctx):
        return
    if inbox.waiting_reply(ctx, uid, update.effective_message):
        await inbox.on_reply_text(update, ctx)
    elif waiting_comment(ctx, uid):
        await on_private_text(update, ctx)
    elif ai_flow.waiting_edit(ctx, uid):
        await ai_flow.on_edit_text(update, ctx)
    elif dm_posts.waiting_links(ctx, uid):
        await dm_posts.on_links_text(update, ctx)
    elif dm_posts.waiting_time(ctx, uid):
        await dm_posts.on_time_text(update, ctx)
    else:
        await dm_posts.on_new_post(update, ctx)


async def cmd_forget(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/forget <id> — delete everything the bot keeps about a person or channel. Owners only."""
    if update.effective_user.id not in cfg.admin_ids:
        return
    arg = (ctx.args or [''])[0]
    if not arg.lstrip('-').isdigit():
        await update.effective_message.reply_text(tr('Use /forget 123456789 (a user or channel id — see /log).'))
        return
    uid = int(arg)
    if uid > 0 and state.captcha_open(uid):
        await captcha.release(ctx, uid)        # deleting the captcha row must not leave them read-only forever
    n = state.forget_person(uid)
    review.forget_model()                      # the filter must not keep learning from deleted texts
    ctx.bot_data.get('profiles', {}).pop(uid, None)
    log.info('forget %s by %s: %d records', arg, update.effective_user.id, n)
    await update.effective_message.reply_text(tr('Deleted {n} records about {id}: warnings, captcha, log lines. '
                                                 'A ban in Telegram itself stays — use /unban for that.', n=n, id=arg))


async def purge(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Log lines older than keep_days are deleted: the log is for recent history, not an archive."""
    n = state.forget_old_actions(time.time() - settings().keep_days * 86400)
    if n:
        log.info('deleted %d log lines older than %d days', n, settings().keep_days)


async def on_error(update: object, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    log.error('error: %s', ctx.error)


async def _startup(app: Application) -> None:
    fixed = state.reconcile()
    if fixed:
        log.info('after the restart: %d posts were left «publishing» and are put right', fixed)
    await refresh_content()
    await language.set_menu(app.bot)


def build_app() -> Application:
    """The bot with every handler and job wired — built without touching the network."""
    app = Application.builder().token(cfg.bot_token).post_init(_startup).build()
    group = GROUP
    # Commands are only for new messages (an edited /ban must not ban twice) and never in the channel's inbox chat.
    new = filters.UpdateType.MESSAGE & ~filters.DIRECT_MESSAGES
    # A message in the group that starts with a command («/x buy crypto https://…») is moderated first:
    # without this, command-shaped spam would skip every check. Admins' real commands pass untouched.
    app.add_handler(TypeHandler(Update, language.remember), group=-2)    # the owners' Telegram language
    app.add_handler(MessageHandler(group & filters.COMMAND & filters.UpdateType.MESSAGE, moderate_command), group=-1)
    app.add_handler(CommandHandler('id', cmd_id, filters=new))
    app.add_handler(CommandHandler('setup', setup.cmd_setup, filters=new))
    app.add_handler(CommandHandler('forget', cmd_forget, filters=filters.ChatType.PRIVATE))
    app.add_handler(CommandHandler('ai', ai_flow.cmd_ai, filters=filters.ChatType.PRIVATE))
    app.add_handler(CommandHandler('report', report.cmd_report, filters=filters.ChatType.PRIVATE))
    app.add_handler(CommandHandler('lang', language.cmd_lang, filters=filters.ChatType.PRIVATE))
    app.add_handler(ChatMemberHandler(setup.on_my_chat_member, ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_handler(ChatJoinRequestHandler(joins.on_request))
    app.add_handler(CommandHandler('version', cmd_version, filters=new))
    app.add_handler(CommandHandler('ban', cmd_ban, filters=group & new))
    app.add_handler(CommandHandler('unban', cmd_unban, filters=group & new))
    app.add_handler(CommandHandler('log', cmd_log, filters=filters.ChatType.PRIVATE))
    app.add_handler(CommandHandler('drafts', cmd_drafts, filters=filters.ChatType.PRIVATE))
    app.add_handler(CommandHandler('sources', cmd_sources, filters=filters.ChatType.PRIVATE))
    app.add_handler(CommandHandler('queue', cmd_queue, filters=filters.ChatType.PRIVATE))
    app.add_handler(CallbackQueryHandler(on_button))
    app.add_handler(MessageHandler(group & (filters.StatusUpdate.NEW_CHAT_MEMBERS | filters.StatusUpdate.LEFT_CHAT_MEMBER),
                                   on_service_message))
    # The channel's direct messages and suggested posts (Telegram 2025+): to the owners' private chat.
    app.add_handler(MessageHandler(filters.DIRECT_MESSAGES & filters.UpdateType.MESSAGE & ~filters.StatusUpdate.ALL,
                                   inbox.on_message))
    # New and edited group messages: an edit is checked for spam only (see on_group_message).
    app.add_handler(MessageHandler(group & ~filters.COMMAND & ~filters.StatusUpdate.ALL, on_group_message))
    # Only new private messages: editing a message you sent the bot must not become a second post.
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.UpdateType.MESSAGE & ~filters.COMMAND
                                   & ~filters.StatusUpdate.ALL, on_private))
    app.add_error_handler(on_error)
    app.job_queue.run_repeating(refresh_content, interval=CONTENT_REFRESH_SECONDS, first=CONTENT_REFRESH_SECONDS)
    app.job_queue.run_repeating(tick, interval=60, first=15)
    app.job_queue.run_repeating(poll, interval=POLL_SECONDS, first=45)
    app.job_queue.run_repeating(captcha.captcha_tick, interval=10, first=10)
    app.job_queue.run_repeating(joins.joins_tick, interval=15, first=20)
    app.job_queue.run_repeating(purge, interval=6 * 3600, first=120)
    app.job_queue.run_repeating(report.weekly, interval=3600, first=300)
    return app


def main() -> None:
    app = build_app()
    if configured():
        log.info('Channel Keeper v%s starting: group %s, channel %s', __version__, cfg.group_id, cfg.channel_id)
    else:
        log.info('Channel Keeper v%s starting, not set up yet: open the bot in Telegram and send /setup', __version__)
    if state.migrated:
        log.info('memory moved from state.json to keeper.db (old file kept as state.json.migrated)')
    app.run_polling(allowed_updates=['message', 'edited_message', 'callback_query', 'my_chat_member', 'chat_join_request'],
                    drop_pending_updates=True)


if __name__ == '__main__':
    main()
