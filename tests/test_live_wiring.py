"""Problems an independent review found that fake-Telegram tests could not see (fixed in 1.8.0)."""
import asyncio
import types
from datetime import datetime, timezone

import pytest
from telegram import Chat, Message, Update, User
from telegram.ext import ApplicationHandlerStop, MessageHandler

from bot.settings import Captcha, Probation, Settings
from tests import fresh

NOW = datetime.now(timezone.utc)


@pytest.fixture()
def app(tmp_path, monkeypatch):
    monkeypatch.setenv('BOT_TOKEN', '123:abc'); monkeypatch.setenv('DATA_DIR', str(tmp_path))
    monkeypatch.setenv('CHANNEL_ID', '-1001'); monkeypatch.setenv('GROUP_ID', '-1002'); monkeypatch.setenv('ADMIN_IDS', '5')
    main = fresh.load('main')
    yield main, main.build_app()
    fresh.drop()


def handler_for(app, callback):
    return next(h for grp in app.handlers.values() for h in grp if isinstance(h, MessageHandler) and h.callback is callback)


def test_command_shaped_spam_in_the_group_is_moderated_first(app):
    main, application = app
    h = handler_for(application, main.moderate_command)
    assert h in application.handlers[-1]                                    # runs before any command handler
    spam = Message(1, NOW, Chat(-1002, 'supergroup'), from_user=User(42, 'S', False), text='/x buy https://spam.example',
                   entities=[__import__('telegram').MessageEntity('bot_command', 0, 2)])
    assert h.check_update(Update(1, message=spam))
    main.current['settings'] = Settings(captcha=Captcha(enabled=False), probation=Probation(messages=0))
    calls = []

    class Bot:
        id = 999
        async def send_message(self, *a, **k): return types.SimpleNamespace(message_id=1)
        async def get_chat_administrators(self, g): return []
        async def get_chat(self, uid): raise RuntimeError('no')

    async def delete(): calls.append('deleted')
    msg = types.SimpleNamespace(is_automatic_forward=False, text='/x buy https://spam.example', caption=None,
                                entities=(), caption_entities=(), forward_origin=None, sender_chat=None, message_id=3,
                                message_thread_id=None, reply_to_message=None, media_group_id=None, delete=delete,
                                photo=None, video=None, animation=None, document=None, video_note=None, contact=None,
                                story=None, via_bot=None, reply_markup=None,
                                from_user=types.SimpleNamespace(id=42, is_bot=False, username='s', first_name='S'))
    ctx = types.SimpleNamespace(bot=Bot(), bot_data={}, job_queue=types.SimpleNamespace(run_once=lambda *a, **k: None))
    with pytest.raises(ApplicationHandlerStop):                             # removed: no command runs after it
        asyncio.run(main.moderate_command(types.SimpleNamespace(effective_message=msg, edited_message=None), ctx))
    assert calls == ['deleted']


def test_inbox_ignores_service_messages_and_edited_commands_are_ignored(app):
    main, application = app
    inbox = handler_for(application, main.inbox.on_message)
    service = Message(1, NOW, Chat(-1005, 'supergroup', is_direct_messages=True), new_chat_title='x')
    assert not inbox.check_update(Update(1, message=service))
    from telegram.ext import CommandHandler
    ban = next(h for grp in application.handlers.values() for h in grp if isinstance(h, CommandHandler) and 'ban' in h.commands)
    cmd = Message(2, NOW, Chat(-1002, 'supergroup'), from_user=User(5, 'A', False), text='/ban',
                  entities=[__import__('telegram').MessageEntity('bot_command', 0, 4)])
    assert ban.filters.check_update(Update(2, message=cmd))
    assert not ban.filters.check_update(Update(3, edited_message=cmd))    # an edited /ban never runs again


def test_edited_channel_post_does_not_reopen_the_window(app):
    main, _ = app
    ctx = types.SimpleNamespace(bot_data={})
    post = types.SimpleNamespace(is_automatic_forward=True, message_id=777)
    asyncio.run(main.on_group_message(types.SimpleNamespace(effective_message=post, edited_message=None), ctx))
    first = ctx.bot_data['fresh_posts'][777]
    ctx.bot_data['fresh_posts'][777] = first - 1000
    asyncio.run(main.on_group_message(types.SimpleNamespace(effective_message=post, edited_message=post), ctx))
    assert ctx.bot_data['fresh_posts'][777] == first - 1000


def test_one_open_review_per_person(app):
    main, _ = app
    main.state.review_add(1, 42, 'ad', 'profile')
    assert main.state.review_open(42) and not main.state.review_open(43)
    main.state.review_decide(1, 42, 'spam')
    assert not main.state.review_open(42)
