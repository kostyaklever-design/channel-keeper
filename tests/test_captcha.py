"""Captcha on a fake Telegram: who gets it, who may press, what happens on time-out and restart."""
import asyncio
import importlib
import types

import pytest

from tests import fresh

from bot.settings import Captcha, Settings, parse_settings



# ---------- settings ----------
def test_on_by_default_and_validated():
    assert parse_settings('').captcha.enabled is True
    assert parse_settings('captcha:\n  enabled: false\n').captcha.enabled is False
    c = parse_settings('captcha:\n  enabled: true\n  seconds: 90\n  text: "{name}, нажми за {seconds} с"\n').captcha
    assert (c.enabled, c.seconds) == (True, 90)
    assert c.html(7, 'A<b>').startswith('<a href="tg://user?id=7">A&lt;b&gt;</a>, нажми за 90 с')
    for bad in ('captcha:\n  enabled: yes please\n', 'captcha:\n  seconds: 5\n', 'captcha:\n  text: "{who}"\n',
                'captcha:\n  timeout: 60\n'):
        with pytest.raises(ValueError):
            parse_settings(bad)


# ---------- the flow ----------
@pytest.fixture()
def cap(tmp_path, monkeypatch):
    monkeypatch.setenv('BOT_TOKEN', '1:x'); monkeypatch.setenv('CHANNEL_ID', '-1001')
    monkeypatch.setenv('GROUP_ID', '-1002'); monkeypatch.setenv('ADMIN_IDS', '5')
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    fresh.drop()
    rt = importlib.import_module('bot.runtime')
    c = importlib.import_module('bot.captcha')
    rt.current['settings'] = Settings(captcha=Captcha(enabled=True, seconds=60))
    calls = []

    class Bot:
        id, n = 999, 100

        async def send_message(self, chat, text, **kw):
            Bot.n += 1
            calls.append(('send', chat, text, kw.get('reply_markup')))
            return types.SimpleNamespace(message_id=Bot.n)

        async def restrict_chat_member(self, chat, uid, perms):
            calls.append(('restrict', uid, perms.can_send_messages))

        async def ban_chat_member(self, chat, uid): calls.append(('ban', uid))
        async def unban_chat_member(self, chat, uid, only_if_banned=False): calls.append(('unban', uid))
        async def delete_message(self, chat, mid): calls.append(('delete', mid))
        async def get_chat_administrators(self, g): return [types.SimpleNamespace(user=types.SimpleNamespace(id=8))]
        async def get_chat(self, g): return types.SimpleNamespace(permissions=c.ChatPermissions(can_send_messages=True))

    ctx = types.SimpleNamespace(bot=Bot(), bot_data={})
    yield types.SimpleNamespace(rt=rt, c=c, ctx=ctx, calls=calls)
    fresh.drop()


def user(uid, bot=False):
    return types.SimpleNamespace(id=uid, is_bot=bot, username=f'u{uid}', first_name='U', full_name='U')


def write(t, uid):
    deleted = []

    async def delete(): deleted.append(uid)
    msg = types.SimpleNamespace(from_user=user(uid), delete=delete)
    stopped = asyncio.run(t.c.gate(types.SimpleNamespace(effective_message=msg), t.ctx))
    return stopped, bool(deleted)


def press(t, uid, by):
    answers = []

    async def answer(text=None, show_alert=False): answers.append(text)
    q = types.SimpleNamespace(data=t.c.button_data(uid), from_user=user(by), answer=answer)
    asyncio.run(t.c.on_button(types.SimpleNamespace(callback_query=q), t.ctx, t.c.parse_button(q.data)))
    return answers


def expire(t):
    t.rt.state.db.execute('UPDATE captchas SET deadline = 0')
    asyncio.run(t.c.captcha_tick(t.ctx))


def test_newcomer_gets_read_only_and_a_button(cap):
    asyncio.run(cap.c.on_join(cap.ctx, [user(42), user(43, bot=True), user(5)]))
    assert ('restrict', 42, False) in cap.calls
    sends = [x for x in cap.calls if x[0] == 'send']
    assert len(sends) == 1 and 'tg://user?id=42' in sends[0][2]          # bots and admins are not checked
    assert sends[0][3].inline_keyboard[0][0].callback_data == 'c:42'


def test_only_that_person_can_press_and_then_writes_forever(cap):
    asyncio.run(cap.c.on_join(cap.ctx, [user(42)]))
    assert press(cap, 42, by=77) == ['This button is for someone else.']
    assert cap.rt.state.captcha_open(42)
    assert press(cap, 42, by=42) == ['Thanks! You can write now.']
    assert ('restrict', 42, True) in cap.calls and ('delete', 101) in cap.calls
    assert write(cap, 42) == (False, False)                             # remembered: no second captcha
    assert press(cap, 42, by=42) == ['Already done.']
    expire(cap)
    assert not any(x[0] == 'ban' for x in cap.calls)                    # the press wins over the time-out


def test_old_member_is_checked_on_first_message(cap):
    assert write(cap, 50) == (True, True)                               # message deleted, captcha shown
    assert write(cap, 50) == (True, True)                               # still deleted, no second button
    assert len([x for x in cap.calls if x[0] == 'send']) == 1


def test_no_press_in_time_removes_but_allows_return(cap):
    write(cap, 50)
    expire(cap)
    assert ('ban', 50) in cap.calls and ('unban', 50) in cap.calls      # kicked, not banned forever
    assert cap.rt.state.recent_actions(1)[0].kind == 'captcha_kicked'
    expire(cap)
    assert cap.calls.count(('ban', 50)) == 1                            # once


def test_admins_and_disabled_captcha_pass(cap):
    assert write(cap, 5) == (False, False)                              # ADMIN_IDS
    assert write(cap, 8) == (False, False)                              # group admin
    cap.rt.current['settings'] = Settings(captcha=Captcha(enabled=False))
    assert write(cap, 60) == (False, False)
    asyncio.run(cap.c.on_join(cap.ctx, [user(61)]))
    assert cap.calls == []


def test_open_captcha_survives_restart(cap):
    write(cap, 50)
    from bot.state import State
    again = State(cap.rt.cfg.data_dir)                                  # what a restarted bot reads
    assert again.captcha_open(50) and again.captchas_due(10**12) == [50]


def test_without_rights_the_bot_says_so_and_does_not_hide_messages_forever(cap):
    async def refuse(*a): raise RuntimeError('not enough rights')
    cap.ctx.bot.restrict_chat_member = refuse
    assert write(cap, 50) == (False, False)                             # message stays, spam checks still run
    assert not cap.rt.state.captcha_open(50)                            # no captcha that can never be passed
