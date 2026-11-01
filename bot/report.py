"""The weekly channel health report: what went out, what the bot cleaned up, what the AI cost.
Works without AI. Comes to owners on Monday morning, and any time with /report."""
import time
from datetime import datetime, timezone

from telegram import Update
from telegram.ext import ContextTypes

from .hygiene import news_streak
from .runtime import ai, cfg, notify_admins, settings, state

WEEK = 7 * 86400
CLEANUP = (('warn', 'warnings'), ('ban', 'bans'), ('manual_ban', 'bans by admins'), ('captcha_kicked', 'removed by captcha'),
           ('flood', 'muted for flood'), ('first_minutes', 'held in fresh posts'), ('ai_flag', 'flagged by AI'),
           ('profile_flag', 'flagged for the profile'), ('learned_flag', 'flagged by the learning filter'),
           ('review_deleted', 'deleted after your review'), ('ai_deleted', 'deleted after your review (before 1.8.6)'))


def report_text(now: float | None = None) -> str:
    now = now or time.time()
    since = now - WEEK
    posts = state.db.execute('SELECT label, COUNT(*) FROM sent WHERE published=1 AND at>=? GROUP BY label',
                             (since,)).fetchall()
    by_label = dict(posts)
    own, news = by_label.get('own', 0), by_label.get('news', 0)
    kinds = dict(state.db.execute('SELECT kind, COUNT(*) FROM actions WHERE at>=? GROUP BY kind', (since,)).fetchall())
    lines = ['📊 Channel week', '',
             f'Posts: {own + news} — {own} yours, {news} news from others']
    rules = settings().rules
    if news and rules.news_in_a_row:
        ratio = 'balanced' if news <= rules.news_in_a_row * max(own, 1) else 'too many others\' news — post something of your own'
        lines.append(f'Rule 1 : {rules.news_in_a_row}: {ratio}')
    streak = news_streak(state.history())
    if streak >= rules.news_in_a_row > 0:
        lines.append(f'Right now {streak} news in a row: the next news waits for your post')
    cleaned = [f'• {label}: {kinds[k]}' for k, label in CLEANUP if kinds.get(k)]
    lines += ['', 'Cleaned up:'] + (cleaned or ['• nothing — a quiet week'])
    from .inbox import summary
    if summary():
        lines += ['', summary()]
    waiting = state.drafts_in('pending')
    if waiting:
        lines += ['', f'Drafts waiting for you: {len(waiting)} (/drafts)']
    if settings().learning_filter:
        from .review import model
        lines += ['', f'Learning filter: {model().progress()}']
    if ai.c.on:
        calls, tokens = ai.usage()
        spaced = f'{tokens:,}'.replace(',', ' ')
        lines += ['', f'AI this month: {calls} of {ai.c.monthly_limit} requests, {spaced} tokens']
    return '\n'.join(lines)


async def cmd_report(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id not in cfg.admin_ids:
        return
    await update.effective_message.reply_text(report_text())


async def weekly(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Checked every hour: Monday, 9:00 or later in the channel's timezone, not sent this week yet."""
    local = datetime.now(timezone.utc).astimezone(settings().tz)
    week = local.strftime('%G-W%V')
    if local.weekday() != 0 or local.hour < 9 or state.get('report_week') == week:
        return
    state.put('report_week', week)
    await notify_admins(ctx, report_text(), quiet=True)
