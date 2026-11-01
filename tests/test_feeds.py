"""Feeds, channel rules and the queue: pure rules first, then the flow on a fake Telegram.
The guard that matters most: other people's news never reach the channel without an admin's press."""
import asyncio
import importlib
import pathlib
import sqlite3
import types
from datetime import datetime, time, timedelta, timezone

import feedparser
import pytest

from tests import fresh as reload

from bot import hygiene as H
from bot import sources as S
from bot.settings import Settings, parse_settings
from bot.state import State

ROOT = pathlib.Path(__file__).parent.parent
NOW = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)      # 13:00 in Amsterdam
YT = 'UC' + 'a' * 22


def src(**kw) -> S.Source:
    base = {'id': 'yt', 'type': 'youtube', 'channel': YT}
    base.update(kw)
    return S.parse_sources(__import__('yaml').safe_dump({'sources': [base]}))[0]


def rss(*items, atom=False) -> bytes:
    """items: (title, link, published datetime or None[, publisher])"""
    out = []
    for it in items:
        title, link, when = it[:3]
        pub = f'<pubDate>{when:%a, %d %b %Y %H:%M:%S} +0000</pubDate>' if when else ''
        source = f'<source url="https://x.example">{it[3]}</source>' if len(it) > 3 else ''
        out.append(f'<item><title>{title}</title><link>{link}</link>{pub}{source}</item>')
    return f'<?xml version="1.0"?><rss version="2.0"><channel><title>t</title>{"".join(out)}</channel></rss>'.encode()


# ---------- sources.yaml ----------
def test_defaults_by_type():
    yt, news = src(), src(id='n', type='google_news', query='AI agents', lang='ru', country='ru')
    assert (yt.label, yt.mode) == ('own', 'auto')
    assert (news.label, news.mode) == ('news', 'draft')
    assert yt.url.endswith(f'channel_id={YT}')
    assert 'q=AI+agents' in news.url and 'hl=ru' in news.url and 'gl=RU' in news.url and 'ceid=RU:ru' in news.url


@pytest.mark.parametrize('bad, why', [
    ({'type': 'youtube', 'channel': '@voxy'}, 'channel id'),
    ({'type': 'google_news', 'query': 'x', 'mode': 'auto'}, 'always go through a draft'),
    ({'type': 'rss', 'url': 'https://a.example/feed', 'template': '{title}'}, 'must contain {link}'),
    ({'type': 'rss', 'url': 'https://a.example/feed', 'template': '{title} {body} {link}'}, 'only {title}'),
    ({'type': 'podcast', 'url': 'https://a.example'}, 'type must be'),
    ({'type': 'rss', 'url': 'ftp://a.example'}, 'https://'),
    ({'type': 'google_alerts', 'url': 'https://a.example/feed'}, 'google.com/alerts'),
    ({'type': 'rss', 'url': 'https://a.example/feed', 'per_day': 0}, 'per_day'),
])
def test_bad_sources_are_explained(bad, why):
    with pytest.raises(ValueError, match=__import__('re').escape(why)):
        src(**bad)


def test_duplicate_and_bad_ids():
    with pytest.raises(ValueError, match='duplicate'):
        S.parse_sources(f'sources:\n  - {{id: a, type: youtube, channel: {YT}}}\n  - {{id: a, type: youtube, channel: {YT}}}\n')
    with pytest.raises(ValueError, match='"id" is required'):
        S.parse_sources(f'sources:\n  - {{id: "My Feed", type: youtube, channel: {YT}}}\n')
    assert S.parse_sources('') == [] and S.parse_sources(None) == []


def test_repo_sources_yaml_is_valid():
    """Fails on GitHub if sources.yaml is broken."""
    path = ROOT / 'sources.yaml'
    if path.exists():
        S.parse_sources(path.read_text(encoding='utf-8'))


# ---------- entries ----------
def test_google_news_title_loses_publisher_and_alerts_links_are_unwrapped():
    news = src(id='n', type='google_news', query='x')
    e = S.entries(feedparser.parse(rss(('Big launch - The Verge', 'https://news.google.com/a/1', NOW, 'The Verge'))), news)[0]
    assert (e.title, e.source) == ('Big launch', 'The Verge')
    assert S.render(news, e) == 'Big launch\n\n<a href="https://news.google.com/a/1">Read on The Verge →</a>'
    alerts = src(id='al', type='google_alerts', url='https://www.google.com/alerts/feeds/1/2')
    link = 'https://www.google.com/url?rct=j&sa=t&url=https://site.example/post&ct=ga'
    e = S.entries(feedparser.parse(rss(('&lt;b&gt;AI&lt;/b&gt; agents win', link, NOW))), alerts)[0]
    assert (e.title, e.link, e.source) == ('AI agents win', 'https://site.example/post', 'site.example')


