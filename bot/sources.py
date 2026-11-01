"""Feeds from sources.yaml — pure logic, no network and no Telegram: what a source is,
where its feed lives, how an entry becomes a post, and when two entries are the same news.
"""
import hashlib
import html
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, quote_plus, urlencode, urlparse, urlunparse

import yaml

TYPES = ('youtube', 'rss', 'google_news', 'google_alerts')
MODES = ('auto', 'draft')
LABELS = ('own', 'news')          # own = your channel, blog, product; news = other people's articles
FIELDS = ('title', 'link', 'source', 'read')      # {read} = «Read on <source> →» with the link hidden in it
TITLE_LIMIT = 300
MAX_AGE = timedelta(days=3)       # an unseen entry older than this is history, not news — never posted

DEFAULT_LABEL = {'youtube': 'own', 'rss': 'own', 'google_news': 'news', 'google_alerts': 'news'}
# own: the bare link makes Telegram show the video or page card; news: a short «Read on …» instead of a long URL.
DEFAULT_TEMPLATE = {'own': '{title}\n\n{link}', 'news': '{title}\n\n{read}'}
MATERIAL_LIMIT = 6000    # characters of the entry's own text kept for the AI retelling
DEFAULT_PER_DAY = {'own': 10, 'news': 3}   # a busy news query must not fill your private chat


@dataclass(frozen=True)
class Source:
    id: str
    type: str
    url: str              # the feed address, built for youtube and google_news
    mode: str             # auto | draft; news is always draft
    label: str            # own | news
    template: str
    per_day: int
    name: str             # what admins see in drafts and /sources

    @property
    def signature(self) -> str:
        """Changes when the feed address changes — then old entries are marked as seen again, not posted."""
        return hashlib.sha1(f'{self.type}|{self.url}'.encode()).hexdigest()[:12]


@dataclass(frozen=True)
class Entry:
    title: str
    link: str
    source: str           # publisher for news, the source name otherwise
    published: datetime | None
    image: str = ''       # a picture the feed itself gives for this entry (YouTube thumbnail, article image)
    material: str = ''    # the entry's own text in the feed — for the AI retelling; never posted as is

    def keys(self) -> list[str]:
        """The same news from two feeds has the same link or the same title."""
        keys = ['l:' + norm_link(self.link)] if self.link else []
        t = norm_title(self.title)
        if len(t) >= 20:          # «Update» or «News» in two feeds is not the same news
            keys.append('t:' + t)
        return keys

    def post_id(self, source_id: str) -> str:
        return f'feed:{source_id}:{hashlib.sha1((self.link or self.title).encode()).hexdigest()[:10]}'


def feed_url(raw: dict, sid: str) -> str:
    kind = raw['type']
    if kind == 'youtube':
        channel = str(raw.get('channel') or '').strip()
        if not re.fullmatch(r'UC[\w-]{22}', channel):
            raise ValueError(f'source "{sid}": channel must be a YouTube channel id like UCxxxxxxxxxxxxxxxxxxxxxx '
                             f'(24 characters, starts with UC)')
        return f'https://www.youtube.com/feeds/videos.xml?channel_id={channel}'
    if kind == 'google_news':
        query = str(raw.get('query') or '').strip()
        if not query:
            raise ValueError(f'source "{sid}": google_news needs "query"')
        lang = str(raw.get('lang') or 'en').strip()
        country = str(raw.get('country') or 'US').strip().upper()
        return (f'https://news.google.com/rss/search?q={quote_plus(query)}'
                f'&hl={lang}&gl={country}&ceid={country}:{lang.split("-")[0]}')
    url = str(raw.get('url') or '').strip()
    if not url.startswith(('https://', 'http://')):
        raise ValueError(f'source "{sid}": "url" must start with https://')
    if kind == 'google_alerts' and 'google.' not in urlparse(url).netloc:
        raise ValueError(f'source "{sid}": google_alerts needs the RSS address from google.com/alerts')
    return url


def parse_sources(text: str | None) -> list[Source]:
    """Sources from sources.yaml text. No file / empty -> no feeds. Raises ValueError with a readable reason."""
    try:
        raw = yaml.safe_load(text or '') or {}
    except yaml.YAMLError as e:
        raise ValueError(f'sources.yaml is not valid YAML: {e}') from e
    if not isinstance(raw, dict):
        raise ValueError('sources.yaml must have "sources:" at the top')
    out, seen = [], set()
    for i, s in enumerate(raw.get('sources') or [], 1):
        if not isinstance(s, dict):
            raise ValueError(f'source #{i}: must be a block with id and type')
        sid = str(s.get('id') or '').strip()
        if not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,30}', sid):
            raise ValueError(f'source #{i}: "id" is required — small letters, digits, - or _, up to 31 characters')
        if sid in seen:
            raise ValueError(f'source "{sid}": duplicate id')
        seen.add(sid)
        kind = str(s.get('type') or '').strip()
        if kind not in TYPES:
            raise ValueError(f'source "{sid}": type must be one of {", ".join(TYPES)}')
        s = {**s, 'type': kind}
        url = feed_url(s, sid)
        label = str(s.get('label') or DEFAULT_LABEL[kind]).strip()
        if label not in LABELS:
            raise ValueError(f'source "{sid}": label must be own or news')
        mode = str(s.get('mode') or ('draft' if label == 'news' else 'auto')).strip()
        if mode not in MODES:
            raise ValueError(f'source "{sid}": mode must be auto or draft')
        if label == 'news' and mode == 'auto':
            raise ValueError(f'source "{sid}": other people\'s news always go through a draft — use mode: draft')
        template = str(s.get('template') or DEFAULT_TEMPLATE[label])
        try:
            template.format(**{f: 'x' for f in FIELDS})
        except (KeyError, IndexError, ValueError) as e:
            raise ValueError(f'source "{sid}": template may use only {{title}}, {{link}}, {{source}}, {{read}}') from e
        if '{link}' not in template and '{read}' not in template:
            raise ValueError(f'source "{sid}": template must contain {{link}} or {{read}} — a post without the link misleads readers')
        per_day = s.get('per_day', DEFAULT_PER_DAY[label])
        if not isinstance(per_day, int) or not 1 <= per_day <= 50:
            raise ValueError(f'source "{sid}": per_day must be a whole number from 1 to 50')
        name = str(s.get('name') or sid).strip()[:60]
        out.append(Source(sid, kind, url, mode, label, template, per_day, name))
    return out


