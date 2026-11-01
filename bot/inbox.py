"""The channel's inbox: messages people write to the channel, and the posts they suggest.

Since 2025 Telegram lets anyone write to a channel and suggest a post (free or for Stars). Both
arrive in the channel's direct-messages chat. The bot needs «Manage direct messages» in the
channel to see them. It brings them to the owners' private chat:
- a message -> «↩️ Reply»: the owner writes the answer, the bot delivers it as the channel;
- a suggested post -> «✅ Approve / ❌ Decline»: Telegram itself publishes an approved post.

The bot never answers people by itself, with or without AI: it only carries the owner's own words.
Answering automatically is left to a separate, optional connector.
A paid suggested post must stay in the channel 24 hours untouched, or the owner is not paid:
the bot never edits, pins on a timer or deletes it — it is published by Telegram, not by the bot.
"""
import html
import time

from telegram import ForceReply, Update
from telegram.ext import ContextTypes

from .i18n import tr
from .runtime import cfg, end_wait, log, markup, state, wait_for, waited
from .runtime import name_of as _name

LINKED = 'dm_chats'                     # bot_data: {direct-messages chat id: (parent channel id or None, when)}
LINK_CACHE_SECONDS = 3600


def parse_button(data: str) -> tuple[str, int] | None:
    parts = (data or '').split(':')
    if len(parts) != 3 or parts[0] != 'i' or parts[1] not in ('re', 'ok', 'no') or not parts[2].isdigit():
        return None
    return parts[1], int(parts[2])


def price_text(info) -> str:
    price = getattr(info, 'price', None)
    return f'{price.amount} {price.currency}' if price else ''


async def ours(ctx, chat) -> bool:
    """Is this direct-messages chat the one of our channel? (The bot may be admin of several channels.)"""
    cache = ctx.bot_data.setdefault(LINKED, {})
    hit = cache.get(chat.id)
    if hit is None or time.time() - hit[1] > LINK_CACHE_SECONDS:
        try:
            full = await ctx.bot.get_chat(chat.id)
            parent = getattr(getattr(full, 'parent_chat', None), 'id', None)
        except Exception as e:
            log.info('direct messages chat %s: %s', chat.id, e)
            parent = None
        hit = cache[chat.id] = (parent, time.time())
    return hit[0] is not None and hit[0] == cfg.channel_id


async def on_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Anything new in the channel's direct-messages chat."""
    msg = update.effective_message
    if msg is None or not await ours(ctx, msg.chat):
        return
    user = msg.from_user
    if user is not None and (user.id == ctx.bot.id or user.id in cfg.admin_ids):
        return                           # our own replies, and owners writing there in the app
    if msg.sender_chat is not None and msg.sender_chat.id == cfg.channel_id:
        return                           # any admin answering as the channel in the app
    topic = getattr(getattr(msg, 'direct_messages_topic', None), 'topic_id', None)
    if topic is None:
        return
    name = _name(user) if user else tr('someone')
    text = msg.text or msg.caption or tr("(no text — open the channel's messages in Telegram)")
    info = getattr(msg, 'suggested_post_info', None)
    if info is not None and getattr(info, 'state', '') == 'pending':
        price = price_text(info)
        item = state.inbox_add(msg.chat.id, topic, msg.message_id, user.id if user else None, name, text,
                               'suggestion', price)
        head = (tr('📝 Suggested post from {name} — offers {price}', name=name, price=price) if price
                else tr('📝 Suggested post from {name} (free)', name=name))
        buttons = [[(tr('✅ Approve'), f'i:ok:{item}'), (tr('❌ Decline'), f'i:no:{item}')]]
        await _tell(ctx, f'{head}:\n\n{text[:3500]}', buttons)
        state.log_action('suggested', user.id if user else None, name, price or 'free', text)
        return
    item = state.inbox_add(msg.chat.id, topic, msg.message_id, user.id if user else None, name, text, 'message')
    await _tell(ctx, tr('✉️ {name} wrote to the channel:', name=name) + f'\n\n{text[:3500]}', [[(tr('↩️ Reply'), f'i:re:{item}')]])


async def _tell(ctx, text: str, buttons) -> None:
    for owner in cfg.admin_ids:
        try:
            await ctx.bot.send_message(owner, text, reply_markup=markup(buttons))
        except Exception as e:
            log.info('could not bring the inbox to %s: %s', owner, e)