def test_same_news_has_same_keys():
    a = S.Entry('OpenAI ships a new agent toolkit today', 'https://www.site.example/p/?utm_source=x', 'a', None)
    b = S.Entry('OpenAI ships a NEW agent toolkit, today!', 'https://other.example/q', 'b', None)
    c = S.Entry('Other', 'https://site.example/p', 'c', None)
    assert set(a.keys()) & set(b.keys())               # same title
    assert set(a.keys()) & set(c.keys())               # same link without www, utm and trailing slash
    assert S.Entry('Update', 'https://x.example/1', '', None).keys() == ['l:x.example/1']   # short titles never match


def test_youtube_atom_feed():
    atom = '''<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><title>ch</title>
      <entry><title>Second</title><link rel="alternate" href="https://www.youtube.com/watch?v=2"/><published>2026-11-03T10:00:00+00:00</published></entry>
      <entry><title>First</title><link rel="alternate" href="https://www.youtube.com/watch?v=1"/><published>2026-11-02T10:00:00+00:00</published></entry>
    </feed>'''.encode()
    got = S.entries(feedparser.parse(atom), src())
    assert [e.title for e in got] == ['First', 'Second']                 # oldest first
    assert S.render(src(), got[0]) == 'First\n\nhttps://www.youtube.com/watch?v=1'


# ---------- channel rules ----------
AMS = 'Europe/Amsterdam'


def hist(*labels, last=NOW - timedelta(hours=2)):
    return [(last - timedelta(hours=i), lab) for i, lab in enumerate(labels)]     # newest first


def test_quiet_hours_cross_midnight():
    r = H.Rules()
    night = datetime(2026, 11, 3, 23, 30, tzinfo=timezone.utc)          # 00:30 in Amsterdam
    assert H.blocker(r, night, AMS, [], 'own') == (H.QUIET, 'quiet hours until 08:00')
    assert H.blocker(r, NOW, AMS, [], 'own') is None
    assert H.parse_quiet('off') is None
    with pytest.raises(ValueError):
        H.parse_quiet('25:00-08:00')


def test_daily_limit_counts_every_post_today():
    r = H.Rules(daily_limit=2, gap_minutes=0)
    assert H.blocker(r, NOW, AMS, hist('own', 'own'), 'own')[0] == H.LIMIT
    assert H.blocker(r, NOW, AMS, hist('own', 'own', last=NOW - timedelta(days=1)), 'own') is None


def test_rule_1_to_3():
    r = H.Rules(daily_limit=0, gap_minutes=0)
    assert H.blocker(r, NOW, AMS, hist('news', 'news'), 'news') is None
    assert H.blocker(r, NOW, AMS, hist('news', 'news', 'news'), 'news')[0] == H.RATIO      # 4th news in a row waits
    assert H.blocker(r, NOW, AMS, hist('news', 'news', 'news'), 'own') is None             # your own post may go
    assert H.blocker(r, NOW, AMS, hist('own', 'news', 'news', 'news'), 'news') is None     # and resets the count


def test_gap_only_for_the_queue():
    r = H.Rules(daily_limit=0)
    recent = hist('own', last=NOW - timedelta(minutes=10))
    assert H.blocker(r, NOW, AMS, recent, 'own')[0] == H.GAP
    assert H.blocker(r, NOW, AMS, recent, 'own', from_queue=False) is None


def test_rules_in_keeper_yaml():
    s = parse_settings('channel_rules:\n  daily_limit: 4\n  quiet_hours: "22:00-07:30"\n  news_in_a_row: 2\n')
    assert s.rules == H.Rules(4, (time(22), time(7, 30)), 2, 30)
    assert parse_settings('timezone: UTC').rules == H.Rules()
    for bad in ('channel_rules:\n  daily: 3\n', 'channel_rules:\n  daily_limit: -1\n', 'channel_rules:\n  quiet_hours: soon\n'):
        with pytest.raises(ValueError):
            parse_settings(bad)


def test_old_database_gets_new_columns(tmp_path):
    db = sqlite3.connect(tmp_path / 'keeper.db')
    db.execute('CREATE TABLE sent (post_id TEXT PRIMARY KEY, at REAL NOT NULL)')
    db.execute("INSERT INTO sent VALUES ('old', 1)")
    db.commit()
    db.close()
    s = State(str(tmp_path))
    assert s.is_sent('old') and s.history() == [(datetime.fromtimestamp(1, timezone.utc), 'own')]


