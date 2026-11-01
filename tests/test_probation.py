"""1.3.0: newcomers' probation, the profile check, edited messages, owners' verdicts kept locally."""
import asyncio
import sqlite3
import types
from datetime import datetime, timezone

import pytest
from telegram import Chat, Message, Update, User
from telegram.ext import MessageHandler

from bot.settings import Captcha, Probation, Settings, parse_settings
from bot.state import State
from tests import fresh


def test_settings():
    assert parse_settings('').probation == Probation(2, 15) and parse_settings('').profile_check is True
    assert parse_settings('probation: off').probation.messages == 0
    with pytest.raises(ValueError):
        parse_settings('probation:\n  messages: -1\n')
    with pytest.raises(ValueError):
        parse_settings('profile_check: maybe')


def test_members_known_before_1_3_are_not_on_probation(tmp_path):
    db = sqlite3.connect(tmp_path / 'keeper.db')
    db.execute('CREATE TABLE members (user_id INTEGER PRIMARY KEY, since REAL NOT NULL)')
    db.execute('INSERT INTO members VALUES (7, 1)')
    db.commit(); db.close()
    s = State(str(tmp_path))
    assert s.clean_count(7) == 99
    s.mark_known(8)
    assert s.clean_count(8) == 0                                      # a new person starts at zero


@pytest.fixture()
def group(tmp_path, monkeypatch):
    monkeypatch.setenv('BOT_TOKEN', '1:x'); monkeypatch.setenv('CHANNEL_ID', '-1001')
    monkeypatch.setenv('GROUP_ID', '-1002'); monkeypatch.setenv('ADMIN_IDS', '5')
    monkeypatch.setenv('DATA_DIR', str(tmp_path)); monkeypatch.delenv('AI_API_KEY', raising=False)
    main = fresh.load('main')
    main.current['settings'] = Settings(captcha=Captcha(enabled=False))
    sent, deleted, bios = [], [], {}

    class Bot:
        id, n = 999, 100

        async def send_message(self, chat, text, reply_markup=None, **kw):
            Bot.n += 1
            sent.append((chat, text, reply_markup))
            return types.SimpleNamespace(message_id=Bot.n)

        async def get_chat(self, uid):
            if uid not in bios:
                raise RuntimeError('chat not found')
            return types.SimpleNamespace(bio=bios[uid])

        async def delete_message(self, chat, mid): deleted.append(mid)
        async def ban_chat_member(self, chat, uid): sent.append(('ban', uid, None))
        async def get_chat_administrators(self, g): return []

    ctx = types.SimpleNamespace(bot=Bot(), bot_data={}, job_queue=types.SimpleNamespace(run_once=lambda *a, **k: None))
    yield types.SimpleNamespace(main=main, state=main.state, ctx=ctx, sent=sent, deleted=deleted, bios=bios)
    fresh.drop()


def send(g, uid, text=None, edited=False, mid=500, **parts):
    gone = []

    async def delete(): gone.append(True)
    base = dict(is_automatic_forward=False, text=text, caption=None, entities=(), caption_entities=(), forward_origin=None,
                sender_chat=None, message_thread_id=None, reply_to_message=None, media_group_id=None, message_id=mid,
                photo=None, video=None, animation=None, document=None, video_note=None, contact=None, story=None,
                via_bot=None, reply_markup=None,
                from_user=types.SimpleNamespace(id=uid, is_bot=False, username=f'u{uid}', first_name='U'), delete=delete)
    base.update(parts)
    msg = types.SimpleNamespace(**base)
    upd = types.SimpleNamespace(effective_message=msg, edited_message=msg if edited else None)
    asyncio.run(g.main.on_group_message(upd, g.ctx))
    return bool(gone)


def test_newcomer_picture_without_words_waits_for_two_real_messages(group):
    photo = [types.SimpleNamespace(file_id='p')]
    assert send(group, 42, photo=photo)                                   # deleted
    assert send(group, 42, forward_origin=types.SimpleNamespace(type='user'))
    notes = [s for s in group.sent if s[0] == -1002 and 'pictures without words' in s[1]]
    assert len(notes) == 1                                                # told once
    assert not send(group, 42, photo=photo, caption='My cat after the vet visit')   # with words: fine, and it counts
    send(group, 42, 'ok')                                                 # too short, does not count
    assert send(group, 42, photo=photo)                                   # one real message so far: still on probation
    send(group, 42, 'Thanks for the post, very useful')
    assert not send(group, 42, photo=photo)                               # two real messages: probation over


