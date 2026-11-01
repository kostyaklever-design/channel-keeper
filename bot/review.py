"""Owners decide about doubtful messages: «🗑 Delete / ✅ Keep». Used by the AI second opinion and the
profile check — neither ever deletes on its own. Every verdict is kept on this server (table
`decisions`) so a future spam filter can learn from the owners' own choices."""
import time

from telegram import Update
from telegram.ext import ContextTypes

from . import learn
from .runtime import cfg, log, markup, settings, state

MODEL = {'model': None, 'at': 0.0}
RETRAIN_SECONDS = 600       # the rules add spam examples all the time; a fresh model every 10 minutes is plenty


def model() -> learn.Model:
    if MODEL['model'] is None or time.time() - MODEL['at'] > RETRAIN_SECONDS:
        MODEL['model'], MODEL['at'] = learn.train(state.examples()), time.time()
    return MODEL['model']


def forget_model() -> None:
    MODEL['model'] = None


async def learned_check(ctx, msg, user_id: int, name: str) -> bool:
    """True when the message looks like what the owners deleted before: they are asked; nothing is deleted."""
    if not settings().learning_filter:
        return False
    text = msg.text or msg.caption or ''
    p = model().spam_probability(text)
    if p < learn.THRESHOLD:
        return False
    await ask_owners(ctx, msg, user_id, name, f'🧠 Looks like spam you deleted before ({int(p * 100)}%).', 'learned')
    state.log_action('learned_flag', user_id, name, f'{int(p * 100)}%', text)
    return True


def buttons(message_id: int, user_id: int) -> list[tuple[str, str]]:
    return [('🗑 Delete', f'm:del:{message_id}:{user_id}'), ('✅ Keep', f'm:keep:{message_id}:{user_id}')]


def parse_button(data: str) -> tuple[str, int, int] | None:
    parts = (data or '').split(':')
    if len(parts) != 4 or parts[0] != 'm' or parts[1] not in ('del', 'keep') \
            or not parts[2].isdigit() or not parts[3].lstrip('-').isdigit():
        return None
    return parts[1], int(parts[2]), int(parts[3])


async def ask_owners(ctx, msg, user_id: int, name: str, headline: str, source: str) -> None:
    """The message stays in the chat; owners get it with the two buttons."""
    text = msg.text or msg.caption or ''
    state.review_add(msg.message_id, user_id, text, source)
    note = f'{headline}\nWho: {name} (id {user_id})\nMessage: {text[:300]}\n\nIt is still in the chat — your call.'
    for admin in cfg.admin_ids:
        try:
            await ctx.bot.send_message(admin, note, reply_markup=markup(buttons(msg.message_id, user_id)))
        except Exception as e:
            log.info('could not ask %s about a doubtful message: %s', admin, e)


async def on_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE, action: str, message_id: int, user_id: int) -> None:
    q = update.callback_query
    if q.from_user.id not in cfg.admin_ids:
        await q.answer('Only the owners can do this.', show_alert=True)
        return
    who = f'@{q.from_user.username}' if q.from_user.username else q.from_user.first_name
    first = state.review_decide(message_id, user_id, 'spam' if action == 'del' else 'ok')
    if not first:
        # Another owner already decided (Keep and Delete must not both happen).
        await q.answer('Already decided by another owner.')
        try:
            await q.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
        return
    forget_model()                  # learn from this verdict right away
    if action == 'del':
        try:
            await ctx.bot.delete_message(cfg.group_id, message_id)
            outcome = f'🗑 Deleted by {who}.'
        except Exception:
            outcome = 'Already gone.'
        state.log_action('review_deleted', user_id, state.name_of(user_id), 'an owner agreed it is spam',
                         by_admin=q.from_user.id)
    else:
        state.trust(user_id)
        outcome = f'✅ Kept by {who}; this person is trusted now — no more checks of this kind.'
    await q.answer()
    try:
        # An old message (48 h+) comes as «inaccessible», without text: then only the outcome is shown.
        await q.edit_message_text(f'{getattr(q.message, "text", None) or ""}\n\n{outcome}'.strip(), reply_markup=None)
    except Exception:
        pass