# ---------- the flow on a fake Telegram ----------
@pytest.fixture()
def bot(tmp_path, monkeypatch):
    monkeypatch.setenv('BOT_TOKEN', '1:x'); monkeypatch.setenv('CHANNEL_ID', '-1001')
    monkeypatch.setenv('GROUP_ID', '-1002'); monkeypatch.setenv('ADMIN_IDS', '5')
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    reload.drop()
    mods = types.SimpleNamespace(**{m: importlib.import_module(f'bot.{m}') for m in ('runtime', 'channel_queue', 'draft_flow', 'feeds')})
    mods.runtime.current['settings'] = Settings(timezone=AMS, rules=H.Rules(quiet=None, gap_minutes=0))
    sent = []

    class Bot:
        id, n = 999, 100

        async def send_message(self, chat, text, **kw):
            Bot.n += 1
            sent.append((chat, text, kw.get('reply_markup')))
            return types.SimpleNamespace(message_id=Bot.n)

        async def send_photo(self, chat, photo=None, caption='', **kw): return await self.send_message(chat, caption, **kw)
        async def edit_message_reply_markup(self, **kw): pass
        async def get_chat_administrators(self, g): return []

    mods.ctx = types.SimpleNamespace(bot=Bot(), bot_data={})
    mods.sent = sent
    yield mods
    reload.drop()


def channel(b):
    return [s[1] for s in b.sent if s[0] == -1001]


def check(b, source, *items):
    asyncio.run(b.feeds.check_source(b.ctx, source, datetime.now(timezone.utc), rss(*items)))


def tick(b, n=1):
    for _ in range(n):
        asyncio.run(b.draft_flow.drafts_tick(b.ctx))
        asyncio.run(b.channel_queue.queue_tick(b.ctx))


def press(b, data, user=5):
    answers = []

    async def answer(text=None, show_alert=False): answers.append(text)
    async def edit(**kw): pass
    q = types.SimpleNamespace(data=data, from_user=types.SimpleNamespace(id=user, username='boss', first_name='B'),
                              message=types.SimpleNamespace(chat=types.SimpleNamespace(id=user), message_id=1),
                              answer=answer, edit_message_reply_markup=edit)
    upd = types.SimpleNamespace(callback_query=q)
    d = b.draft_flow.D.parse_button(data)
    if d:
        asyncio.run(b.draft_flow.on_draft_button(upd, b.ctx, *d))
    else:
        asyncio.run(b.channel_queue.on_queue_button(upd, b.ctx, *b.channel_queue.parse_button(data)))
    return answers


def fresh(n):
    return datetime.now(timezone.utc) - timedelta(minutes=n)


def test_first_check_posts_nothing_then_only_new_once(bot):
    yt = src()
    check(bot, yt, ('Old video', 'https://youtu.be/1', fresh(600)))
    tick(bot)
    assert channel(bot) == [] and bot.runtime.state.items_in('queued', 'draft') == []
    for _ in range(3):
        check(bot, yt, ('Old video', 'https://youtu.be/1', fresh(600)), ('New video', 'https://youtu.be/2', fresh(5)))
    tick(bot, 3)
    assert channel(bot) == ['New video\n\nhttps://youtu.be/2']


def test_changed_feed_address_does_not_dump_old_entries(bot):
    check(bot, src(), ('A', 'https://youtu.be/1', fresh(5)))
    check(bot, src(channel='UC' + 'b' * 22), ('B', 'https://youtu.be/9', fresh(5)))
    tick(bot)
    assert channel(bot) == []


def test_same_news_from_two_feeds_comes_once_and_never_alone(bot):
    a, b2 = src(id='a', type='google_news', query='x'), src(id='b', type='google_news', query='y')
    check(bot, a)
    check(bot, b2)
    item = ('Agents are eating software, says report', 'https://news.google.com/1', fresh(5), 'Wired')
    check(bot, a, item)
    check(bot, b2, item[:1] + ('https://news.google.com/2',) + item[2:])
    tick(bot, 5)
    previews = [s for s in bot.sent if s[0] == 5 and s[2] is not None]
    assert len(previews) == 1                       # one draft, not two
    assert channel(bot) == []                       # news never goes out without a press
    press(bot, 'd:pub:1')
    assert channel(bot) == ['Agents are eating software, says report\n\n<a href="https://news.google.com/1">Read on Wired →</a>']


def test_too_old_and_over_the_daily_cap_are_skipped(bot):
    news = src(id='n', type='google_news', query='x', per_day=2)
    check(bot, news)
    check(bot, news, *[(f'Story number {i} about something long', f'https://n.example/{i}', fresh(5)) for i in range(4)],
          ('Ancient story about something long', 'https://n.example/old', fresh(60 * 24 * 5)))
    assert len(bot.runtime.state.items_in('draft')) == 2
    f = bot.runtime.state.feed('n')
    assert (f.found, f.skipped) == (2, 3)


