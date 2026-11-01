"""Posts through the private chat — pure rules, no Telegram calls: buttons, times, limits."""
import html
import json
import re
from datetime import datetime, timedelta, timezone

from .schedule import CAPTION_LIMIT, TEXT_LIMIT

NOW, HOUR, MORNING, PICK, CANCEL, EDIT = 'now', 'h1', 'am', 'pick', 'x', 'ai'
LINKS, PIN, DELETE, AD = 'lnk', 'pin', 'del', 'ad'
ACTIONS = (NOW, HOUR, MORNING, PICK, CANCEL, EDIT, LINKS, PIN, DELETE, AD)
MORNING_HOUR = 10
PIN_CYCLE = (0, 24, 48, 168, -1)        # off, 24 h, 48 h, a week, until you unpin
DELETE_CYCLE = (0, 24, 48, 72)          # stays; ad formats 1/24, 2/48, 3/72 — never under 24 h
MAX_LINKS = 3


def next_in(cycle: tuple, current: int) -> int:
    return cycle[(cycle.index(current) + 1) % len(cycle)] if current in cycle else cycle[1]


def hours_label(h: int) -> str:
    return {0: 'off', -1: 'until unpinned', 168: '7 days'}.get(h, f'{h} h')


def buttons(post_id: int, ai: bool = False, p=None) -> list[list[tuple[str, str]]]:
    """The preview's buttons; p (a stored post) shows the current options on the labels."""
    n_links = len(json.loads(p.links)) if p is not None and p.links else 0
    pin = p.pin_hours if p is not None else 0
    delete = p.delete_hours if p is not None else 0
    ad = bool(p.ad) if p is not None else False
    last = [('🗓 Pick a time', f'p:{PICK}:{post_id}')] + ([('✨ Edit with AI', f'p:{EDIT}:{post_id}')] if ai else [])
    return [[('✅ Publish now', f'p:{NOW}:{post_id}'), ('🗑 Cancel', f'p:{CANCEL}:{post_id}')],
            [('🕐 In 1 hour', f'p:{HOUR}:{post_id}'), (f'🌅 Tomorrow {MORNING_HOUR}:00', f'p:{MORNING}:{post_id}')],
            last,
            [(f'🔗 Buttons: {n_links}', f'p:{LINKS}:{post_id}'), (f'📣 Ad label: {"on" if ad else "off"}', f'p:{AD}:{post_id}')],
            [(f'📌 Pin: {hours_label(pin)}', f'p:{PIN}:{post_id}'), (f'⏱ Delete: {hours_label(delete)}', f'p:{DELETE}:{post_id}')]]


def parse_links(text: str) -> list[tuple[str, str]] | str:
    """«Label - https://link», one per line, up to 3; «-» alone removes them. Returns the buttons or why not."""
    text = (text or '').strip()
    if text == '-':
        return []
    out = []
    for line in [l.strip() for l in text.splitlines() if l.strip()]:
        m = re.fullmatch(r'(.+?)\s+[-–—|]\s+((?:https?|tg)://\S+)', line)
        if not m:
            return f'Cannot read «{line[:40]}». Write: Button text - https://link'
        label = m.group(1).strip()
        if len(label) > 40:
            return f'«{label[:20]}…» is too long for a button — up to 40 characters.'
        out.append((label, m.group(2)))
    if not out:
        return 'Write: Button text - https://link'
    if len(out) > MAX_LINKS:
        return f'Up to {MAX_LINKS} buttons.'
    return out


def with_label(text_html: str, label: str, on: bool) -> str:
    """The ad label as the first line, in bold — EU and Russian rules both want it clear and at the start."""
    return f'<b>{html.escape(label)}</b>\n\n{text_html}' if on else text_html


def scheduled_buttons(post_id: int) -> list[list[tuple[str, str]]]:
    return [[('✅ Publish now', f'p:{NOW}:{post_id}'), ('🗑 Cancel', f'p:{CANCEL}:{post_id}')]]


def parse_button(data: str) -> tuple[str, int] | None:
    parts = (data or '').split(':')
    if len(parts) != 3 or parts[0] != 'p' or parts[1] not in ACTIONS \
            or not parts[2].isdigit():
        return None
    return parts[1], int(parts[2])


def parse_when(text: str, now: datetime) -> datetime | str:
    """`18:30` (today, or tomorrow if passed), `03.11 18:30`, `03.11.2026 18:30` in now's timezone.
    Returns the moment, or the reason it cannot be used."""
    m = re.fullmatch(r'\s*(?:(\d{1,2})\.(\d{1,2})(?:\.(\d{4}))?\s+)?(\d{1,2})[:.](\d{2})\s*', text or '')
    if not m:
        return 'Send the time like 18:30 or 03.11 18:30.'
    day, month, year, hour, minute = m.groups()
    try:
        if day:
            at = now.replace(year=int(year or now.year), month=int(month), day=int(day),
                             hour=int(hour), minute=int(minute), second=0, microsecond=0)
            if not year and at < now - timedelta(minutes=1):
                at = at.replace(year=at.year + 1)      # «03.01» in December means next January
        else:
            at = now.replace(hour=int(hour), minute=int(minute), second=0, microsecond=0)
            if at <= now:
                at += timedelta(days=1)
    except ValueError:
        return 'There is no such date or time.'
    if at <= now:
        return 'That time has passed.'
    if at - now > timedelta(days=366):
        return 'More than a year ahead — pick a closer date.'
    return at


def quick_time(action: str, now: datetime) -> datetime:
    if action == HOUR:
        # Real time, not clock time: across the autumn clock change «+1 h» on the wall clock is 2 real hours.
        return (now.astimezone(timezone.utc) + timedelta(hours=1)).astimezone(now.tzinfo)
    return (now + timedelta(days=1)).replace(hour=MORNING_HOUR, minute=0, second=0, microsecond=0)


def too_long(text_len: int, has_photo: bool) -> str | None:
    limit = CAPTION_LIMIT if has_photo else TEXT_LIMIT
    if text_len > limit:
        what = 'a photo caption' if has_photo else 'a post'
        return f'Telegram allows {limit} characters for {what}; this one has {text_len}. Shorten by {text_len - limit}.'
    return None
