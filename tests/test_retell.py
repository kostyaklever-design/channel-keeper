"""1.8.3: news posts from feeds — a short «Read on …» link, the feed's picture, and «✨ Retell» by the AI."""
import asyncio
import types
from datetime import datetime, timedelta, timezone

import feedparser
import httpx
import pytest
from telegram.error import BadRequest

from bot import sources as S
from bot.settings import Settings, parse_settings
from tests import fresh

HABR = b'''<?xml version="1.0"?><rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/"><channel><title>h</title>
<item><title>AI agents &amp; small business</title><link>https://habr.com/ru/articles/1/</link>
<description>&lt;img src="https://habrastorage.org/pic.png"&gt; Agents now answer calls for salons. Prices fell.</description>
<pubDate>%s</pubDate></item></channel></rss>'''


def habr_feed(minutes_ago=5):
    when = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    return HABR % when.strftime('%a, %d %b %Y %H:%M:%S +0000').encode()


def src(**kw):
    import yaml
    return S.parse_sources(yaml.safe_dump({'sources': [{'id': 'habr', 'type': 'rss', 'url': 'https://habr.com/rss',
                                                        'label': 'news', **kw}]}))[0]


def test_entry_picture_material_and_short_link():
    e = S.entries(feedparser.parse(habr_feed()), src())[0]
    assert e.image == 'https://habrastorage.org/pic.png'
    assert 'answer calls for salons' in e.material
    assert S.render(src(), e, 'Читать на {source} →') == \
        'AI agents &amp; small business\n\n<a href="https://habr.com/ru/articles/1/">Читать на habr.com →</a>'
    yt = b'''<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom" xmlns:media="http://search.yahoo.com/mrss/">
      <entry><title>Video</title><link rel="alternate" href="https://www.youtube.com/watch?v=1"/>
      <media:group><media:thumbnail url="https://i.ytimg.com/vi/1/hq.jpg" width="480" height="360"/></media:group>
      </entry></feed>'''
    assert S.entries(feedparser.parse(yt), src(id='yt', type='youtube', channel='UC' + 'a' * 22, label='own'))[0].image \
        == 'https://i.ytimg.com/vi/1/hq.jpg'


def test_settings_and_templates():
    s = parse_settings('read_more: "Читать на {source} →"\nai_language: Russian')
    assert (s.read_more, s.ai_language) == ('Читать на {source} →', 'Russian')
    with pytest.raises(ValueError):
        parse_settings('read_more: "{site}"')
    assert src(template='{title} {read}').template == '{title} {read}'          # {read} alone is enough


@pytest.fixture()
def bot(tmp_path, monkeypatch):
    monkeypatch.setenv('BOT_TOKEN', '1:x'); monkeypatch.setenv('CHANNEL_ID', '-1001')
    monkeypatch.setenv('GROUP_ID', '-1002'); monkeypatch.setenv('ADMIN_IDS', '5')
    monkeypatch.setenv('DATA_DIR', str(tmp_path)); monkeypatch.setenv('AI_API_KEY', 'sk-ant-k'); monkeypatch.delenv('AI_PROVIDER', raising=False)
    main = fresh.load('main')
    main.current['settings'] = Settings(read_more='Читать на {source} →', ai_language='Russian',
                                        rules=main.current['settings'].rules.__class__(quiet=None, gap_minutes=0))
    rt = __import__('bot.runtime', fromlist=['x'])
    asked = []

    def provider(request):
        asked.append(request.content.decode())
        return httpx.Response(200, json={'content': [{'type': 'text', 'text': 'Агенты отвечают на звонки салонов. Цены упали.'}],
                                         'usage': {}})
    rt.ai.transport = httpx.MockTransport(provider)
    log, broken = [], {'photo': False}

    class Bot:
        id, n = 999, 100

        def _m(self):
            Bot.n += 1
            return types.SimpleNamespace(message_id=Bot.n)

        async def send_message(self, chat, text, reply_markup=None, **kw):
            log.append(('text', chat, text, reply_markup)); return self._m()

        async def send_photo(self, chat, photo=None, caption=None, reply_markup=None, **kw):
            if broken['photo']:
                raise BadRequest('Wrong file identifier/http url specified')
            log.append(('photo', chat, f'{photo}|{caption}', reply_markup)); return self._m()

        async def edit_message_reply_markup(self, **kw): pass
        async def get_chat_administrators(self, g): return []

    ctx = types.SimpleNamespace(bot=Bot(), bot_data={})
    yield types.SimpleNamespace(main=main, feeds=main.feeds if hasattr(main, 'feeds') else __import__('bot.feeds', fromlist=['x']),
                                state=main.state, ctx=ctx, log=log, asked=asked, broken=broken)
    fresh.drop()


