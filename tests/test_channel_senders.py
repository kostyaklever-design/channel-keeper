"""Messages «on behalf of a channel»: the channel is the author, not Telegram's shared service account.
Before 0.7.1 such messages skipped the captcha and a ban hit the service account (id 136817688)."""
import asyncio
import importlib
import types

import pytest

from tests import fresh

from bot.settings import Settings, parse_settings

CHANNEL_BOT = 136817688          # what Telegram puts in from_user for every message sent as a channel
SPAM_CHANNEL = -1009999


def test_settings():
    assert parse_settings('').channel_messages == 'block'
    assert parse_settings('').captcha.seconds == 120
    assert parse_settings('channel_messages: Check').channel_messages == 'check'
    with pytest.raises(ValueError, match='block or check'):
        parse_settings('channel_messages: allow')
    s = Settings()
    assert 'tg://user' not in s.html('warn', SPAM_CHANNEL, '@spam_ch')     # a channel cannot be mentioned
    assert 'tg://user?id=7' in s.html('warn', 7, 'Ann')


@pytest.fixture()
def group(tmp_path, monkeypatch):
    monkeypatch.setenv('BOT_TOKEN', '1:x'); monkeypatch.setenv('CHANNEL_ID', '-1001')
    monkeypatch.setenv('GROUP_ID', '-1002'); monkeypatch.setenv('ADMIN_IDS', '5')
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    fresh.drop()
    main = importlib.import_module('bot.main')
    calls = []

    class Bot:
        id, n = 999, 100

        async def send_message(self, chat, text, **kw):
            Bot.n += 1
            calls.append(('send', chat, text))
            return types.SimpleNamespace(message_id=Bot.n)

        async def ban_chat_member(self, chat, uid): calls.append(('ban_member', uid))
        async def unban_chat_member(self, chat, uid, only_if_banned=False): calls.append(('unban_member', uid))
        async def ban_chat_sender_chat(self, chat, cid): calls.append(('ban_channel', cid))
        async def unban_chat_sender_chat(self, chat, cid): calls.append(('unban_channel', cid))
        async def restrict_chat_member(self, *a): calls.append(('restrict',) + a[1:2])
        async def get_chat_administrators(self, g): return []

    jobs = types.SimpleNamespace(run_once=lambda *a, **k: None)
    ctx = types.SimpleNamespace(bot=Bot(), bot_data={}, job_queue=jobs)
    yield types.SimpleNamespace(main=main, rt=main.state, ctx=ctx, calls=calls)
    fresh.drop()


def as_channel(g, text='hello', chat_id=SPAM_CHANNEL):
    deleted = []

    async def delete(): deleted.append(True)
    msg = types.SimpleNamespace(
        is_automatic_forward=False, text=text, caption=None, entities=(), caption_entities=(), forward_origin=None,
        sender_chat=types.SimpleNamespace(id=chat_id, username='spam_ch', title='Spam'),
        from_user=types.SimpleNamespace(id=CHANNEL_BOT, is_bot=True, username='Channel_Bot', first_name='Channel'),
        delete=delete)
    asyncio.run(g.main.on_group_message(types.SimpleNamespace(effective_message=msg), g.ctx))
    return bool(deleted)


def test_block_mode_warns_then_bans_the_channel_not_the_service_account(group):
    assert as_channel(group)                                        # deleted even without a link
    assert as_channel(group)
    assert ('ban_channel', SPAM_CHANNEL) in group.calls
    assert not any(c[0] in ('ban_member', 'restrict') and CHANNEL_BOT in c for c in group.calls)
    assert group.rt.recent_actions(1)[0].reason == 'message on behalf of a channel'


def test_check_mode_lets_clean_channel_messages_through(group):
    group.main.current['settings'] = Settings(channel_messages='check')
    assert not as_channel(group, 'Nice post, thanks')
    assert as_channel(group, 'see https://spam.example')
    assert as_channel(group, 'again https://spam.example')
    assert ('ban_channel', SPAM_CHANNEL) in group.calls


def test_warnings_are_per_channel(group):
    as_channel(group, chat_id=-1007)
    as_channel(group, chat_id=-1008)                                # another channel: its first warning
    assert not any(c[0] == 'ban_channel' for c in group.calls)


def test_own_channel_and_anonymous_admin_are_never_touched(group):
    assert not as_channel(group, chat_id=-1001)
    assert not as_channel(group, chat_id=-1002)


def test_unban_button_lifts_a_channel_ban(group):
    answers = []

    async def answer(text=None, show_alert=False): answers.append(text)
    async def edit(*a, **k): pass
    q = types.SimpleNamespace(data=f'unban:{SPAM_CHANNEL}', answer=answer, edit_message_text=edit,
                              from_user=types.SimpleNamespace(id=5, username='boss', first_name='B'),
                              message=types.SimpleNamespace(text='x', chat=types.SimpleNamespace(id=5), message_id=1))
    asyncio.run(group.main.on_button(types.SimpleNamespace(callback_query=q), group.ctx))
    assert ('unban_channel', SPAM_CHANNEL) in group.calls
