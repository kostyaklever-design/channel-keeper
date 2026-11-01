"""Drafts — pure rules, no Telegram calls: what an admin sees, which buttons, what may happen next."""
import html
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from .i18n import tr
from .schedule import CAPTION_LIMIT, TEXT_LIMIT, Post

TTL = timedelta(hours=48)            # a draft nobody answers disappears — the news is stale by then
COMMENT_LIMIT = 500                  # «1–2 lines»; long enough for a real comment, short enough to stay one

PUBLISH, SCHEDULE, COMMENT, REJECT, RETELL = 'pub', 'sch', 'com', 'rej', 'sum'
OPEN = ('pending', 'approved')       # a decision can still be made


def buttons(draft_id: int, feed: bool = False, retell: bool = False) -> list[list[tuple[str, str]]]:
    # A post from a feed has no time of its own: «To queue» lets the channel rules pick the moment.
    later = tr('🗓 To queue') if feed else tr('🗓 Schedule')
    rows = [[(tr('✅ Publish now'), f'd:{PUBLISH}:{draft_id}'), (later, f'd:{SCHEDULE}:{draft_id}')],
            [(tr('✏️ Add comment'), f'd:{COMMENT}:{draft_id}'), (tr('🗑 Reject'), f'd:{REJECT}:{draft_id}')]]
    if feed and retell:
        rows.append([(tr('✨ Retell in my channel\'s words'), f'd:{RETELL}:{draft_id}')])
    return rows


def parse_button(data: str) -> tuple[str, int] | None:
    parts = (data or '').split(':')
    if len(parts) != 3 or parts[0] != 'd' or parts[1] not in (PUBLISH, SCHEDULE, COMMENT, REJECT, RETELL) \
            or not parts[2].isdigit():
        return None
    return parts[1], int(parts[2])


def compose(post: Post, comment: str) -> str:
    """The text that will be published: the admin's comment on top, then the post."""
    comment = (comment or '').strip()
    if comment and post.html:
        comment = html.escape(comment, quote=False)      # the comment is plain text; the post is Telegram HTML
    return f'{comment}\n\n{post.text}' if comment else post.text


def comment_problem(post: Post, comment: str) -> str | None:
    """Why this comment cannot be used, or None."""
    comment = (comment or '').strip()
    if not comment:
        return tr('The comment is empty.')
    if len(comment) > COMMENT_LIMIT:
        return tr('The comment is {n} characters, keep it under {limit}.', n=len(comment), limit=COMMENT_LIMIT)
    limit = CAPTION_LIMIT if (post.image or post.photo_id or post.media) else TEXT_LIMIT
    total = len(compose(post, comment))
    if total > limit:
        return tr('With this comment the post is {n} characters; Telegram allows {limit}. Shorten by {cut}.',
                  n=total, limit=limit, cut=total - limit)
    return None


def when(post: Post, tz: str) -> str:
    if post.from_feed:
        return tr('from {source}', source=post.source)
    return post.at.astimezone(ZoneInfo(tz)).strftime('%d.%m %H:%M')


def header(post: Post, tz: str, comment: str = '') -> str:
    extra = '\n' + tr('With your comment on top.') if comment else ''
    if post.from_feed:
        head = (tr('📝 News from «{source}».', source=post.source) if post.label == 'news'
                else tr('📝 New post from «{source}».', source=post.source))
        return (head + extra + '\n' +
                tr('Below — exactly how it will look in the channel. Add a line of your own: a bare link says little.'))
    return (tr('📝 Draft «{id}» for {at}.', id=post.id, at=when(post, tz)) + extra + '\n' +
            tr('Below — exactly how it will look in the channel. Nothing goes out until you press a button.'))


def expired(created: float, now: datetime) -> bool:
    return now - datetime.fromtimestamp(created, timezone.utc) > TTL


def outcome(action: str, who: str, post: Post, tz: str, now: datetime) -> str:
    if action == PUBLISH:
        return tr('✅ Published by {who}.', who=who)
    if action == SCHEDULE:
        if post.from_feed:
            return tr('🗓 Approved by {who} — in the queue; goes out when the channel rules allow (/queue).', who=who)
        if post.at <= now:
            return tr('🗓 Approved by {who}. Its time has passed — it goes out within a minute.', who=who)
        return tr('🗓 Approved by {who} — goes out {at}.', who=who, at=when(post, tz))
    if action == REJECT:
        return tr('🗑 Rejected by {who}.', who=who)
    return ''
