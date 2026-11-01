"""1.10: the owners' language — from their Telegram, /lang, keeper.yaml — and the command menu."""
import asyncio
import types

import pytest

from tests import fresh


@pytest.fixture()
def bot(tmp_path, monkeypatch):
    monkeypatch.setenv('BOT_TOKEN', '1:x'); monkeypatch.setenv('ADMIN_IDS', '5')
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    for k in ('CHANNEL_ID', 'GROUP_ID'):
        monkeypatch.delenv(k, raising=False)
    main = fresh.load('main')
    from bot import language, setup
    rt = __import__('bot.runtime', fromlist=['x'])
    menus, replies = [], []

    class Bot:
        id = 999

        async def set_my_commands(self, commands, scope=None, language_code=None):
            menus.append((language_code, type(scope).__name__, [(c.command, c.description) for c in commands]))

    async def reply_text(t, **kw): replies.append(t)
    ctx = types.SimpleNamespace(bot=Bot(), bot_data={}, args=[])
    yield types.SimpleNamespace(main=main, rt=rt, language=language, setup=setup, ctx=ctx, menus=menus,
                                replies=replies, reply_text=reply_text)
    fresh.drop()


def update(b, uid=5, code='ru'):
    user = types.SimpleNamespace(id=uid, language_code=code, username='o', first_name='O', is_bot=False)
    msg = types.SimpleNamespace(reply_text=b.reply_text, chat=types.SimpleNamespace(type='private', id=uid))
    return types.SimpleNamespace(effective_user=user, effective_message=msg, effective_chat=msg.chat)


def test_owner_telegram_language_is_used(bot):
    asyncio.run(bot.language.remember(update(bot, code='ru'), bot.ctx))
    assert bot.rt.owner_lang() == 'ru'
    assert any(code is None and dict(cmds)['setup'] == 'выбрать канал и группу, проверить права'
               for code, _, cmds in bot.menus)                               # the default menu turned Russian
    asyncio.run(bot.setup.cmd_setup(update(bot), bot.ctx))
    assert bot.replies[-1].startswith('Шаг 1 из 2')


def test_strangers_do_not_change_the_language(bot):
    asyncio.run(bot.language.remember(update(bot, uid=77, code='ru'), bot.ctx))
    assert bot.rt.owner_lang() == 'en' and bot.menus == []


def test_lang_command_fixes_the_language(bot):
    bot.ctx.args = ['en']
    asyncio.run(bot.language.cmd_lang(update(bot, code='ru'), bot.ctx))
    assert bot.replies[-1] == '✅ Language: English.'
    asyncio.run(bot.language.remember(update(bot, code='ru'), bot.ctx))
    assert bot.rt.owner_lang() == 'en'                                      # /lang wins over Telegram
    bot.ctx.args = ['auto']
    asyncio.run(bot.language.cmd_lang(update(bot, code='ru'), bot.ctx))
    assert bot.rt.owner_lang() == 'ru' and bot.replies[-1] == '✅ Язык: Русский.'
    bot.ctx.args = []
    asyncio.run(bot.language.cmd_lang(update(bot), bot.ctx))
    assert bot.replies[-1].startswith('Язык: Русский.')


def test_keeper_yaml_wins(bot):
    from bot.settings import Settings
    bot.rt.current['settings'] = Settings(language='en')
    asyncio.run(bot.language.remember(update(bot, code='ru'), bot.ctx))
    assert bot.rt.owner_lang() == 'en'


def test_menu_is_set_in_both_languages_and_a_failure_is_harmless(bot):
    asyncio.run(bot.language.set_menu(bot.ctx.bot))
    assert {(code, scope) for code, scope, _ in bot.menus} == {
        (None, 'BotCommandScopeAllPrivateChats'), (None, 'BotCommandScopeAllChatAdministrators'),
        ('ru', 'BotCommandScopeAllPrivateChats'), ('ru', 'BotCommandScopeAllChatAdministrators')}
    commands = {c for _, _, cmds in bot.menus for c, _ in cmds}
    assert {'setup', 'lang', 'ban'} <= commands and all(len(d) <= 256 for _, _, cmds in bot.menus for _, d in cmds)

    async def broken(*a, **k): raise RuntimeError('network')
    bot.ctx.bot.set_my_commands = broken
    asyncio.run(bot.language.set_menu(bot.ctx.bot))                          # logs, does not raise


def test_every_menu_command_exists():
    import re
    from bot.menu import IN_GROUP, PRIVATE
    import pathlib
    code = (pathlib.Path(__file__).parent.parent / 'bot' / 'main.py').read_text(encoding='utf-8')
    handled = set(re.findall(r"CommandHandler\('(\w+)'", code))
    assert {c for c, _ in PRIVATE + IN_GROUP} <= handled


def test_posts_queue_and_inbox_speak_russian(bot):
    """1.11: the preview's buttons, the queue and the inbox summary follow the owners' language."""
    bot.rt.state.put('lang', 'ru')
    from bot import channel_queue, dm_rules, inbox
    labels = [label for row in dm_rules.buttons(1, ai=True) for label, _ in row]
    assert '✅ Опубликовать' in labels and '🌅 Завтра в 10:00' in labels and '✨ Править с ИИ' in labels
    assert channel_queue.queue_text().startswith('Очередь: пусто')
    bot.rt.state.inbox_add(-100, 1, 2, 7, 'Ann', 'hi', 'message')
    assert inbox.summary() == 'Входящие: без ответа 1, предложенных постов 0'
    bot.rt.state.put('lang', 'en')
    assert channel_queue.queue_text().startswith('Queue: empty')


def test_report_log_and_sources_speak_russian(bot):
    """1.12: the owners' reports in Russian."""
    bot.rt.state.put('lang', 'ru')
    from bot import feeds, report
    from bot.notify import log_text
    assert report.report_text().startswith('📊 Неделя канала')
    assert feeds.sources_text().startswith('Лент нет.')
    bot.rt.state.log_action('ban', 1, '@x', 'link')
    assert '⛔ Забанен, сообщение удалено' in log_text(bot.rt.state.recent_actions(5))


def test_a_member_pressing_a_button_reads_their_own_language(bot):
    """Owners in English, a member with Russian Telegram: the captcha answer is Russian."""
    from bot import captcha
    answers = []

    async def answer(text=None, show_alert=False): answers.append(text)
    q = types.SimpleNamespace(data='c:42', answer=answer,
                              from_user=types.SimpleNamespace(id=77, language_code='ru'))
    asyncio.run(captcha.on_button(types.SimpleNamespace(callback_query=q), bot.ctx, 42))
    assert answers == ['Эта кнопка для другого человека.']
    q.from_user.language_code = 'de'
    asyncio.run(captcha.on_button(types.SimpleNamespace(callback_query=q), bot.ctx, 42))
    assert answers[-1] == 'This button is for someone else.'