def test_risky_things(group):
    risky = group.main.probation.risky
    ns = types.SimpleNamespace
    assert risky(ns(photo=[1], caption='')) == 'a picture or video without words'
    assert risky(ns(photo=[1], caption='hi')) is None
    assert risky(ns(via_bot=ns(id=1))) == 'a message with buttons'
    assert risky(ns(text='plain text')) is None


def test_probation_off(group):
    group.main.current['settings'] = Settings(captcha=Captcha(enabled=False), probation=Probation(messages=0))
    assert not send(group, 42, contact=types.SimpleNamespace(phone_number='1'))


def test_edit_into_spam_is_caught_and_edits_do_not_count(group):
    assert not send(group, 42, 'A perfectly normal first message here')
    assert send(group, 42, 'Now with https://spam.example', edited=True)
    assert 'added by editing' in group.state.recent_actions(1)[0].reason
    before = group.state.clean_count(42)
    send(group, 42, 'A clean edit of some long text here', edited=True)
    assert group.state.clean_count(42) == before                          # an edit is not a new message


def test_profile_with_link_goes_to_owners_and_verdicts_are_kept(group):
    group.bios[42] = 'Traffic expert 🔥 t.me/best_traffic'
    assert not send(group, 42, 'Great post, totally agree with the author', mid=777)   # stays in the chat
    asks = [s for s in group.sent if s[0] == 5 and s[1].startswith('👤')]
    assert len(asks) == 1 and 'link in the profile' in asks[0][1]
    assert group.state.known_since(42) is None
    answers = []

    async def answer(text=None, show_alert=False): answers.append(text)
    async def edit(*a, **k): pass
    q = types.SimpleNamespace(data='m:del:777:42', answer=answer, edit_message_text=edit, message=None,
                              from_user=types.SimpleNamespace(id=5, username='boss', first_name='B'))
    asyncio.run(group.main.on_button(types.SimpleNamespace(callback_query=q), group.ctx))
    assert group.deleted == [777]
    rows = group.state.db.execute('SELECT text, verdict, source FROM decisions').fetchall()
    assert rows == [('Great post, totally agree with the author', 'spam', 'profile')]


def test_keep_trusts_and_unreadable_profiles_pass(group):
    group.bios[42] = 'my site example.com'
    send(group, 42, 'A normal long question about the post?', mid=778)
    async def answer(text=None, show_alert=False): pass
    async def edit(*a, **k): pass
    q = types.SimpleNamespace(data='m:keep:778:42', answer=answer, edit_message_text=edit, message=None,
                              from_user=types.SimpleNamespace(id=5, username='boss', first_name='B'))
    asyncio.run(group.main.on_button(types.SimpleNamespace(callback_query=q), group.ctx))
    assert group.state.clean_count(42) >= 99                              # trusted: no probation, no more checks
    assert not send(group, 43, 'Someone whose profile the bot cannot read')    # get_chat fails -> no flag
    assert not [s for s in group.sent if s[0] == 5 and 'id 43' in s[1]]


def test_editing_a_private_message_does_not_make_a_second_post(tmp_path, monkeypatch):
    monkeypatch.setenv('BOT_TOKEN', '123:abc'); monkeypatch.setenv('DATA_DIR', str(tmp_path))
    main = fresh.load('main')
    app = main.build_app()
    handler = next(h for grp in app.handlers.values() for h in grp
                   if isinstance(h, MessageHandler) and h.callback is main.on_private)
    msg = Message(1, datetime.now(timezone.utc), Chat(5, 'private'), from_user=User(5, 'A', False), text='typo fixed')
    assert handler.check_update(Update(1, message=msg))
    assert not handler.check_update(Update(2, edited_message=msg))
    fresh.drop()
