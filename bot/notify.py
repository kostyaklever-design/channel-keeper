"""What admins are told and which buttons they get — pure functions, no Telegram calls."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

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


def action_text(kind: str, user_name: str = '', user_id: int | None = None, reason: str = '',
                excerpt: str = '') -> str:
    lines = [TITLES.get(kind, kind)]
    if user_id is not None:
        lines.append(f'Who: {user_name} (id {user_id})')
    if reason:
        lines.append(f'{"Post" if kind == "post" else "Why"}: {reason}')
    if excerpt:
        short = excerpt if len(excerpt) <= 200 else excerpt[:200] + '…'
        lines.append(f'Message: {short}')
    return '\n'.join(lines)


def buttons_for(kind: str, user_id: int) -> list[tuple[str, str]]:
    """[(label, callback_data)] under a notification."""
    if kind == 'ban':
        return [('Unban', f'{UNBAN}:{user_id}'), ('OK', f'{OK}:0')]
    if kind == 'warn':
        return [('Clear warning', f'{FORGIVE}:{user_id}'), ('OK', f'{OK}:0')]
    return []


def parse_button(data: str) -> tuple[str, int] | None:
    """(action, user id) from callback data; None for anything we did not send."""
    action, _, arg = (data or '').partition(':')
    if action not in (UNBAN, FORGIVE, OK) or not arg.lstrip('-').isdigit():
        return None
    return action, int(arg)


def log_text(actions: list[Action], tz: str = 'UTC') -> str:
    if not actions:
        return 'Nothing yet.'
    zone = ZoneInfo(tz)
    out = []
    for a in actions:
        when = datetime.fromtimestamp(a.at, timezone.utc).astimezone(zone).strftime('%d.%m %H:%M')
        who = f' {a.user_name}' if a.user_name else ''
        why = f' — {a.reason}' if a.reason else ''
        out.append(f'{when} {TITLES.get(a.kind, a.kind)}{who}{why}')
    return '\n'.join(out)
