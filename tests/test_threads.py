"""1.8.1: in a channel's discussion group people write in comment threads under posts. Everything the bot says
about a message — the captcha button, warnings, notes — must appear in that thread, or the person never sees it."""
import asyncio
import types

import pytest

from bot.settings import Captcha, Probation, Settings
from tests import fresh

THREAD = 777          # the channel post mirrored into the group; its comments form the thread


@pytest.fixture()
def grp(tmp_path, monkeypatch):
    monkeypatch.setenv('BOT_TOKEN', '1:x'); monkeypatch.setenv('CHANNEL_ID', '-1001')
    monkeypatch.setenv('GROUP_ID', '-1002'); monkeypatch.setenv('ADMIN_IDS', '5')
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    main = fresh.load('main')
    main.current['settings'] = Settings(probation=Probation(messages=0))
    sent, restricted, fail = [], [], {'send': False}

    class Bot:
        id, n = 999, 100

        async def send_message(self, chat, text, reply_markup=None, **kw):
            if fail['send'] and chat == -1002:
                raise RuntimeError('Bad Request: message thread not found')
            Bot.n += 1
            rp = kw.get('reply_parameters')
            sent.append((chat, text, reply_markup, rp.message_id if rp else None))
            return types.SimpleNamespace(message_id=Bot.n)

        async def restrict_chat_member(self, chat, uid, perms, until_date=None):
            restricted.append((uid, perms.can_send_messages))

        async def get_chat(self, chat): return types.SimpleNamespace(permissions=main.captcha.ChatPermissions(can_send_messages=True), bio='')
        async def get_chat_administrators(self, g): return []
        async def ban_chat_member(self, chat, uid): sent.append(('ban', uid, None, None))
        async def unban_chat_member(self, chat, uid, only_if_banned=False): pass
        async def delete_message(self, chat, mid): pass

    ctx = types.SimpleNamespace(bot=Bot(), bot_data={}, job_queue=types.SimpleNamespace(run_once=lambda *a, **k: None))
    yield types.SimpleNamespace(main=main, state=main.state, ctx=ctx, sent=sent, restricted=restricted, fail=fail)
    fresh.drop()


def comment(g, uid, text, thread=THREAD):
    gone = []

    async def delete(): gone.append(True)
    msg = types.SimpleNamespace(
        is_automatic_forward=False, text=text, caption=None, entities=(), caption_entities=(), forward_origin=None,
        sender_chat=None, message_thread_id=thread, reply_to_message=None, media_group_id=None, message_id=900,
        photo=None, video=None, animation=None, document=None, video_note=None, contact=None, story=None, via_bot=None,
        reply_markup=None, from_user=types.SimpleNamespace(id=uid, is_bot=False, username=f'u{uid}', first_name='U'),
        delete=delete)
    asyncio.run(g.main.on_group_message(types.SimpleNamespace(effective_message=msg, edited_message=None), g.ctx))
    return bool(gone)


def test_captcha_button_appears_in_the_comment_thread(grp):
    assert comment(grp, 42, 'Hello from the comments')
    button = [s for s in grp.sent if s[0] == -1002 and s[2] is not None]
    assert len(button) == 1 and button[0][3] == THREAD                       # replied into the thread


def test_warning_appears_in_the_thread(grp):
    grp.main.current['settings'] = Settings(captcha=Captcha(enabled=False), probation=Probation(messages=0))
    assert comment(grp, 43, 'look https://spam.example')
    assert [s[3] for s in grp.sent if s[0] == -1002] == [THREAD]


def test_main_chat_messages_stay_in_the_main_chat(grp):
    comment(grp, 44, 'Hello', thread=None)
    assert [s[3] for s in grp.sent if s[0] == -1002] == [None]


def test_no_button_means_no_lockout(grp):
    """If the button cannot be shown, nobody can pass the captcha — the person must not stay read-only or be removed."""
    grp.fail['send'] = True
    assert not comment(grp, 45, 'Hello')                                     # message stays
    assert grp.restricted[-1] == (45, True) and not grp.state.captcha_open(45)
    asyncio.run(grp.main.captcha.captcha_tick(grp.ctx))
    assert not [s for s in grp.sent if s[0] == 'ban']