# ---------- entries ----------
TAG = re.compile(r'<[^>]+>')


def clean(text: str) -> str:
    return re.sub(r'\s+', ' ', html.unescape(TAG.sub('', text or ''))).strip()


def unwrap(link: str) -> str:
    """Google Alerts wraps every link in google.com/url?url=…; readers should see the real site."""
    u = urlparse(link or '')
    if u.netloc.endswith('google.com') and u.path == '/url':
        real = parse_qs(u.query).get('url') or parse_qs(u.query).get('q')
        if real:
            return real[0]
    return link or ''


def norm_link(link: str) -> str:
    u = urlparse(unwrap(link).strip())
    query = urlencode(sorted((k, v) for k, vs in parse_qs(u.query).items() if not k.lower().startswith('utm_')
                             for v in vs))
    host = u.netloc.lower().removeprefix('www.').removeprefix('m.')
    return urlunparse(('', host, u.path.rstrip('/'), '', query, ''))[2:]


def norm_title(title: str) -> str:
    return ' '.join(re.findall(r'\w+', clean(title).lower()))


def _when(e) -> datetime | None:
    t = e.get('published_parsed') or e.get('updated_parsed')
    return datetime(*t[:6], tzinfo=timezone.utc) if t else None


def entries(parsed, source: Source) -> list[Entry]:
    """Entries of a parsed feed (feedparser result), oldest first."""
    out = []
    for e in parsed.get('entries') or []:
        title = clean(e.get('title', ''))
        link = unwrap(e.get('link', '')).strip()
        if not title and not link:
            continue
        publisher = clean((e.get('source') or {}).get('title', '')) if source.type == 'google_news' else ''
        if publisher and title.endswith(f' - {publisher}'):
            title = title[: -len(publisher) - 3].rstrip()       # Google News adds « - Publisher» to every title
        if not publisher and source.label == 'news':
            publisher = urlparse(link).netloc.removeprefix('www.')
        body = (e.get('content') or [{}])[0].get('value') or e.get('summary', '')
        material = '' if source.type == 'google_news' else clean(body)[:MATERIAL_LIMIT]   # Google News: title only
        out.append(Entry(title[:TITLE_LIMIT], link, publisher or source.name, _when(e), picture(e, body), material))
    return sorted(out, key=lambda x: x.published or datetime.min.replace(tzinfo=timezone.utc))


IMG = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.I)


def picture(e, body: str) -> str:
    """The entry's picture: media:thumbnail / media:content (YouTube, many blogs), an image enclosure,
    or the first <img> in its text. Only https addresses — Telegram fetches the picture itself."""
    candidates = [m.get('url', '') for m in (e.get('media_thumbnail') or [])]
    candidates += [m.get('url', '') for m in (e.get('media_content') or [])
                   if str(m.get('type', 'image')).startswith('image') or m.get('medium') == 'image']
    candidates += [l.get('href', '') for l in (e.get('links') or [])
                   if l.get('rel') == 'enclosure' and str(l.get('type', '')).startswith('image')]
    m = IMG.search(body or '')
    if m:
        candidates.append(html.unescape(m.group(1)))
    return next((c for c in candidates if c.startswith('https://')), '')


def too_old(entry: Entry, now: datetime) -> bool:
    return entry.published is not None and now - entry.published > MAX_AGE


def read_link(link: str, source: str, read_more: str) -> str:
    """«Read on dev.by →» with the long address hidden inside — Telegram HTML."""
    words = html.escape(read_more.format(source=source), quote=False)
    return f'<a href="{html.escape(link, quote=True)}">{words}</a>' if link else words


def render(source: Source, entry: Entry, read_more: str = 'Read on {source} →') -> str:
    """The post as Telegram HTML: title and source escaped, {link} as the address, {read} as a short link."""
    esc = lambda t: html.escape(t, quote=False)
    return source.template.format(title=esc(entry.title), link=esc(entry.link), source=esc(entry.source),
                                  read=read_link(entry.link, entry.source, read_more)).strip()
