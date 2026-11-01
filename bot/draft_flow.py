"""Drafts in Telegram: previews in admins' private chats, the four buttons, comments, expiry.
Drafts come from posts.yaml (status: draft) and from feeds (news always, own posts with mode: draft)."""
from datetime import datetime, timezone

from telegram import ForceReply, Update
from telegram.error import Forbidden
from telegram.ext import ContextTypes

from .i18n import tr
from . import drafts as D
from .channel_queue import find_post as _post
from .channel_queue import publish_item, tell_held, why_not_now
from .runtime import ai, cfg, current, end_wait, failed, wait_for, waited, is_admin, log, name_of, publish, send_post, settings, state, under, why_failed



async def _say_under(ctx, admin: int, message_id: int, text: str) -> None:
    """Remove the buttons from a preview and answer under it with what happened."""
    try:
        await ctx.bot.edit_message_reply_markup(chat_id=admin, message_id=message_id, reply_markup=None)
    except Exception:
        pass   # already without buttons, or deleted by the admin
    if text:
        try:
            await ctx.bot.send_message(admin, text, disable_notification=True, **under(message_id))
        except Exception as e:
            log.info('could not report draft outcome to %s: %s', admin, e)


async def retire(ctx, draft_id: int, text: str) -> None:
    for admin, message_id in state.draft_pop_msgs(draft_id):
        await _say_under(ctx, admin, message_id, text)


async def send_previews(ctx: ContextTypes.DEFAULT_TYPE, draft_id: int, post, comment: str) -> None:
    tz = settings().timezone
    body = D.compose(post, comment)
    for admin in cfg.admin_ids:
        try:
            await ctx.bot.send_message(admin, D.header(post, tz, comment), disable_notification=False)
            mid = await send_post(ctx, admin, post, body, D.buttons(draft_id, post.from_feed, ai.c.on))
            if mid is not None:
                state.draft_add_msg(draft_id, admin, mid)
        except Forbidden:
            log.warning('admin %s has not started the bot: draft %s not delivered', admin, post.id)
        except Exception as e:
            log.error('draft %s preview to %s failed: %s', post.id, admin, e)


async def drafts_tick(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """New drafts from posts.yaml -> previews; approved and due -> channel; unanswered for 48 h -> gone.
    Drafts from feeds get their preview when the feed brings them in, and go to the queue once approved."""
    now = datetime.now(timezone.utc)
    for post in current['posts']:
        if post.status == 'draft' and not state.is_sent(post.id) and state.draft_for(post.id) is None:
            draft_id = state.draft_create(post.id)
            log.info('draft %s sent to admins for review', post.id)
            await send_previews(ctx, draft_id, post, '')
    for d in state.drafts_in(*D.OPEN):
        post = _post(d.post_id)
        if post is None or state.is_sent(post.id):
            continue
        if d.status == 'approved' and not post.from_feed and post.at <= now:
            if state.draft_move(d.id, 'publishing', ('approved',)):
                ok = await publish(ctx, post, D.compose(post, d.comment))
                state.draft_move(d.id, 'published' if ok else 'approved', ('publishing',))
                if not ok and await failed(ctx, post.id, tr('The draft «{id}»', id=post.id)):
                    state.draft_move(d.id, 'failed', ('approved',))
        elif d.status == 'pending' and D.expired(d.created, now):
            if state.draft_move(d.id, 'expired', ('pending',)):
                log.info('draft %s expired after 48 h without an answer', post.id)
                if post.from_feed:
                    item = state.item_by_post(post.id)
                    state.item_move(item.id, 'expired', ('draft',))
                    note = tr('⌛ Expired: no answer in 48 hours.')
                else:
                    note = tr('⌛ Expired: no answer in 48 hours. Change its id in posts.yaml to send it again.')
                await retire(ctx, d.id, note)


async def on_draft_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE, action: str, draft_id: int) -> None:
    q = update.callback_query
    if not await is_admin(ctx, q.from_user.id):
        await q.answer(tr('Only admins can do this.'), show_alert=True)
        return
    d = state.draft(draft_id)
    post = _post(d.post_id) if d else None
    if d is None or d.status not in D.OPEN:
        await q.answer(tr('Already decided.'))
        await _say_under(ctx, q.message.chat.id, q.message.message_id, '')
        return
    if post is None:
        await q.answer(tr('This post is no longer in posts.yaml.'), show_alert=True)
        return
    who, tz, now = name_of(q.from_user), settings().timezone, datetime.now(timezone.utc)

    if action == D.COMMENT:
        wait_for(ctx, q.from_user.id, 'comment', draft_id)
        await q.answer()
        await ctx.bot.send_message(q.from_user.id,
                                   tr('Reply with 1–2 lines for «{id}». They go on top of the post, '
                                      'and you get a new preview.', id=post.id),
                                   reply_markup=ForceReply(selective=True, input_field_placeholder=tr('Your comment')))
        return

    if waited(ctx, q.from_user.id, 'comment') == draft_id:
        end_wait(ctx, q.from_user.id)          # decided with a button: the comment it asked for is moot
    if post.from_feed:
        await _feed_decision(update, ctx, action, d, post)
        return
    if action == D.REJECT:
        if not state.draft_move(draft_id, 'rejected', D.OPEN, by=q.from_user.id):
            await q.answer(tr('Already decided.'))
            return
        state.log_action('draft_rejected', reason=post.id, by_admin=q.from_user.id)
    elif action == D.SCHEDULE:
        if not state.draft_move(draft_id, 'approved', ('pending',), by=q.from_user.id):
            await q.answer(tr('Already decided.'))
            return
        state.log_action('draft_approved', reason=post.id, by_admin=q.from_user.id)
    elif action == D.PUBLISH:
        if not state.draft_move(draft_id, 'publishing', D.OPEN, by=q.from_user.id):
            await q.answer(tr('Already decided.'))
            return
        await q.answer(tr('Publishing…'))
        ok = await publish(ctx, post, D.compose(post, d.comment))
        if not ok:
            state.draft_move(draft_id, d.status, ('publishing',))
            await ctx.bot.send_message(q.from_user.id, tr('Could not publish «{id}»: {why}. The draft is still open.',
                                                          id=post.id, why=why_failed(post.id)))
            return
        state.draft_move(draft_id, 'published', ('publishing',))
    await q.answer()
    await retire(ctx, draft_id, D.outcome(action, who, post, tz, now))


