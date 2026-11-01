"""1.4.0: an ad post through the private chat — link buttons, the ad label, pin with a timer, auto-delete."""
import asyncio
import types

import pytest

from bot.dm_rules import DELETE_CYCLE, PIN_CYCLE, next_in, parse_links, with_label
from bot.settings import Settings, parse_settings
from tests import fresh


def test_parse_links():
    assert parse_links('Buy - https://shop.example\nChat | tg://resolve?domain=x') == \
        [('Buy', 'https://shop.example'), ('Chat', 'tg://resolve?domain=x')]
    assert parse_links('-') == []
    assert 'Cannot read' in parse_links('just text')
    assert 'Up to 3' in parse_links('\n'.join(f'B{i} - https://x.example/{i}' for i in range(4)))
    assert 'too long' in parse_links('x' * 41 + ' - https://x.example')


def test_cycles_and_label():
    assert next_in(PIN_CYCLE, 0) == 24 and next_in(PIN_CYCLE, -1) == 0
    assert min(h for h in DELETE_CYCLE if h) >= 24               # never under 24 h: ad formats and paid posts
    assert with_label('Text', 'Реклама', True) == '<b>Реклама</b>\n\nText'
    assert with_label('Text', 'Реклама', False) == 'Text'
    assert parse_settings('ad_label: Реклама').ad_label == 'Реклама'
    assert parse_settings('ad_label:').ad_label == 'Advertisement'      # empty = the default, never «None»


@pytest.fixture()
def dm(tmp_path, monkeypatch):
    monkeypatch.setenv('BOT_TOKEN', '1:x'); monkeypatch.setenv('CHANNEL_ID', '-1001')
    monkeypatch.setenv('GROUP_ID', '-1002'); monkeypatch.setenv('ADMIN_IDS', '5')
    monkeypatch.setenv('DATA_DIR', str(tmp_path)); monkeypatch.delenv('AI_API_KEY', raising=False)
    main = fresh.load('main')
    main.current['settings'] = Settings(timezone='Europe/Amsterdam', ad_label='Реклама')
    log = []
    rights = {'pin': True}

    class Bot:
        id, n = 999, 100

        async def send_message(self, chat, text, reply_markup=None, **kw):
            Bot.n += 1
            log.append(('send', chat, text, reply_markup))
            return types.SimpleNamespace(message_id=Bot.n)

        async def pin_chat_message(self, chat, mid, disable_notification=False):
            if not rights['pin']:
                raise RuntimeError('Bad Request: not enough rights to manage pinned messages')
            log.append(('pin', chat, mid))

        async def unpin_chat_message(self, chat, mid): log.append(('unpin', chat, mid))
        async def delete_message(self, chat, mid): log.append(('delete', chat, mid))
        async def edit_message_reply_markup(self, **kw): pass
        async def get_chat_administrators(self, g): return []

    ctx = types.SimpleNamespace(bot=Bot(), bot_data={})
    yield types.SimpleNamespace(main=main, dp=main.dm_posts, state=main.state, ctx=ctx, log=log, rights=rights)
    fresh.drop()


def write(t, text):
    async def reply_text(x, **kw): t.log.append(('reply', 5, x, None))
    msg = types.SimpleNamespace(text=text, text_html=text, caption=None, caption_html=None, media_group_id=None,
                                photo=[], reply_text=reply_text)
    asyncio.run(t.main.on_private(types.SimpleNamespace(effective_message=msg,
                                                        effective_user=types.SimpleNamespace(id=5)), t.ctx))


def press(t, data):
    async def answer(text=None, show_alert=False): t.log.append(('answer', 5, text, None))
    q = types.SimpleNamespace(data=data, answer=answer, from_user=types.SimpleNamespace(id=5, username='b', first_name='B'))
    asyncio.run(t.main.on_button(types.SimpleNamespace(callback_query=q), t.ctx))


def channel(t):
    return [x for x in t.log if x[1] == -1001]


def test_full_ad_post(dm):
    write(dm, 'Our partner sells great coffee')
    press(dm, 'p:lnk:1')
    write(dm, 'Order - https://coffee.example')
    press(dm, 'p:ad:1')
    press(dm, 'p:pin:1')                                         # 24 h
    press(dm, 'p:del:1'); press(dm, 'p:del:1')                   # 48 h
    p = dm.state.dm(1)
    assert (p.ad, p.pin_hours, p.delete_hours) == (1, 24, 48)
    last_preview = [x for x in dm.log if x[0] == 'send' and x[1] == 5 and x[3] is not None][-1]
    assert last_preview[2].startswith('<b>Реклама</b>')         # the preview shows the label…
    assert last_preview[3].inline_keyboard[0][0].url == 'https://coffee.example'   # …and the link button first
    press(dm, 'p:now:1')
    sent, pinned = channel(dm)[0], channel(dm)[1]
    assert sent[2] == '<b>Реклама</b>\n\nOur partner sells great coffee'
    assert [b.url for row in sent[3].inline_keyboard for b in row] == ['https://coffee.example']   # no bot buttons
    assert pinned[0] == 'pin'
    timers = dm.state.timers_for('dm:1')
    assert [a for a, _ in timers] == ['unpin', 'delete'] and timers[0][1] < timers[1][1]
    dm.state.db.execute('UPDATE timers SET at = 0')
    asyncio.run(dm.dp.timers_tick(dm.ctx)); asyncio.run(dm.dp.timers_tick(dm.ctx))
    assert [x[0] for x in channel(dm)].count('unpin') == 1 and [x[0] for x in channel(dm)].count('delete') == 1


def test_without_pin_right_the_post_still_goes_out(dm):
    dm.rights['pin'] = False
    write(dm, 'Pinned news')
    press(dm, 'p:pin:1')
    press(dm, 'p:now:1')
    assert channel(dm)[0][0] == 'send' and dm.state.dm(1).status == 'published'
    assert any('not pinned' in x[2] and '«Edit messages»' in x[2] for x in dm.log if x[1] == 5)
    assert dm.state.timers_for('dm:1') == []                       # nothing to unpin


def test_bad_links_are_explained_and_nothing_changes(dm):
    write(dm, 'Post')
    press(dm, 'p:lnk:1')
    write(dm, 'click here')
    assert any('Cannot read' in x[2] for x in dm.log if x[0] == 'reply')
    assert dm.state.dm(1).links == ''
    write(dm, '-')                                                 # still waiting: «-» means no buttons
    assert dm.state.dm_in('new')[0].id == 1 and len(dm.state.dm_in('new')) == 1


def test_plain_post_has_no_extras(dm):
    write(dm, 'Just a post')
    press(dm, 'p:now:1')
    assert channel(dm)[0][3] is None and dm.state.timers_for('dm:1') == []
