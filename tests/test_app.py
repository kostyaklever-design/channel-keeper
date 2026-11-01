"""The real python-telegram-bot application is built with every handler — no network, no fakes.
Catches what fake-Telegram tests cannot: a handler or job the library no longer accepts after an upgrade."""
import warnings

import telegram
from telegram.ext import CommandHandler

from tests import fresh


def test_library_is_new_enough():
    major, minor = (int(x) for x in telegram.__bot_api_version__.split('.')[:2])
    assert (major, minor) >= (9, 2), 'channel direct messages and suggested posts need Bot API 9.2+'


def test_app_builds_without_deprecated_calls(tmp_path, monkeypatch):
    monkeypatch.setenv('BOT_TOKEN', '123:abc'); monkeypatch.setenv('DATA_DIR', str(tmp_path))
    for k in ('CHANNEL_ID', 'GROUP_ID', 'ADMIN_IDS', 'AI_API_KEY'):
        monkeypatch.delenv(k, raising=False)
    with warnings.catch_warnings():
        warnings.simplefilter('error', telegram.warnings.PTBDeprecationWarning)
        main = fresh.load('main')
        app = main.build_app()
    commands = {c for group in app.handlers.values() for h in group if isinstance(h, CommandHandler) for c in h.commands}
    assert {'setup', 'version', 'log', 'drafts', 'sources', 'queue', 'ai', 'report', 'forget', 'ban', 'unban', 'id'} <= commands
    rt = __import__('bot.runtime', fromlist=['x'])
    assert rt.under(5)['reply_parameters'].allow_sending_without_reply is True and rt.under(None) == {}
    fresh.drop()
