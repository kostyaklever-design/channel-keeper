"""Join requests: the captcha before someone is even in the group.

Works when the group has «Approve new members» on (Group → Edit → Group type / Join requests).
Then Telegram asks the bot about each newcomer, and the bot may write to that person for 5 minutes:
- captcha (default): a button in their private chat; pressed in time -> approved and remembered as a person;
  not pressed -> declined (they may ask again);
- a link or spam word in their profile, or join_requests: owners -> the owners decide with Approve / Decline.
The bot needs the «Add users» (invite users) right in the group to approve.
"""
import time

from telegram import Update
from telegram.ext import ContextTypes

from .i18n import of_code, tr
from .probation import profile_reason
from .runtime import cfg, log, markup, settings, state
from .runtime import name_of as _name

LANG = 'join_lang'         # bot_data: {user id: the newcomer's language}, for the «time is up» note
WINDOW = 5 * 60 - 20       # Telegram lets the bot write to the person for 5 minutes after the request


def parse_button(data: str) -> tuple[str, int] | None:
    parts = (data or '').split(':')
    if len(parts) != 3 or parts[0] != 'j' or parts[1] not in ('me', 'ok', 'no') or not parts[2].isdigit():
        return None
    return parts[1], int(parts[2])


async def _ask_owners(ctx, user, why: str, bio: str) -> None:
    text = (tr('🚪 {name} (id {id}) asks to join the group — {why}.', name=_name(user), id=user.id, why=why)
            + ('\n' + tr('Profile: {bio}', bio=bio[:200]) if bio else ''))
    for owner in cfg.admin_ids:
        try:
            await ctx.bot.send_message(owner, text, reply_markup=markup([(tr('✅ Approve'), f'j:ok:{user.id}'),
                                                                         (tr('❌ Decline'), f'j:no:{user.id}')]))
        except Exception as e:
            log.info('could not ask %s about a join request: %s', owner, e)


async def on_request(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    req = update.chat_join_request
    mode = settings().join_requests
    if mode == 'off' or req.chat.id != cfg.group_id:
        return
    user, bio = req.from_user, req.bio or ''
    suspicious = profile_reason(bio, settings().spam_words) if settings().profile_check else None
    if mode == 'owners' or suspicious:
        await _ask_owners(ctx, user, suspicious or tr('please decide'), bio)
        return
    if not state.join_add(user.id, _name(user), time.time() + WINDOW):
        return
    c = settings().captcha
    lang = of_code(getattr(user, 'language_code', None))       # a newcomer reads their own language
    ctx.bot_data.setdefault(LANG, {})[user.id] = lang
    try:
        m = await ctx.bot.send_message(req.user_chat_id, tr('To join «{title}», press the button within 4 minutes.', lang,
                                                            title=req.chat.title),
                                       reply_markup=markup([(f'✅ {c.label(lang)}', f'j:me:{user.id}')]))
        state.join_set_message(user.id, m.message_id)
    except Exception as e:
        state.join_take(user.id)
        log.info('cannot write to %s about their join request: %s', user.id, e)
        await _ask_owners(ctx, user, tr('the bot could not send them the button'), bio)


async def on_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE, action: str, user_id: int) -> None:
    q = update.callback_query
    if action == 'me':
        lang = of_code(getattr(q.from_user, 'language_code', None))
        if q.from_user.id != user_id:
            await q.answer(tr('This button is for someone else.', lang), show_alert=True)
            return
        if state.join_take(user_id) is None:
            await q.answer(tr('Too late — send the request again.', lang), show_alert=True)
            return
        ok = await _decide(ctx, user_id, True)
        state.mark_human(user_id)
        await q.answer(tr('Welcome!', lang) if ok else tr('Something went wrong — the admins will see your request.', lang))
        try:
            await q.edit_message_text(tr('✅ Welcome — you can write in the group now.', lang) if ok else
                                      tr('Your request is waiting for the admins.', lang), reply_markup=None)
        except Exception:
            pass
        return
    if q.from_user.id not in cfg.admin_ids:
        await q.answer(tr('Only the owners can do this.'), show_alert=True)
        return
    state.join_take(user_id)
    ok = await _decide(ctx, user_id, action == 'ok')
    if action == 'ok' and ok:
        state.mark_human(user_id)
    who = _name(q.from_user)
    outcome = ((tr('✅ Approved by {who}.', who=who) if action == 'ok' else tr('❌ Declined by {who}.', who=who)) if ok
               else tr('Already handled (in the app, or the request expired).'))
    await q.answer()
    try:
        await q.edit_message_text(f'{getattr(q.message, "text", None) or ""}\n\n{outcome}'.strip(), reply_markup=None)
    except Exception:
        pass


async def _decide(ctx, user_id: int, approve: bool) -> bool:
    try:
        if approve:
            await ctx.bot.approve_chat_join_request(cfg.group_id, user_id)
        else:
            await ctx.bot.decline_chat_join_request(cfg.group_id, user_id)
            state.log_action('join_declined', user_id, state.name_of(user_id), tr('join request'))
        return True
    except Exception as e:
        log.warning('join request of %s: %s', user_id, e)
        return False


async def joins_tick(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Requests whose button was not pressed in time are declined; the person may ask again."""
    for user_id in state.joins_due(time.time()):
        taken = state.join_take(user_id)
        if taken is None:
            continue
        name, message_id = taken
        try:
            await ctx.bot.decline_chat_join_request(cfg.group_id, user_id)
        except Exception as e:
            log.info('decline %s: %s', user_id, e)
        state.log_action('join_declined', user_id, name, tr('no press in time'))
        if message_id:
            try:
                lang = ctx.bot_data.get(LANG, {}).pop(user_id, 'en')
                await ctx.bot.edit_message_text(tr('⌛ Time is up. Send the join request again to try once more.', lang),
                                                chat_id=user_id, message_id=message_id)
            except Exception:
                pass