def test_fourth_news_in_a_row_waits_until_publish_anyway(bot):
    st = bot.runtime.state
    for i in range(3):
        st.mark_sent(f'n{i}', 'news', at=(datetime.now(timezone.utc) - timedelta(hours=3 - i)).timestamp())
    news = src(id='n', type='google_news', query='x')
    check(bot, news)
    check(bot, news, ('A fourth piece of news in a row today', 'https://n.example/4', fresh(5)))
    answers = press(bot, 'd:pub:1')
    assert answers == ['Held by the channel rules'] and channel(bot) == []
    tick(bot, 3)
    assert channel(bot) == []                                        # the queue respects 1 : 3 too
    held = [s for s in bot.sent if s[0] == 5 and s[1].startswith('⏸')]
    assert len(held) == 1 and '1 : 3' in held[0][1]                  # told once, not every minute
    press(bot, 'q:any:1')
    assert len(channel(bot)) == 1
    assert press(bot, 'q:any:1') == ['Already decided.'] and len(channel(bot)) == 1


def test_own_post_overtakes_held_news_and_unblocks_it(bot):
    st = bot.runtime.state
    for i in range(3):
        st.mark_sent(f'n{i}', 'news', at=(datetime.now(timezone.utc) - timedelta(hours=3 - i)).timestamp())
    news, yt = src(id='n', type='google_news', query='x'), src()
    check(bot, news); check(bot, yt)
    check(bot, news, ('Held news story for the queue test', 'https://n.example/h', fresh(5)))
    press(bot, 'd:sch:1')                                            # to the queue
    check(bot, yt, ('Our new video', 'https://youtu.be/7', fresh(1)))
    tick(bot)
    assert channel(bot) == ['Our new video\n\nhttps://youtu.be/7']   # own goes first
    tick(bot)
    assert channel(bot)[-1].startswith('Held news story')            # then the news is allowed


def test_quiet_hours_hold_the_queue(bot):
    bot.runtime.current['settings'] = Settings(timezone='UTC', rules=H.Rules(quiet=(time(0, 0), time(23, 59)), gap_minutes=0))
    now = datetime.now(timezone.utc).time()
    if now >= time(23, 59):
        pytest.skip('the one free minute of the day')
    yt = src()
    check(bot, yt)
    check(bot, yt, ('Night video', 'https://youtu.be/n', fresh(1)))
    tick(bot, 2)
    assert channel(bot) == []
    assert 'quiet hours' in bot.channel_queue.queue_text()


def test_skip_removes_from_queue(bot):
    st = bot.runtime.state
    for i in range(3):
        st.mark_sent(f'n{i}', 'news')
    news = src(id='n', type='google_news', query='x')
    check(bot, news)
    check(bot, news, ('Another news story nobody needs', 'https://n.example/s', fresh(5)))
    press(bot, 'd:sch:1')
    tick(bot)
    press(bot, 'q:skip:1')
    assert st.item(1).status == 'skipped' and st.draft(1).status == 'rejected'


def test_unanswered_feed_draft_expires(bot):
    news = src(id='n', type='google_news', query='x')
    check(bot, news)
    check(bot, news, ('A story that nobody answers at all', 'https://n.example/e', fresh(5)))
    bot.runtime.state.db.execute('UPDATE drafts SET created = created - 49*3600')
    tick(bot)
    assert bot.runtime.state.item(1).status == 'expired' and channel(bot) == []


def test_broken_feed_is_reported_not_fatal(bot):
    yt = src()
    asyncio.run(bot.feeds.check_source(bot.ctx, yt, NOW, b'<html>not a feed'))
    assert bot.runtime.state.feed('yt').error == 'this address is not an RSS or Atom feed'
    bot.runtime.current['sources'] = [yt]
    assert '⚠️' in bot.feeds.sources_text()


def test_stale_news_leaves_the_queue_and_drafts(bot):
    st = bot.runtime.state
    for i in range(3):
        st.mark_sent(f'n{i}', 'news')
    news = src(id='n', type='google_news', query='x')
    check(bot, news)
    check(bot, news, ('News that waits far too long in the queue', 'https://n.example/w', fresh(5)))
    press(bot, 'd:sch:1')
    st.db.execute('UPDATE items SET created = created - 73*3600')
    tick(bot)
    assert st.item(1).status == 'expired' and st.drafts_in('pending', 'approved') == [] and channel(bot) == []
