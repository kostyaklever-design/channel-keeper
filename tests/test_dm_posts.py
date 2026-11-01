"""0.9.0: posts through the private chat — time parsing, who may post, exactly one publication."""
import asyncio
import types
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from bot.dm_rules import parse_button, parse_when, quick_time, too_long
from bot.settings import Settings
from tests import fresh

AMS = ZoneInfo('Europe/Amsterdam')
NOW = datetime(2026, 11, 3, 14, 0, tzinfo=AMS)


# ---------- pure ----------
def test_parse_when():
    assert parse_when('18:30', NOW) == NOW.replace(hour=18, minute=30)
    assert parse_when('09:00', NOW) == (NOW + timedelta(days=1)).replace(hour=9, minute=0)   # passed today
    assert parse_when('05.11 10:15', NOW) == NOW.replace(day=5, hour=10, minute=15)
    assert parse_when('02.01 10:00', NOW).year == 2027                                       # next January
    assert parse_when('18.30', NOW) == NOW.replace(hour=18, minute=30)
    for bad, why in (('tomorrow', 'like 18:30'), ('31.02 10:00', 'no such'), ('25:00', 'no such'),
                     ('01.11.2026 10:00', 'passed'), ('01.11.2030 10:00', 'year')):
        assert why in parse_when(bad, NOW)


def test_quick_times_and_limits():
    assert quick_time('h1', NOW) == NOW + timedelta(hours=1)
    assert quick_time('am', NOW) == (NOW + timedelta(days=1)).replace(hour=10, minute=0)
    assert too_long(1025, True) and too_long(1024, True) is None and too_long(4097, False)
    assert parse_button('p:now:3') == ('now', 3) and parse_button('p:boom:3') is None


# ---------- the flow on a fake Telegram ----------
@pytest.fixture()
def dm(tmp_path, monkeypatch):
    monkeypatch.setenv('BOT_TOKEN', '1:x'); monkeypatch.setenv('CHANNEL_ID', '-1001')
    monkeypatch.setenv('GROUP_ID', '-1002'); monkeypatch.setenv('ADMIN_IDS', '5')
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    main = fresh.load('main')
    main.current['settings'] = Settings(timezone='Europe/Amsterdam')
    sent = []

    class Bot:
        id, n = 999, 100

        async def send_message(self, chat, text, **kw):
            Bot.n += 1
            sent.append((chat, text, kw.get('parse_mode')))
            return types.SimpleNamespace(message_id=Bot.n)

        async def send_photo(self, chat, photo=None, caption='', **kw):
            Bot.n += 1
            sent.append((chat, f'[{photo}] {caption}', kw.get('parse_mode')))
            return types.SimpleNamespace(message_id=Bot.n)

        async def edit_message_reply_markup(self, **kw): pass
        async def get_chat_administrators(self, g): return [types.SimpleNamespace(user=types.SimpleNamespace(id=8))]

    ctx = types.SimpleNamespace(bot=Bot(), bot_data={})
    yield types.SimpleNamespace(main=main, dp=main.dm_posts, state=main.state, ctx=ctx, sent=sent)
    fresh.drop()


def write(t, uid, text=None, photo=None, caption=None):
    replies = []

    async def reply_text(x, **kw): replies.append(x)
    msg = types.SimpleNamespace(text=text, text_html=text and text.replace('bold', '<b>bold</b>'),
                                caption=caption, caption_html=caption, media_group_id=None, reply_text=reply_text,
                                photo=[types.SimpleNamespace(file_id='small'), types.SimpleNamespace(file_id=photo)] if photo else [])
    upd = types.SimpleNamespace(effective_message=msg, effective_user=types.SimpleNamespace(id=uid, username='b', first_name='B'))
    asyncio.run(t.main.on_private(upd, t.ctx))
    return replies


def press(t, data, uid=5):
    answers = []

    async def answer(text=None, show_alert=False): answers.append(text)
    q = types.SimpleNamespace(data=data, answer=answer, from_user=types.SimpleNamespace(id=uid, username='b', first_name='B'))
    asyncio.run(t.main.on_button(types.SimpleNamespace(callback_query=q), t.ctx))
    return answers


def channel(t):
    return [s for s in t.sent if s[0] == -1001]


