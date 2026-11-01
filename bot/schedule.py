"""Scheduled posts from posts.yaml — pure logic, no Telegram calls."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml

CAPTION_LIMIT = 1024   # Telegram limit for a photo caption
TEXT_LIMIT = 4096      # Telegram limit for a text message
STATUSES = ('scheduled', 'draft')
GRACE = timedelta(minutes=30)  # missed by more than this -> skipped, never sent late or twice


@dataclass(frozen=True)
class Post:
    id: str
    at: datetime          # timezone-aware
    text: str
    image: str | None = None
    status: str = 'scheduled'   # scheduled | draft — a draft goes to admins first, never straight to the channel
    label: str = 'own'          # own | news — for the 1 : 3 rule; what you write yourself is own
    source: str = ''            # feed name for posts brought in from sources.yaml, '' for posts.yaml
    photo_id: str | None = None # a Telegram photo (posts sent to the bot in a private chat)
    html: bool = False          # text is Telegram HTML: bold, links and the rest kept as the admin wrote them
    links: tuple = ()           # ((label, url), …): link buttons under the post
    media: tuple = ()           # ((kind, file_id), …): a video, a GIF, or an album of photos and videos

    @property
    def from_feed(self) -> bool:
        return bool(self.source)


def load_posts(path: str, default_tz: str = 'UTC') -> list[Post]:
    with open(path, encoding='utf-8') as f:
        return parse_posts(f.read(), default_tz)


def parse_posts(text: str | None, default_tz: str = 'UTC') -> list[Post]:
    """Posts from posts.yaml text. No file / empty file -> no posts. Raises ValueError with a readable reason."""
    try:
        raw = yaml.safe_load(text or '') or {}
    except yaml.YAMLError as e:
        raise ValueError(f'posts.yaml is not valid YAML: {e}') from e
    if not isinstance(raw, dict):
        raise ValueError('posts.yaml must have "posts:" at the top')
    try:
        tz = ZoneInfo(raw.get('timezone') or default_tz)
    except (ZoneInfoNotFoundError, ValueError) as e:
        raise ValueError(f'posts.yaml: unknown timezone "{raw.get("timezone")}"') from e
    posts, seen = [], set()
    for i, p in enumerate(raw.get('posts') or [], 1):
        if not isinstance(p, dict):
            raise ValueError(f'post #{i}: must be a block with id, at and text')
        pid = str(p.get('id') or '').strip()
        if not pid:
            raise ValueError(f'post #{i}: "id" is required')
        if pid in seen:
            raise ValueError(f'post "{pid}": duplicate id')
        seen.add(pid)
        at = p.get('at')
        if isinstance(at, str):
            try:
                at = datetime.strptime(at.strip(), '%Y-%m-%d %H:%M')
            except ValueError:
                at = None
        if not isinstance(at, datetime):
            raise ValueError(f'post "{pid}": "at" must look like 2026-11-03 10:00')
        text = str(p.get('text') or '').strip()
        if not text:
            raise ValueError(f'post "{pid}": "text" is empty')
        image = str(p.get('image')).strip() if p.get('image') else None
        limit = CAPTION_LIMIT if image else TEXT_LIMIT
        if len(text) > limit:
            raise ValueError(f'post "{pid}": text is {len(text)} chars, limit is {limit}')
        status = str(p.get('status') or 'scheduled').strip().lower()
        if status not in STATUSES:
            raise ValueError(f'post "{pid}": status must be one of {", ".join(STATUSES)}, got "{status}"')
        posts.append(Post(pid, at.replace(tzinfo=tz) if at.tzinfo is None else at, text, image, status))
    return sorted(posts, key=lambda p: p.at)


def due_posts(posts: list[Post], now: datetime, is_sent) -> tuple[list[Post], list[Post]]:
    """Return (to_send, too_old_to_send) for scheduled posts not sent yet. Drafts are never here:
    they wait for an admin (see drafts.py)."""
    send, skip = [], []
    for p in posts:
        if p.status != 'scheduled' or is_sent(p.id) or p.at > now:
            continue
        (send if now - p.at <= GRACE else skip).append(p)
    return send, skip
