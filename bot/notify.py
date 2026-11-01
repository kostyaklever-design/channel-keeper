"""What admins are told and which buttons they get — pure functions, no Telegram calls."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from .i18n import tr
from .state import Action

# Button data: "<action>:<user id>". Telegram allows 64 bytes, this stays far below.
UNBAN, FORGIVE, OK = 'unban', 'forgive', 'ok'

TITLES = {
    'warn': '⚠️ Warned and deleted',
    'ban': '⛔ Banned and deleted',
    'unban': '✅ Unbanned',
    'forgive': '✅ Warning cleared',
    'manual_ban': '⛔ Banned by an admin',
    'post': '📣 Published',
    'draft_approved': '🗓 Draft approved',
    'draft_rejected': '🗑 Draft rejected',
    'draft_comment': '✏️ Draft commented',
    'feed_new': '📥 New from a feed',
    'queue_forced': '✅ Published anyway',
    'queue_skipped': '🗑 Skipped from the queue',
    'captcha_kicked': "🚪 Removed: did not press «I'm human»",
    'flood': '🔇 Read-only for flooding',
    'first_minutes': '⏳ Deleted: too soon after a post',
    'ai_flag': '🤖 Flagged by AI — waiting for an owner',
    'ai_deleted': '🗑 Deleted after an owner\'s review',
    'review_deleted': '🗑 Deleted after an owner\'s review',
    'probation': '🐣 Deleted: newcomer on probation',
    'suggested': '📝 Post suggested to the channel',
    'join_declined': '🚪 Join request declined',
    'suggestion_approved': '✅ Suggested post approved',
    'suggestion_declined': '❌ Suggested post declined',
    'profile_flag': '👤 Profile with an ad — waiting for an owner',
    'learned_flag': '🧠 Looks like spam you deleted before — waiting for an owner',
}


# The weekly report's clean-up lines: (log kind, label). Labels are translated where they are shown.
CLEANUP = (('warn', 'warnings'), ('ban', 'bans'), ('manual_ban', 'bans by admins'), ('captcha_kicked', 'removed by captcha'),
           ('flood', 'muted for flood'), ('first_minutes', 'held in fresh posts'), ('ai_flag', 'flagged by AI'),
           ('profile_flag', 'flagged for the profile'), ('learned_flag', 'flagged by the learning filter'),
           ('review_deleted', 'deleted after your review'), ('ai_deleted', 'deleted after your review (before 1.8.6)'))


def title(kind: str) -> str:
    return tr(TITLES[kind]) if kind in TITLES else kind


def action_text(kind: str, user_name: str = '', user_id: int | None = None, reason: str = '',
                excerpt: str = '') -> str:
    lines = [title(kind)]
    if user_id is not None:
        lines.append(tr('Who: {name} (id {id})', name=user_name, id=user_id))
    if reason:
        lines.append(tr('Post: {what}', what=reason) if kind == 'post' else tr('Why: {what}', what=reason))
    if excerpt:
        short = excerpt if len(excerpt) <= 200 else excerpt[:200] + '…'
        lines.append(tr('Message: {text}', text=short))
    return '\n'.join(lines)


def buttons_for(kind: str, user_id: int) -> list[tuple[str, str]]:
    """[(label, callback_data)] under a notification."""
    if kind == 'ban':
        return [(tr('Unban'), f'{UNBAN}:{user_id}'), ('OK', f'{OK}:0')]
    if kind == 'warn':
        return [(tr('Clear warning'), f'{FORGIVE}:{user_id}'), ('OK', f'{OK}:0')]
    return []


def parse_button(data: str) -> tuple[str, int] | None:
    """(action, user id) from callback data; None for anything we did not send."""
    action, _, arg = (data or '').partition(':')
    if action not in (UNBAN, FORGIVE, OK) or not arg.lstrip('-').isdigit():
        return None
    return action, int(arg)


def log_text(actions: list[Action], tz: str = 'UTC') -> str:
    if not actions:
        return tr('Nothing yet.')
    zone = ZoneInfo(tz)
    out = []
    for a in actions:
        when = datetime.fromtimestamp(a.at, timezone.utc).astimezone(zone).strftime('%d.%m %H:%M')
        who = f' {a.user_name}' if a.user_name else ''
        why = f' — {a.reason}' if a.reason else ''
        out.append(f'{when} {title(a.kind)}{who}{why}')
    return '\n'.join(out)