async def on_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE, action: str, item_id: int) -> None:
    q = update.callback_query
    if q.from_user.id not in cfg.admin_ids:
        await q.answer(tr('Only the owners can do this.'), show_alert=True)
        return
    item = state.inbox(item_id)
    if item is None or item.status != 'new' and action != 're':
        await q.answer(tr('Already decided.'))
        return
    who = _name(q.from_user)
    if action == 're':
        await q.answer()
        prompt = await ctx.bot.send_message(q.from_user.id, tr('Your answer to {name} — it goes from the channel. '
                                                               'Reply to this message:', name=item.name),
                                            reply_markup=ForceReply(selective=True, input_field_placeholder=tr('Your answer')))
        # Only a reply to this very prompt goes out as the channel: anything else the owner writes is not it.
        wait_for(ctx, q.from_user.id, 'inbox_reply', (item_id, prompt.message_id))
        return
    if action == 'ok':
        if not state.inbox_move(item_id, 'approved', ('new',)):
            await q.answer(tr('Already decided.'))
            return
        try:
            await ctx.bot.approve_suggested_post(item.chat_id, item.message_id)
            outcome = tr('✅ Approved by {who} — Telegram publishes it in the channel.', who=who)
            state.log_action('suggestion_approved', item.user_id, item.name, item.price or 'free', by_admin=q.from_user.id)
        except Exception as e:
            if gone(e):
                state.inbox_move(item_id, 'gone', ('approved',))
                outcome = tr('Already handled in Telegram or expired ({error}).', error=e)
            else:
                state.inbox_move(item_id, 'new', ('approved',))
                outcome = tr('⚠️ Telegram refused: {error}. Does the bot have «Manage direct messages» and «Post messages»?', error=e)
    else:
        if not state.inbox_move(item_id, 'declined', ('new',)):
            await q.answer(tr('Already decided.'))
            return
        try:
            await ctx.bot.decline_suggested_post(item.chat_id, item.message_id)
            outcome = tr('❌ Declined by {who}.', who=who)
            state.log_action('suggestion_declined', item.user_id, item.name, item.price or 'free', by_admin=q.from_user.id)
        except Exception as e:
            if gone(e):
                state.inbox_move(item_id, 'gone', ('declined',))
                outcome = tr('Already handled in Telegram or expired ({error}).', error=e)
            else:
                state.inbox_move(item_id, 'new', ('declined',))
                outcome = tr('⚠️ Telegram refused: {error}.', error=e)
    await q.answer()
    try:
        await q.edit_message_text(f'{getattr(q.message, "text", None) or ""}\n\n{outcome}'.strip(), reply_markup=None)
    except Exception:
        await ctx.bot.send_message(q.from_user.id, outcome)


def gone(e: Exception) -> bool:
    """The suggestion no longer exists or was already decided (in the app, or it expired)."""
    low = str(e).lower()
    return any(w in low for w in ('not found', 'already', 'expired', 'invalid message'))


def waiting_reply(ctx, user_id: int, msg=None) -> bool:
    """True only for a reply to the bot's «Your answer» prompt. Any other message ends the wait: the owner
    moved on, and their next post must never go to a stranger as the channel."""
    w = waited(ctx, user_id, 'inbox_reply')
    if w is None:
        return False
    replied_to = getattr(getattr(msg, 'reply_to_message', None), 'message_id', None)
    if replied_to != w[1]:
        end_wait(ctx, user_id)
        return False
    return True


async def on_reply_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """The owner's answer: delivered into that person's topic, as the channel."""
    msg, user = update.effective_message, update.effective_user
    if not (msg.text or '').strip():
        await msg.reply_text(tr("Only text can be sent as the channel's answer. Write it, or press ↩️ Reply again later."))
        return
    w = waited(ctx, user.id, 'inbox_reply')
    item = state.inbox(w[0]) if w else None
    end_wait(ctx, user.id)
    if item is None:
        await msg.reply_text(tr('That conversation is gone — nothing sent.'))
        return
    try:
        await ctx.bot.send_message(item.chat_id, msg.text_html or html.escape(msg.text or ''), parse_mode='HTML',
                                   direct_messages_topic_id=item.topic_id)
    except Exception as e:
        await msg.reply_text(tr('Not sent: {error}. Does the bot have «Manage direct messages» in the channel?', error=e))
        return
    state.inbox_move(item.id, 'answered', ('new', 'answered'))
    await msg.reply_text(tr('↩️ Sent to {name} from the channel.', name=item.name))


def summary() -> str:
    open_items = state.inbox_open()
    if not open_items:
        return ''
    msgs = sum(1 for i in open_items if i.kind == 'message')
    sugg = len(open_items) - msgs
    return tr('Inbox: unanswered messages {m}, suggested posts {s}', m=msgs, s=sugg)

