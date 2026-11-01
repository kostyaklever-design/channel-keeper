"""Channel rules — pure logic: may a post from the feeds go out right now, and if not, why and until when.

Rules apply to what the bot brings in by itself (feeds). Posts you write in posts.yaml
go out at their time and are never held, but they count toward the limits.
"""
import re
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

QUIET, LIMIT, RATIO, GAP = 'quiet', 'limit', 'ratio', 'gap'


@dataclass(frozen=True)
class Rules:
    daily_limit: int = 6                     # channel posts per day, all kinds; 0 = no limit
    quiet: tuple[time, time] | None = (time(23, 0), time(8, 0))
    news_in_a_row: int = 3                   # rule 1 : 3; 0 = off
    gap_minutes: int = 30                    # between two posts from the queue; 0 = off


def parse_quiet(value) -> tuple[time, time] | None:
    if value in (None, '', False, 'off'):
        return None
    m = re.fullmatch(r'\s*(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})\s*', str(value))
    if not m or int(m[1]) > 23 or int(m[3]) > 23 or int(m[2]) > 59 or int(m[4]) > 59:
        raise ValueError('keeper.yaml: channel_rules.quiet_hours must look like "23:00-08:00" (in quotes) or off')
    start, end = time(int(m[1]), int(m[2])), time(int(m[3]), int(m[4]))
    if start == end:
        raise ValueError('keeper.yaml: channel_rules.quiet_hours start and end are the same')
    return start, end


def parse_rules(raw) -> Rules:
    if raw is None:
        return Rules()
    if not isinstance(raw, dict):
        raise ValueError('keeper.yaml: channel_rules must be a mapping')
    known = {'daily_limit', 'quiet_hours', 'news_in_a_row', 'gap_minutes'}
    unknown = set(raw) - known
    if unknown:
        raise ValueError(f'keeper.yaml: unknown channel_rules {sorted(unknown)}; known: {sorted(known)}')
    d = Rules()
    values = {}
    for key, low, high in (('daily_limit', 0, 100), ('news_in_a_row', 0, 20), ('gap_minutes', 0, 720)):
        v = raw.get(key, getattr(d, key))
        if not isinstance(v, int) or isinstance(v, bool) or not low <= v <= high:
            raise ValueError(f'keeper.yaml: channel_rules.{key} must be a whole number from {low} to {high}')
        values[key] = v
    quiet = parse_quiet(raw['quiet_hours']) if 'quiet_hours' in raw else d.quiet
    return Rules(values['daily_limit'], quiet, values['news_in_a_row'], values['gap_minutes'])


def _in_quiet(rules: Rules, local: datetime) -> datetime | None:
    """End of the quiet period (local time) when `local` is inside it."""
    if not rules.quiet:
        return None
    start, end = rules.quiet
    t = local.time()
    inside = start <= t < end if start < end else (t >= start or t < end)
    if not inside:
        return None
    day = local.date() if t < end else local.date() + timedelta(days=1)
    return datetime.combine(day, end, local.tzinfo)


def news_streak(history: list[tuple[datetime, str]]) -> int:
    """How many news went out in a row since the last own post. history is newest first."""
    n = 0
    for _, label in history:
        if label != 'news':
            break
        n += 1
    return n


def blocker(rules: Rules, now: datetime, tz: str, history: list[tuple[datetime, str]], label: str,
            from_queue: bool = True) -> tuple[str, str] | None:
    """(code, human reason) when a post may not go out now, else None.
    history: [(published_at_utc, label)] of channel posts, newest first.
    from_queue: the gap between posts applies to the queue, not to an admin pressing Publish now."""
    zone = ZoneInfo(tz)
    local = now.astimezone(zone)
    end = _in_quiet(rules, local)
    if end:
        return QUIET, f'quiet hours until {end:%H:%M}'
    if rules.daily_limit:
        today = sum(1 for at, _ in history if at.astimezone(zone).date() == local.date())
        if today >= rules.daily_limit:
            return LIMIT, f'{today} posts today, the limit is {rules.daily_limit} — tomorrow'
    if label == 'news' and rules.news_in_a_row and news_streak(history) >= rules.news_in_a_row:
        return RATIO, (f'rule 1 : {rules.news_in_a_row}: {news_streak(history)} news in a row — '
                       f'waits for your own post')
    if from_queue and rules.gap_minutes and history:
        nxt = history[0][0] + timedelta(minutes=rules.gap_minutes)
        if now < nxt:
            return GAP, f'{rules.gap_minutes} min between posts — after {nxt.astimezone(zone):%H:%M}'
    return None