def bring(b, source=None, feed=None):
    source = source or src()
    asyncio.run(b.feeds.check_source(b.ctx, source, datetime.now(timezone.utc), b'<rss version="2.0"><channel></channel></rss>'))
    asyncio.run(b.feeds.check_source(b.ctx, source, datetime.now(timezone.utc), feed or habr_feed()))


def press(b, data, uid=5):
    answers = []

    async def answer(text=None, show_alert=False): answers.append(text)
    q = types.SimpleNamespace(data=data, answer=answer, message=None,
                              from_user=types.SimpleNamespace(id=uid, username='boss', first_name='B'))
    asyncio.run(b.main.on_button(types.SimpleNamespace(callback_query=q), b.ctx))
    return answers


def test_preview_has_picture_short_link_and_retell_button(bot):
    bring(bot)
    preview = [x for x in bot.log if x[0] == 'photo' and x[1] == 5][0]
    assert preview[2].startswith('https://habrastorage.org/pic.png|AI agents &amp; small business')
    assert 'Читать на habr.com →</a>' in preview[2]
    assert any('Retell' in b.text for row in preview[3].inline_keyboard for b in row)


def test_retell_replaces_the_body_and_asks_again(bot):
    bring(bot)
    assert press(bot, 'd:sum:1') == ['Retelling…']
    assert 'Russian' in bot.asked[0] and 'answer calls for salons' in bot.asked[0]       # the article text went to the AI
    item = bot.state.item(1)
    assert item.text.startswith('<b>AI agents &amp; small business</b>\n\nАгенты отвечают на звонки салонов.')
    assert item.text.endswith('Читать на habr.com →</a>')
    assert bot.state.draft(1).status == 'pending'
    assert [x for x in bot.log if x[1] == -1001] == []                                   # nothing published
    press(bot, 'd:pub:1')
    assert [x for x in bot.log if x[1] == -1001][0][2].startswith('https://habrastorage.org/pic.png|<b>AI agents')


def test_google_news_is_written_from_the_headline_with_guardrails(bot):
    gn = src(id='gn', type='google_news', query='x')
    feed = b'''<?xml version="1.0"?><rss version="2.0"><channel><item><title>Big news - Wired</title>
      <link>https://news.google.com/rss/articles/abc</link><source url="https://wired.com">Wired</source></item></channel></rss>'''
    bring(bot, gn, feed)
    assert press(bot, 'd:sum:1') == ['Retelling…']
    sent = bot.asked[0]
    assert 'ONLY a headline' in sent and 'Never invent details' in sent and 'Source: Wired' in sent
    assert bot.state.item(1).text.endswith('Читать на Wired →</a>')
    assert any('headline only' in x[2] for x in bot.log if x[1] == 5 and x[0] == 'text')    # the owner is warned


def test_broken_picture_falls_back_to_text_and_comment_is_escaped(bot):
    bring(bot)
    bot.broken['photo'] = True
    msg = types.SimpleNamespace(text='Важно: a < b', reply_text=lambda *a, **k: asyncio.sleep(0))
    press(bot, 'd:com:1')
    asyncio.run(bot.main.on_private(types.SimpleNamespace(effective_message=msg,
                                                          effective_user=types.SimpleNamespace(id=5, username='b', first_name='B')),
                                    bot.ctx))
    press(bot, 'd:pub:2' if bot.state.draft(2) else 'd:pub:1')
    out = [x for x in bot.log if x[1] == -1001]
    assert out and out[0][0] == 'text' and out[0][2].startswith('Важно: a &lt; b')
