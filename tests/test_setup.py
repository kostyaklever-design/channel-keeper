"""1.0.0: /setup — the bot starts with only BOT_TOKEN, the owner picks the channel and group with buttons."""
import asyncio
import time
import types

import pytest

from bot.config import Config
from tests import fresh


def test_only_the_token_is_required(monkeypatch):
    for k in ('CHANNEL_ID', 'GROUP_ID', 'ADMIN_IDS'):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv('BOT_TOKEN', '1:x')
    c = Config.from_env()
    assert (c.channel_id, c.group_id, c.admin_ids) == (None, None, set())
    monkeypatch.delenv('BOT_TOKEN')
    with pytest.raises(SystemExit, match='BOT_TOKEN'):
        Config.from_env()


@pytest.fixture()
def bot(tmp_path, monkeypatch):
    for k in ('CHANNEL_ID', 'GROUP_ID', 'ADMIN_IDS'):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv('BOT_TOKEN', '1:x')
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    main = fresh.load('main')
    sent = []
    rights = {'post': True, 'delete': True, 'restrict': False}

    class Bot:
        id, n = 999, 100

        async def send_message(self, chat, text, reply_markup=None, **kw):
            Bot.n += 1
            sent.append((chat, text, reply_markup))
            return types.SimpleNamespace(message_id=Bot.n)

        async def get_chat_member(self, chat, uid):
            return types.SimpleNamespace(can_post_messages=rights['post'], can_delete_messages=rights['delete'],
                                         can_restrict_members=rights['restrict'])

        async def get_chat(self, chat):
            return types.SimpleNamespace(linked_chat_id=-1002 if chat == -1001 else None)

        async def get_chat_administrators(self, g): return []

    ctx = types.SimpleNamespace(bot=Bot(), bot_data={})
    yield types.SimpleNamespace(main=main, setup=main.setup, rt=main.setup, state=main.state, cfg=main.cfg,
                                ctx=ctx, sent=sent, rights=rights, tmp=tmp_path)
    fresh.drop()


def command(b, uid, chat_type='private', chat_id=None, title='G'):
    replies = []

    async def reply_text(t, reply_markup=None, **kw): replies.append((t, reply_markup))
    upd = types.SimpleNamespace(
        effective_message=types.SimpleNamespace(reply_text=reply_text),
        effective_user=types.SimpleNamespace(id=uid),
        effective_chat=types.SimpleNamespace(type=chat_type, id=chat_id or uid, title=title))
    asyncio.run(b.setup.cmd_setup(upd, b.ctx))
    return replies


def made_admin(b, chat_id, kind, title, status='administrator'):
    cm = types.SimpleNamespace(chat=types.SimpleNamespace(id=chat_id, type=kind, title=title),
                               new_chat_member=types.SimpleNamespace(status=status))
    asyncio.run(b.setup.on_my_chat_member(types.SimpleNamespace(my_chat_member=cm), b.ctx))


def press(b, data, uid):
    answers = []

    async def answer(text=None, show_alert=False): answers.append(text)
    q = types.SimpleNamespace(data=data, answer=answer, from_user=types.SimpleNamespace(id=uid))
    asyncio.run(b.main.on_button(types.SimpleNamespace(callback_query=q), b.ctx))
    return answers


def buttons(markup):
    return [btn.callback_data for row in markup.inline_keyboard for btn in row]


def test_first_person_becomes_owner_then_strangers_are_ignored(bot):
    replies = command(bot, 5)
    assert 'owner' in replies[0][0] and bot.cfg.admin_ids == {5}
    assert command(bot, 77) == []
    assert bot.state.get('owners') == '5'


def test_two_presses_pick_channel_and_group(bot):
    command(bot, 5)
    made_admin(bot, -1001, 'channel', 'My channel')
    made_admin(bot, -1002, 'supergroup', 'Its chat')
    made_admin(bot, -1003, 'supergroup', 'Another chat')
    step1 = command(bot, 5)[-1]
    assert buttons(step1[1]) == ['s:ch:-1001']
    press(bot, 's:ch:-1001', 5)
    step2 = bot.sent[-1]
    assert buttons(step2[2])[0] == 's:gr:-1002' and '⭐' in step2[2].inline_keyboard[0][0].text   # linked one first
    press(bot, 's:gr:-1002', 5)
    assert (bot.cfg.channel_id, bot.cfg.group_id) == (-1001, -1002)
    assert -1002 in bot.main.GROUP.chat_ids                       # moderation starts without a restart
    report = bot.sent[-1][1]
    assert '✅ Channel: can post' in report and '⚠️ Group: turn on «Ban users»' in report