async def _feed_decision(update: Update, ctx: ContextTypes.DEFAULT_TYPE, action: str, d, post) -> None:
    """A draft from a feed: it has no time of its own, so approval puts it in the queue.
    Publish now still respects the channel rules — breaking them takes a second, explicit press."""
    q = update.callback_query
    who, tz, now = name_of(q.from_user), settings().timezone, datetime.now(timezone.utc)
    item = state.item_by_post(post.id)
    if action == D.REJECT:
        if not state.draft_move(d.id, 'rejected', D.OPEN, by=q.from_user.id):
            await q.answer(tr('Already decided.'))
            return
        state.item_move(item.id, 'rejected', ('draft', 'queued'))
        state.log_action('draft_rejected', reason=post.id, by_admin=q.from_user.id)
        await q.answer()
        await retire(ctx, d.id, D.outcome(action, who, post, tz, now))
        return
    if not state.draft_move(d.id, 'approved', D.OPEN, by=q.from_user.id):
        await q.answer(tr('Already decided.'))
        return
    state.item_move(item.id, 'queued', ('draft',))
    state.log_action('draft_approved', reason=post.id, by_admin=q.from_user.id)
    if action == D.SCHEDULE:
        await q.answer()
        await retire(ctx, d.id, D.outcome(action, who, post, tz, now))
        return
    why = why_not_now(post.label, from_queue=False, now=now)
    if why:
        await q.answer(tr('Held by the channel rules'))
        await retire(ctx, d.id, tr('🗓 Approved by {who} — in the queue: {why}.', who=who, why=why[1]))
        await tell_held(ctx, state.item(item.id), why[1], to=[q.from_user.id])
        return
    await q.answer(tr('Publishing…'))
    if await publish_item(ctx, state.item(item.id)):
        await retire(ctx, d.id, D.outcome(action, who, post, tz, now))
    else:
        await ctx.bot.send_message(q.from_user.id, tr('Could not publish «{id}»: {why}. It waits in the queue.',
                                                      id=post.source, why=why_failed(post.id)))


def waiting_comment(ctx, user_id: int) -> bool:
    return waited(ctx, user_id, 'comment') is not None


async def on_private_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """A comment for the draft the admin pressed «Add comment» on."""
    msg = update.effective_message
    draft_id = waited(ctx, update.effective_user.id, 'comment')
    if draft_id is None:
        return
    d = state.draft(draft_id)
    post = _post(d.post_id) if d else None
    if d is None or post is None or d.status not in D.OPEN:
        end_wait(ctx, update.effective_user.id)
        await msg.reply_text(tr('That draft is already decided — nothing changed.'))
        return
    problem = D.comment_problem(post, msg.text or '')
    if problem:
        await msg.reply_text(problem + ' ' + tr('Send it again.'))
        return
    end_wait(ctx, update.effective_user.id)
    comment = msg.text.strip()
    state.draft_comment(draft_id, comment)
    if post.from_feed:                  # new text must be approved again: out of the queue until then
        item = state.item_by_post(post.id)
        state.item_move(item.id, 'draft', ('queued',))
    state.log_action('draft_comment', reason=post.id, excerpt=comment, by_admin=update.effective_user.id)
    await retire(ctx, draft_id, tr('✏️ Comment added by {who} — new preview below.', who=name_of(update.effective_user)))
    await send_previews(ctx, draft_id, post, comment)


async def cmd_drafts(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Drafts waiting for a decision or for their time."""
    if not await is_admin(ctx, update.effective_user.id):
        return
    tz = settings().timezone
    rows = []
    for d in state.drafts_in(*D.OPEN):
        post = _post(d.post_id)
        when = D.when(post, tz) if post else tr('removed from posts.yaml')
        state_word = tr('waiting for you') if d.status == 'pending' else tr('approved')
        rows.append(f'• {d.post_id} — {state_word}, {when}' + (' ' + tr('(with comment)') if d.comment else ''))
    await update.effective_message.reply_text('\n'.join(rows) if rows else tr('No open drafts.'))
