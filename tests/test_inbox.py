"""1.5.0: messages to the channel and suggested posts come to the owners; the bot never answers by itself."""
import asyncio
import types
from datetime import datetime, timezone

import pytest
from telegram import Chat, Message, Update, User
from telegram.ext import MessageHandler

from tests import fresh

DM_CHAT = -1005


@pytest.fixture()
def box(tmp_path, monkeypatch):
    monkeypatch.setenv('BOT_TOKEN', '1:x'); monkeypatch.setenv('CHANNEL_ID', '-1001')
    monkeypatch.setenv('GROUP_ID', '-1002'); monkeypatch.setenv('ADMIN_IDS', '5')
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    main = fresh.load('main')
    log, fail = [], {'approve': False}

    class Bot:
        id, n = 999, 100

        async def send_message(self, chat, text, reply_markup=None, **kw):
            Bot.n += 1
            log.append(('send', chat, text, reply_markup, kw.get('direct_messages_topic_id')))
            return types.SimpleNamespace(message_id=Bot.n)

        async def get_chat(self, chat):
            parent = {DM_CHAT: -1001, -1009: -1777}.get(chat)
            return types.SimpleNamespace(parent_chat=types.SimpleNamespace(id=parent) if parent else None)

        async def approve_suggested_post(self, chat, mid, send_date=None):
            if fail['approve']:
                raise RuntimeError('Bad Request: not enough rights')
            log.append(('approve', chat, mid, None, None))

        async def decline_suggested_post(self, chat, mid, comment=None): log.append(('decline', chat, mid, None, None))

    ctx = types.SimpleNamespace(bot=Bot(), bot_data={})
    yield types.SimpleNamespace(main=main, ib=main.inbox, state=main.state, ctx=ctx, log=log, fail=fail)
    fresh.drop()


def incoming(b, text, uid=42, chat=DM_CHAT, mid=10, suggestion=None):
    msg = types.SimpleNamespace(chat=types.SimpleNamespace(id=chat), text=text, caption=None, message_id=mid, sender_chat=None,
                                from_user=types.SimpleNamespace(id=uid, username=f'u{uid}', first_name='U'),
                                direct_messages_topic=types.SimpleNamespace(topic_id=7), suggested_post_info=suggestion)
    asyncio.run(b.ib.on_message(types.SimpleNamespace(effective_message=msg), b.ctx))


def press(b, data, uid=5):
    answers = []

    async def answer(text=None, show_alert=False): answers.append(text)
    async def edit(*a, **k): pass
    q = types.SimpleNamespace(data=data, answer=answer, edit_message_text=edit, message=None,
                              from_user=types.SimpleNamespace(id=uid, username='boss', first_name='B'))
    asyncio.run(b.main.on_button(types.SimpleNamespace(callback_query=q), b.ctx))
    return answers


def to_owner(b):
    return [x for x in b.log if x[0] == 'send' and x[1] == 5]


def test_message_reaches_owner_and_the_owner_answers(box):
    incoming(box, 'Do you ship to Poland?')
    assert 'wrote to the channel' in to_owner(box)[0][2] and 'Poland' in to_owner(box)[0][2]
    assert not [x for x in box.log if x[1] == DM_CHAT]                  # the bot said nothing to the person
    press(box, 'i:re:1')
    prompt = box.ctx.bot_data['waits'][5][1][1]           # the answer is a reply to the bot's prompt
    msg = types.SimpleNamespace(text='Yes, from next week', text_html='Yes, from next week',
                                reply_to_message=types.SimpleNamespace(message_id=prompt),
                                reply_text=lambda *a, **k: asyncio.sleep(0))
    asyncio.run(box.main.on_private(types.SimpleNamespace(effective_message=msg,
                                                          effective_user=types.SimpleNamespace(id=5)), box.ctx))
    sent = [x for x in box.log if x[1] == DM_CHAT]
    assert sent == [('send', DM_CHAT, 'Yes, from next week', None, 7)]  # into that person's topic
    assert box.state.inbox(1).status == 'answered' and box.state.dm_in('new') == []   # not a channel post


def test_paid_suggestion_approved_once(box):
    info = types.SimpleNamespace(state='pending', price=types.SimpleNamespace(amount=150, currency='XTR'))
    incoming(box, 'Please post our event', suggestion=info, mid=11)
    assert '150 XTR' in to_owner(box)[0][2]
    press(box, 'i:ok:1')
    assert press(box, 'i:ok:1') == ['Already decided.'] and press(box, 'i:no:1') == ['Already decided.']
    assert [x[0] for x in box.log].count('approve') == 1
    assert box.state.recent_actions(1)[0].kind == 'suggestion_approved'


def test_refused_approval_stays_open(box):
    box.fail['approve'] = True
    incoming(box, 'Free suggestion', suggestion=types.SimpleNamespace(state='pending', price=None))
    press(box, 'i:ok:1')
    assert box.state.inbox(1).status == 'new'
    box.fail['approve'] = False
    press(box, 'i:no:1')
    assert ('decline', DM_CHAT, 10, None, None) in box.log


def test_other_channels_owners_and_strangers(box):
    incoming(box, 'to someone else', chat=-1009)                        # another channel's inbox
    incoming(box, 'owner typing in the app', uid=5)
    assert to_owner(box) == []
    incoming(box, 'hello')
    assert press(box, 'i:re:1', uid=77) == ['Only the owners can do this.']


def test_handler_catches_direct_messages_only(tmp_path, monkeypatch):
    monkeypatch.setenv('BOT_TOKEN', '123:abc'); monkeypatch.setenv('DATA_DIR', str(tmp_path))
    main = fresh.load('main')
    app = main.build_app()
    handler = next(h for grp in app.handlers.values() for h in grp
                   if isinstance(h, MessageHandler) and h.callback is main.inbox.on_message)
    now = datetime.now(timezone.utc)
    dm = Message(1, now, Chat(DM_CHAT, 'supergroup', is_direct_messages=True), from_user=User(42, 'A', False), text='hi')
    group = Message(2, now, Chat(-1002, 'supergroup'), from_user=User(42, 'A', False), text='hi')
    assert handler.check_update(Update(1, message=dm)) and not handler.check_update(Update(2, message=group))
    fresh.drop()
