"""1.7.0: join requests — the captcha before someone gets in; suspicious profiles go to the owners."""
import asyncio
import types

import pytest

from bot.settings import Settings, parse_settings
from tests import fresh


def test_setting():
    assert parse_settings('').join_requests == 'captcha'
    assert parse_settings('join_requests: owners').join_requests == 'owners'
    with pytest.raises(ValueError):
        parse_settings('join_requests: auto')


@pytest.fixture()
def grp(tmp_path, monkeypatch):
    monkeypatch.setenv('BOT_TOKEN', '1:x'); monkeypatch.setenv('CHANNEL_ID', '-1001')
    monkeypatch.setenv('GROUP_ID', '-1002'); monkeypatch.setenv('ADMIN_IDS', '5')
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    main = fresh.load('main')
    main.current['settings'] = Settings()
    log, dm_fail = [], {'on': False}

    class Bot:
        id, n = 999, 100

        async def send_message(self, chat, text, reply_markup=None, **kw):
            if dm_fail['on'] and chat == 4200:
                raise RuntimeError('Forbidden: bot can\'t initiate conversation')
            Bot.n += 1
            log.append(('send', chat, text, reply_markup))
            return types.SimpleNamespace(message_id=Bot.n)

        async def approve_chat_join_request(self, chat, uid): log.append(('approve', chat, uid, None))
        async def decline_chat_join_request(self, chat, uid): log.append(('decline', chat, uid, None))
        async def edit_message_text(self, *a, **k): pass

    ctx = types.SimpleNamespace(bot=Bot(), bot_data={})
    yield types.SimpleNamespace(main=main, j=main.joins, state=main.state, ctx=ctx, log=log, dm_fail=dm_fail)
    fresh.drop()


def request(g, uid=42, bio='', chat=-1002):
    req = types.SimpleNamespace(chat=types.SimpleNamespace(id=chat, title='Group'), bio=bio, user_chat_id=uid * 100,
                                from_user=types.SimpleNamespace(id=uid, username=f'u{uid}', first_name='U'))
    asyncio.run(g.j.on_request(types.SimpleNamespace(chat_join_request=req), g.ctx))


def press(g, data, uid):
    answers = []

    async def answer(text=None, show_alert=False): answers.append(text)
    async def edit(*a, **k): pass
    q = types.SimpleNamespace(data=data, answer=answer, edit_message_text=edit, message=None,
                              from_user=types.SimpleNamespace(id=uid, username='x', first_name='X'))
    asyncio.run(g.main.on_button(types.SimpleNamespace(callback_query=q), g.ctx))
    return answers


def test_button_in_private_then_approved_and_no_second_captcha(grp):
    request(grp)
    dm = [x for x in grp.log if x[1] == 4200]
    assert dm and dm[0][3].inline_keyboard[0][0].callback_data == 'j:me:42'
    assert press(grp, 'j:me:42', uid=77) == ['This button is for someone else.']
    assert press(grp, 'j:me:42', uid=42) == ['Welcome!']
    assert ('approve', -1002, 42, None) in grp.log and grp.state.is_human(42)   # the group captcha will not ask again
    assert press(grp, 'j:me:42', uid=42) == ['Too late — send the request again.']


def test_no_press_declines_once(grp):
    request(grp)
    grp.state.db.execute('UPDATE join_requests SET deadline = 0')
    asyncio.run(grp.j.joins_tick(grp.ctx)); asyncio.run(grp.j.joins_tick(grp.ctx))
    assert grp.log.count(('decline', -1002, 42, None)) == 1
    assert grp.state.recent_actions(1)[0].kind == 'join_declined'


def test_suspicious_profile_and_unreachable_people_go_to_owners(grp):
    request(grp, uid=43, bio='Earn 500$ a day t.me/money_now')
    ask = [x for x in grp.log if x[1] == 5]
    assert ask and 'link in the profile' in ask[0][2] and not [x for x in grp.log if x[1] == 4300]
    assert press(grp, 'j:ok:43', uid=77) == ['Only the owners can do this.']
    press(grp, 'j:no:43', uid=5)
    assert ('decline', -1002, 43, None) in grp.log
    grp.dm_fail['on'] = True
    request(grp, uid=42)
    assert any('could not send them the button' in x[2] for x in grp.log if x[1] == 5)


def test_other_chats_and_off(grp):
    request(grp, chat=-1001)                         # the channel's own requests are not ours
    grp.main.current['settings'] = Settings(join_requests='off')
    request(grp)
    assert grp.log == []
