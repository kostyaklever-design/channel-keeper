"""/setup: pick the channel and the group with buttons — no ids to look up.

The bot remembers every channel and group where it is made admin (Telegram tells it with a
my_chat_member update). /setup in the private chat lists them; you press two buttons; the bot
checks its rights there and says what is missing. With no ADMIN_IDS the first person to send
/setup becomes the owner — so set it up right after the deploy.
"""
from telegram import Update
from telegram.constants import ChatType
from telegram.ext import ContextTypes

from .runtime import (FROM_ENV, cfg, claim_owner, configured, end_wait, log, markup, notify_admins, save_setup, state,
                      wait_for, waited)

PICKED = 'setup_channel'      # bot_data: {owner id: channel id picked in step 1}


def parse_button(data: str) -> tuple[str, int] | None:
    parts = (data or '').split(':')
    if len(parts) != 3 or parts[0] != 's' or parts[1] not in ('ch', 'gr') or not parts[2].lstrip('-').isdigit():
        return None
    return parts[1], int(parts[2])


async def on_my_chat_member(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """The bot was made admin somewhere, or lost its rights there."""
    cm = update.my_chat_member
    chat, status = cm.chat, cm.new_chat_member.status
    if chat.type not in (ChatType.CHANNEL, ChatType.SUPERGROUP, ChatType.GROUP):
        return
    admin = status == 'administrator'
    state.chat_seen(chat.id, chat.type, chat.title or '', admin)
    log.info('chat %s (%s): bot is %s', chat.id, chat.title, status)
    if admin and not configured():
        await notify_admins(ctx, f'I am now an admin in «{chat.title}». Send /setup to pick it.')
    elif not admin and chat.id in (cfg.channel_id, cfg.group_id):
        await notify_admins(ctx, f'⚠️ I am no longer an admin in «{chat.title}». Make me admin again, '
                                 f'or send /setup to pick another chat.')


async def rights(ctx, channel_id: int, group_id: int) -> list[str]:
    """What the bot can and cannot do there, in plain words. Empty problems list = all fine."""
    lines = []
    try:
        me = await ctx.bot.get_chat_member(channel_id, ctx.bot.id)
        lines.append('✅ Channel: can post' if getattr(me, 'can_post_messages', False)
                     else '⚠️ Channel: turn on «Post messages» for the bot')
        # Optional: only for ad posts with a pin or auto-delete.
        if not getattr(me, 'can_edit_messages', False):
            lines.append('ℹ️ Channel: to pin posts, also turn on «Edit messages» (optional)')
        if not getattr(me, 'can_delete_messages', False):
            lines.append('ℹ️ Channel: to delete ad posts on a timer, also turn on «Delete messages» (optional)')
        if not getattr(me, 'can_manage_direct_messages', False):
            lines.append('ℹ️ Channel: to get messages and suggested posts sent to the channel, turn on '
                         '«Manage direct messages» (optional)')
    except Exception as e:
        lines.append(f'⚠️ Channel: I am not an admin there ({e.__class__.__name__})')
    try:
        me = await ctx.bot.get_chat_member(group_id, ctx.bot.id)
        lines.append('✅ Group: can delete messages' if getattr(me, 'can_delete_messages', False)
                     else '⚠️ Group: turn on «Delete messages» for the bot')
        lines.append('✅ Group: can ban and restrict (captcha, flood)' if getattr(me, 'can_restrict_members', False)
                     else '⚠️ Group: turn on «Ban users» for the bot')
        if not getattr(me, 'can_invite_users', False):
            lines.append('ℹ️ Group: to check join requests before people get in, also turn on «Add users» (optional)')
    except Exception as e:
        lines.append(f'⚠️ Group: I am not an admin there ({e.__class__.__name__})')
    try:
        chan = await ctx.bot.get_chat(channel_id)
        if getattr(chan, 'linked_chat_id', None) and chan.linked_chat_id != group_id:
            lines.append('⚠️ This group is not the discussion group of this channel — comments go elsewhere')
    except Exception:
        pass
    return lines


def _choices(kinds: tuple, step: str) -> list[list[tuple[str, str]]]:
    return [[(title[:40], f's:{step}:{cid}')] for cid, title in state.chats_where_admin(*kinds)[:10]]


async def cmd_setup(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    msg, user, chat = update.effective_message, update.effective_user, update.effective_chat
    if chat.type in (ChatType.SUPERGROUP, ChatType.GROUP):
        # /setup sent in a group: remember the group, in case Telegram's notice was missed.
        if user.id in cfg.admin_ids:
            state.chat_seen(chat.id, chat.type, chat.title or '', True)
            await msg.reply_text('Got this group. Now open me in a private chat and send /setup.')
        return
    if not cfg.admin_ids:
        claim_owner(user.id)
        await msg.reply_text('You are the owner of this bot now. Only you can manage it; '
                             'add more people with ADMIN_IDS in the server variables.')
    elif user.id not in cfg.admin_ids:
        return
    if FROM_ENV['channel'] and FROM_ENV['group']:
        report = await rights(ctx, cfg.channel_id, cfg.group_id)
        await msg.reply_text('The channel and the group are set by CHANNEL_ID and GROUP_ID in the server '
                             'variables. Remove them there to choose here.\n\n' + '\n'.join(report))
        return
    if FROM_ENV['channel']:                       # the channel is fixed by CHANNEL_ID: go straight to the group
        await _ask_group(ctx, user.id, cfg.channel_id)
        return
    choices = _choices((ChatType.CHANNEL,), 'ch')
    if not choices:
        wait_for(ctx, user.id, 'setup_forward', True)
        await msg.reply_text('Step 1 of 2 — the channel.\n'
                             'Add me to your channel as admin with «Post messages», then send /setup again.\n'
                             'Already did it? Forward any post from the channel here.')
        return
    await msg.reply_text('Step 1 of 2 — which channel do I post to?', reply_markup=markup(choices))


async def on_forward(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> bool:
    """A post forwarded from a channel during /setup: that channel becomes a choice."""
    msg, user = update.effective_message, update.effective_user
    if not waited(ctx, user.id, 'setup_forward'):
        return False
    origin = getattr(msg, 'forward_origin', None)
    chat = getattr(origin, 'chat', None)
    if chat is None or str(getattr(origin, 'type', '')) != 'channel':
        return False
    end_wait(ctx, user.id)
    state.chat_seen(chat.id, ChatType.CHANNEL, chat.title or '', True)
    await msg.reply_text(f'Got «{chat.title}».', reply_markup=markup([[(chat.title[:40], f's:ch:{chat.id}')]]))
    return True


async def on_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE, step: str, chat_id: int) -> None:
    q = update.callback_query
    if q.from_user.id not in cfg.admin_ids:
        await q.answer('Only the owner can do this.', show_alert=True)
        return
    await q.answer()
    if step == 'ch':
        end_wait(ctx, q.from_user.id)              # the forwarding fallback, if it was waiting, is done
        if FROM_ENV['group']:                      # the group is fixed by GROUP_ID: only the channel was to pick
            await _finish(ctx, q.from_user.id, chat_id, cfg.group_id)
            return
        await _ask_group(ctx, q.from_user.id, chat_id)
        return
    channel = ctx.bot_data.get(PICKED, {}).pop(q.from_user.id, None) or cfg.channel_id
    if channel is None:
        await ctx.bot.send_message(q.from_user.id, 'Pick the channel first: send /setup.')
        return
    await _finish(ctx, q.from_user.id, channel, chat_id)


async def _ask_group(ctx, owner_id: int, chat_id: int) -> None:
    """Step 2: the discussion group, the one linked to the channel first."""
    ctx.bot_data.setdefault(PICKED, {})[owner_id] = chat_id
    groups = _choices((ChatType.SUPERGROUP, ChatType.GROUP), 'gr')
    linked = None
    try:
        linked = (await ctx.bot.get_chat(chat_id)).linked_chat_id
    except Exception:
        pass
    if linked:
        groups = sorted(groups, key=lambda row: row[0][1] != f's:gr:{linked}')
        groups = [[(f'⭐ {label}' if data == f's:gr:{linked}' else label, data)] for [(label, data)] in groups]
    if not groups:
        await ctx.bot.send_message(owner_id, 'Step 2 of 2 — the discussion group.\n'
                                   'Add me to the group as admin with «Delete messages» and «Ban users», '
                                   'then send /setup in that group, and /setup here again.')
        return
    await ctx.bot.send_message(owner_id, 'Step 2 of 2 — the discussion group (⭐ = linked to the channel):',
                               reply_markup=markup(groups))


async def _finish(ctx, owner_id: int, channel: int, chat_id: int) -> None:
    save_setup(channel, chat_id)
    for key in ('admins', 'group_permissions'):    # they belonged to the previous group
        ctx.bot_data.pop(key, None)
    report = await rights(ctx, channel, chat_id)
    ok = not any(line.startswith('⚠️') for line in report)
    await ctx.bot.send_message(owner_id, ('✅ Done. ' if ok else 'Saved, but fix the ⚠️ lines and send /setup '
                                                'again to check.\n') + '\n'.join(report) +
                               '\n\nNext: send me a post right here to try it, or see /queue.')
