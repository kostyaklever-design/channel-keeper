"""The owners' language (1.10): remembered from their Telegram, set with /lang, and the bot's command menu.

keeper.yaml `language:` wins over everything; /lang ru|en fixes it in the bot's memory; /lang auto goes back
to the owner's Telegram language. The command menu (the «Menu» button) is set by the bot itself at start —
no @BotFather step: the default menu in the owners' language, and a Russian one for Russian-language Telegram.
"""
from telegram import (BotCommand, BotCommandScopeAllChatAdministrators, BotCommandScopeAllPrivateChats, Update)
from telegram.ext import ContextTypes

from .i18n import LANGS, of_code, tr
from .menu import IN_GROUP, PRIVATE
from .runtime import cfg, log, owner_lang, settings, state

NAMES = {'en': 'English', 'ru': 'Русский'}



async def remember(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Any update from an owner: their Telegram language becomes the bot's, unless /lang fixed one."""
    user = update.effective_user
    if user is None or user.id not in cfg.admin_ids or not user.language_code or state.get('lang_set'):
        return
    lang = of_code(getattr(user, 'language_code', None))
    if state.get('lang') != lang:
        state.put('lang', lang)
        log.info('owners\' language: %s (from Telegram)', lang)
        await set_menu(ctx.bot)


async def cmd_lang(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/lang ru | en | auto. Owners only."""
    msg, user = update.effective_message, update.effective_user
    if user.id not in cfg.admin_ids:
        return
    arg = (ctx.args or [''])[0].strip().lower()
    if arg in LANGS:
        state.put('lang', arg)
        state.put('lang_set', '1')
    elif arg == 'auto':
        state.put('lang_set', '')
        state.put('lang', of_code(getattr(user, 'language_code', None)))
    else:
        await msg.reply_text(tr('Language: {name}. Change: /lang ru, /lang en, or /lang auto for your Telegram language.',
                                name=NAMES[owner_lang()]))
        return
    note = ''
    if settings().language:
        note = '\n' + tr('keeper.yaml sets language: {lang}, and it wins over /lang.', lang=settings().language)
    await set_menu(ctx.bot)
    await msg.reply_text(tr('✅ Language: {name}.', name=NAMES[owner_lang()]) + note)


async def set_menu(bot) -> None:
    """The «Menu» button: commands with short descriptions. A failure only costs the menu, never the bot."""
    try:
        for code, lang in ((None, owner_lang()), ('ru', 'ru')):
            await bot.set_my_commands([BotCommand(c, tr(d, lang)) for c, d in PRIVATE],
                                      scope=BotCommandScopeAllPrivateChats(), language_code=code)
            await bot.set_my_commands([BotCommand(c, tr(d, lang)) for c, d in IN_GROUP],
                                      scope=BotCommandScopeAllChatAdministrators(), language_code=code)
    except Exception as e:
        log.warning('could not set the command menu: %s', e)