def test_choice_survives_a_restart(bot, monkeypatch):
    command(bot, 5)
    made_admin(bot, -1001, 'channel', 'C'); made_admin(bot, -1002, 'supergroup', 'G')
    press(bot, 's:ch:-1001', 5); press(bot, 's:gr:-1002', 5)
    again = fresh.load('runtime')
    assert (again.cfg.channel_id, again.cfg.group_id, again.cfg.admin_ids) == (-1001, -1002, {5})


def test_strangers_cannot_press_and_lost_rights_are_reported(bot):
    command(bot, 5)
    made_admin(bot, -1001, 'channel', 'C')
    assert press(bot, 's:ch:-1001', 77) == ['Only the owner can do this.']
    bot.cfg.channel_id = -1001
    made_admin(bot, -1001, 'channel', 'C', status='left')
    assert any('no longer an admin' in s[1] for s in bot.sent)
    assert bot.state.chats_where_admin('channel') == []


def test_forwarded_channel_post_is_the_fallback(bot):
    command(bot, 5)
    assert 'Forward any post' in command(bot, 5)[-1][0]
    replies = []

    async def reply_text(t, reply_markup=None, **kw): replies.append(buttons(reply_markup))
    origin = types.SimpleNamespace(type='channel', chat=types.SimpleNamespace(id=-1001, title='C'))
    upd = types.SimpleNamespace(effective_message=types.SimpleNamespace(forward_origin=origin, reply_text=reply_text),
                                effective_user=types.SimpleNamespace(id=5))
    asyncio.run(bot.main.on_private(upd, bot.ctx))
    assert replies == [['s:ch:-1001']] and bot.state.dm_in('new') == []   # not turned into a post


def test_variables_win_over_setup(tmp_path, monkeypatch):
    monkeypatch.setenv('BOT_TOKEN', '1:x'); monkeypatch.setenv('DATA_DIR', str(tmp_path))
    monkeypatch.setenv('CHANNEL_ID', '-1009'); monkeypatch.setenv('GROUP_ID', '-1008'); monkeypatch.setenv('ADMIN_IDS', '5')
    rt = fresh.load('runtime')
    rt.state.put('channel_id', '-1001')
    rt = fresh.load('runtime')
    assert rt.cfg.channel_id == -1009 and rt.FROM_ENV == {'channel': True, 'group': True}
    fresh.drop()


def test_nothing_is_published_before_setup(bot):
    from datetime import datetime, timezone

    from bot.schedule import Post
    rt = __import__('bot.runtime', fromlist=['x'])
    assert not rt.configured()
    assert asyncio.run(rt.publish(bot.ctx, Post('a', datetime.now(timezone.utc), 'x'))) is None
    asyncio.run(bot.main.tick(bot.ctx))
    assert bot.sent == []


def test_forget_and_purge(bot):
    st = bot.state
    st.add_warning(42); st.mark_human(42); st.mark_known(42); st.log_action('warn', 42, '@x', 'link')
    st.log_action('warn', 43, '@y', 'link')
    assert st.forget_person(42) == 4
    assert st.recent_actions(10, who='42') == [] and st.recent_actions(10, who='43')
    st.db.execute('UPDATE actions SET at = ?', (time.time() - 100 * 86400,))
    assert st.forget_old_actions(time.time() - 90 * 86400) == 1


def test_channel_from_variables_goes_straight_to_the_group(tmp_path, monkeypatch):
    monkeypatch.setenv('BOT_TOKEN', '1:x'); monkeypatch.setenv('DATA_DIR', str(tmp_path))
    monkeypatch.setenv('CHANNEL_ID', '-1001'); monkeypatch.setenv('ADMIN_IDS', '5'); monkeypatch.delenv('GROUP_ID', raising=False)
    main = fresh.load('main')
    sent = []

    class Bot:
        id = 999
        async def send_message(self, chat, text, reply_markup=None, **kw):
            sent.append(text); return types.SimpleNamespace(message_id=1)
        async def get_chat(self, chat): return types.SimpleNamespace(linked_chat_id=None)
    main.state.chat_seen(-1002, 'supergroup', 'G', True)
    b = types.SimpleNamespace(main=main, setup=main.setup, ctx=types.SimpleNamespace(bot=Bot(), bot_data={}))
    command(b, 5)
    assert any(t.startswith('Step 2 of 2') for t in sent)        # the channel is not asked: CHANNEL_ID fixes it
    fresh.drop()
