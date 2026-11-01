"""Drafts — pure rules, no Telegram calls: what an admin sees, which buttons, what may happen next."""
import html
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from .schedule import CAPTION_LIMIT, TEXT_LIMIT, Post

TTL = timedelta(hours=48)            # a draft nobody answers disappears — the news is stale by then
COMMENT_LIMIT = 500                  # «1–2 lines»; long enough for a real comment, short enough to stay one

PUBLISH, SCHEDULE, COMMENT, REJECT, RETELL = 'pub', 'sch', 'com', 'rej', 'sum'
OPEN = ('pending', 'approved')       # a decision can still be made


def buttons(draft_id: int, feed: bool = False, retell: bool = False) -> list[list[tuple[str, str]]]:
    # A post from a feed has no time of its own: «To queue» lets the channel rules pick the moment.
    later = '🗓 To queue' if feed else '🗓 Schedule'
    rows = [[('✅ Publish now', f'd:{PUBLISH}:{draft_id}'), (later, f'd:{SCHEDULE}:{draft_id}')],
            [('✏️ Add comment', f'd:{COMMENT}:{draft_id}'), ('🗑 Reject', f'd:{REJECT}:{draft_id}')]]
    if feed and retell:
        rows.append([('✨ Retell in my channel\'s words', f'd:{RETELL}:{draft_id}')])
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
        return 'The comment is empty.'
    if len(comment) > COMMENT_LIMIT:
        return f'The comment is {len(comment)} characters, keep it under {COMMENT_LIMIT}.'
    limit = CAPTION_LIMIT if (post.image or post.photo_id or post.media) else TEXT_LIMIT
    total = len(compose(post, comment))
    if total > limit:
        return f'With this comment the post is {total} characters; Telegram allows {limit}. Shorten by {total - limit}.'
    return None


def when(post: Post, tz: str) -> str:
    if post.from_feed:
        return f'from {post.source}'
    return post.at.astimezone(ZoneInfo(tz)).strftime('%d.%m %H:%M')


def header(post: Post, tz: str, comment: str = '') -> str:
    extra = '\nWith your comment on top.' if comment else ''
    if post.from_feed:
        kind = 'News' if post.label == 'news' else 'New post'
        return (f'📝 {kind} from «{post.source}».{extra}\n'
                f'Below — exactly how it will look in the channel. Add a line of your own: a bare link says little.')
    return (f'📝 Draft «{post.id}» for {when(post, tz)}.{extra}\n'
            f'Below — exactly how it will look in the channel. Nothing goes out until you press a button.')


def expired(created: float, now: datetime) -> bool:
    return now - datetime.fromtimestamp(created, timezone.utc) > TTL


def outcome(action: str, who: str, post: Post, tz: str, now: datetime) -> str:
    if action == PUBLISH:
        return f'✅ Published by {who}.'
    if action == SCHEDULE:
        if post.from_feed:
            return f'🗓 Approved by {who} — in the queue; goes out when the channel rules allow (/queue).'
        if post.at <= now:
            return f'🗓 Approved by {who}. Its time has passed — it goes out within a minute.'
        return f'🗓 Approved by {who} — goes out {when(post, tz)}.'
    if action == REJECT:
        return f'🗑 Rejected by {who}.'
    return ''