def test_text_post_keeps_formatting_and_goes_out_once(dm):
    write(dm, 5, 'Hello bold world')
    preview = [s for s in dm.sent if s[0] == 5 and 'Hello' in s[1]]
    assert preview == [(5, 'Hello <b>bold</b> world', 'HTML')]            # preview = what the channel gets
    assert channel(dm) == []
    press(dm, 'p:now:1')
    assert channel(dm) == [(-1001, 'Hello <b>bold</b> world', 'HTML')]
    assert press(dm, 'p:now:1') == ['Already done.'] and len(channel(dm)) == 1


def test_photo_post(dm):
    write(dm, 5, photo='big', caption='Caption')
    press(dm, 'p:now:1')
    assert channel(dm) == [(-1001, '[big] Caption', 'HTML')]             # the largest size


def test_only_owners_post_group_admins_do_not(dm):
    assert write(dm, 8, 'I am a group admin') == []                       # silently ignored
    assert write(dm, 77, 'random person') == []
    assert dm.state.dm_in('new') == []
    write(dm, 5, 'Mine')
    assert press(dm, 'p:now:1', uid=8) == ['Only the channel owners can do this.'] and channel(dm) == []


def test_pick_a_time_then_publish_on_tick(dm):
    write(dm, 5, 'Later')
    press(dm, 'p:pick:1')
    assert 'like 18:30' in write(dm, 5, 'whenever')[0]                    # asked again, nothing scheduled
    write(dm, 5, '23:59')
    p = dm.state.dm(1)
    assert p.status == 'scheduled'
    asyncio.run(dm.dp.dm_tick(dm.ctx))
    assert channel(dm) == []                                              # not yet
    dm.state.db.execute('UPDATE dm_posts SET at = ?', (datetime.now(timezone.utc).timestamp() - 60,))
    asyncio.run(dm.dp.dm_tick(dm.ctx))
    asyncio.run(dm.dp.dm_tick(dm.ctx))
    assert [s[1] for s in channel(dm)] == ['Later']
    assert 'Later' not in __import__('bot.channel_queue', fromlist=['x']).queue_text()


def test_a_new_message_after_picking_time_is_a_time_not_a_post(dm):
    write(dm, 5, 'Post A')
    press(dm, 'p:pick:1')
    write(dm, 5, '18:30')
    assert len(dm.state.dm_in('new', 'scheduled')) == 1                   # «18:30» did not become a post


def test_missed_post_waits_for_the_owner(dm):
    write(dm, 5, 'Was due at night')
    press(dm, 'p:h1:1')
    dm.state.db.execute('UPDATE dm_posts SET at = ?', (datetime.now(timezone.utc).timestamp() - 3 * 3600,))
    asyncio.run(dm.dp.dm_tick(dm.ctx))
    assert dm.state.dm(1).status == 'missed' and channel(dm) == []
    press(dm, 'p:now:1')
    assert len(channel(dm)) == 1


def test_cancel_and_queue_listing(dm):
    write(dm, 5, 'Tomorrow post')
    press(dm, 'p:am:1')
    assert 'Tomorrow post' in __import__('bot.channel_queue', fromlist=['x']).queue_text()
    press(dm, 'p:x:1')
    asyncio.run(dm.dp.dm_tick(dm.ctx))
    assert dm.state.dm(1).status == 'cancelled' and channel(dm) == []


def test_too_long_is_refused(dm):
    assert 'Shorten by' in write(dm, 5, photo='big', caption='x' * 1100)[0]
    assert dm.state.dm_in('new') == []


def test_failure_reason_reaches_the_owner(dm):
    """Before 1.1.1 the owner saw «see the log» and had to dig in Railway for the reason."""
    real = dm.ctx.bot.send_message

    async def refuse_channel(chat, text, **kw):
        if chat == -1001:
            raise RuntimeError('Bad Request: need administrator rights in the channel chat')
        return await real(chat, text, **kw)
    dm.ctx.bot.send_message = refuse_channel
    write(dm, 5, 'Will fail')
    press(dm, 'p:now:1')
    told = [s[1] for s in dm.sent if s[0] == 5 and s[1].startswith('Could not publish')]
    assert told and '«Post messages»' in told[0]
    assert dm.state.dm(1).status == 'new'                                  # still there to try again
