"""Captcha: everyone except admins proves once that they are a person.

Newcomers — right when they join. People who were in the group before — on their first
message after the captcha is turned on: the message is deleted, they can only read, and get
a button only they can press. Pressed -> they write on, remembered forever. Not pressed in
time -> removed from the group (they may join again and try once more).

Telegram does not give bots the member list, so old members can only be checked when they write.
"""
import time

from telegram import ChatPermissions, Update
from telegram.ext import ContextTypes

from .runtime import cfg, is_admin, log, markup, same_thread, settings, state
from .runtime import name_of as _name

READ_ONLY = ChatPermissions.no_permissions()
CHAT_PERMISSIONS_SECONDS = 600


def button_data(user_id: int) -> str:
    return f'c:{user_id}'


def parse_button(data: str) -> int | None:
    kind, _, uid = (data or '').partition(':')
    return int(uid) if kind == 'c' and uid.isdigit() else None


async def _group_permissions(ctx) -> ChatPermissions:
    """What members of this group may do normally — restored after the press, never more than that."""
    cache = ctx.bot_data.get('group_permissions')
    if not cache or time.time() - cache[0] > CHAT_PERMISSIONS_SECONDS:
        chat = await ctx.bot.get_chat(cfg.group_id)
        cache = (time.time(), chat.permissions or ChatPermissions(can_send_messages=True))
        ctx.bot_data['group_permissions'] = cache
    return cache[1]


async def release(ctx, user_id: int) -> bool:
    """Give a person the group's normal rights back. False when Telegram refused."""
    try:
        await ctx.bot.restrict_chat_member(cfg.group_id, user_id, await _group_permissions(ctx))
        return True
    except Exception as e:
        log.error('cannot give %s their rights back: %s', user_id, e)
        return False


async def needs_check(ctx, user) -> bool:
    c = settings().captcha
    return (c.enabled and user is not None and not user.is_bot and user.id != ctx.bot.id
            and not state.is_human(user.id) and not await is_admin(ctx, user.id))


async def challenge(ctx, user, reason: str, msg=None) -> bool:
    """Read-only + the button. True when the person now has a captcha open."""
    c = settings().captcha
    if not state.captcha_add(user.id, time.time() + c.seconds, reason, _name(user)):
        return True   # already has one
    try:
        await ctx.bot.restrict_chat_member(cfg.group_id, user.id, READ_ONLY)
    except Exception as e:
        # Without the «Ban users» right the bot cannot restrict anyone: say so, do not pretend.
        state.captcha_take(user.id)
        log.error('captcha: cannot restrict %s — does the bot have the «Ban users» right? %s', user.id, e)
        return False
    try:
        m = await _send_button(ctx, c, user, msg)
    except Exception as e:
        # Without the button nobody can pass: lift the restriction rather than remove a person for nothing.
        state.captcha_take(user.id)
        log.error('captcha: could not show the button to %s, letting them write: %s', user.id, e)
        try:
            await ctx.bot.restrict_chat_member(cfg.group_id, user.id, await _group_permissions(ctx))
        except Exception:
            pass
        return False
    state.captcha_set_message(user.id, m.message_id)
    log.info('captcha for %s (%s)', user.id, reason)
    return True


async def _send_button(ctx, c, user, msg):
    return await ctx.bot.send_message(cfg.group_id, c.html(user.id, _name(user)), parse_mode='HTML', **same_thread(msg),
                                   reply_markup=markup([(f'✅ {c.button}', button_data(user.id))]))


async def on_join(ctx, members) -> None:
    for user in members:
        if await needs_check(ctx, user):
            await challenge(ctx, user, 'join')


async def gate(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> bool:
    """True when the message was stopped by the captcha (the caller then does nothing more)."""
    msg = update.effective_message
    user = msg.from_user
    if not await needs_check(ctx, user):
        return False
    if not await challenge(ctx, user, 'first_message', msg):
        return False   # the captcha cannot work (no rights): ordinary moderation still applies
    try:
        await msg.delete()
    except Exception:
        pass
    return True


async def _delete(ctx, message_id) -> None:
    if message_id:
        try:
            await ctx.bot.delete_message(cfg.group_id, message_id)
        except Exception:
            pass


async def on_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    q = update.callback_query
    if q.from_user.id != user_id:
        await q.answer('This button is for someone else.', show_alert=True)
        return
    taken = state.captcha_take(user_id)
    if taken is None:
        await q.answer('Already done.')
        return
    state.mark_human(user_id)
    # A person, not yet «known»: known comes from the first clean message, after the newcomer checks
    # (profile, learning filter, AI). 1.9.3: marking known here let everyone who pressed skip all three.
    if not await release(ctx, user_id):
        from .runtime import notify_admins
        await notify_admins(ctx, f'⚠️ {taken[2] or user_id} pressed «I\'m human», but the bot could not give their '
                                 f'rights back — lift the restriction in the group by hand (id {user_id}).')
        await q.answer('Thanks! The admins will let you write shortly.')
        await _delete(ctx, taken[0])
        return
    await q.answer('Thanks! You can write now.')
    await _delete(ctx, taken[0])
    log.info('captcha passed by %s', user_id)


async def captcha_tick(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Every few seconds: whoever did not press in time leaves the group. Kept in the database,
    so a restart neither forgets anyone nor keeps them read-only forever."""
    for user_id in state.captchas_due(time.time()):
        taken = state.captcha_take(user_id)
        if taken is None:
            continue
        message_id, reason, name = taken
        try:
            # Ban + unban = removed, but free to join again.
            await ctx.bot.ban_chat_member(cfg.group_id, user_id)
            await ctx.bot.unban_chat_member(cfg.group_id, user_id, only_if_banned=True)
        except Exception as e:
            # Could not remove them: at least do not leave them read-only forever with no button.
            log.error('captcha: cannot remove %s (%s) — lifting the restriction instead', user_id, e)
            await release(ctx, user_id)
        await _delete(ctx, message_id)
        state.log_action('captcha_kicked', user_id, name, 'joined' if reason == 'join' else 'first message')
        log.info('captcha: removed %s, no press in time', user_id)
