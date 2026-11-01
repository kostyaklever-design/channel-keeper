"""The bot in Russian (1.10+): every English text the code passes to tr() has a Russian line with the same
{placeholders}, and no Russian line is left over for a text the code no longer says."""
import ast
import pathlib
import string

import pytest

from bot import i18n
from bot.notify import CLEANUP, TITLES
from bot.texts_ru import RU

ROOT = pathlib.Path(__file__).parent.parent


def texts_in_code() -> dict[str, str]:
    """{english text: where} for every tr('…') with a literal first argument in bot/."""
    found = {}
    for path in (ROOT / 'bot').glob('*.py'):
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
            if (isinstance(node, ast.Call) and getattr(node.func, 'id', None) == 'tr' and node.args
                    and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
                found.setdefault(node.args[0].value, f'{path.name}:{node.lineno}')
    for title in TITLES.values():                          # /log and notifications translate these by key
        found.setdefault(title, 'notify.TITLES')
    from bot.settings import DEFAULT_CAPTCHA_TEXT, DEFAULT_MESSAGES   # what the chat reads by default
    for text in list(DEFAULT_MESSAGES.values()) + [DEFAULT_CAPTCHA_TEXT]:
        found.setdefault(text, 'settings defaults')
    for _, label in CLEANUP:                               # the weekly report's lines
        found.setdefault(label, 'notify.CLEANUP')
    from bot.menu import IN_GROUP, PRIVATE             # the command menu translates these by key
    for _, description in PRIVATE + IN_GROUP:
        found.setdefault(description, 'language.py menu')
    return found


def fields(text: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


def test_every_text_has_a_russian_line():
    missing = {t: w for t, w in texts_in_code().items() if t not in RU}
    assert not missing, 'add to bot/texts_ru.py:\n' + '\n'.join(f'{w}: {t!r}' for t, w in missing.items())


def test_placeholders_match():
    bad = [t for t in RU if fields(t) != fields(RU[t])]
    assert not bad, f'the Russian line uses other {{placeholders}}: {bad}'


def test_no_leftover_russian_lines():
    stale = set(RU) - set(texts_in_code())
    assert not stale, f'texts the code no longer says — remove from texts_ru.py: {sorted(stale)}'


def test_the_guard_sees_the_code():
    found = texts_in_code()
    assert '✅ Publish now' in found and 'Only the owner can do this.' in found and len(found) > 50


def test_tr():
    assert i18n.tr('✅ Publish now', 'en') == '✅ Publish now'
    assert i18n.tr('✅ Publish now', 'ru') == RU['✅ Publish now']
    assert i18n.tr('Got «{title}».', 'ru', title='Канал') == RU['Got «{title}».'].format(title='Канал')
    assert i18n.tr('not in the catalog', 'ru') == 'not in the catalog'      # never crashes, falls back to English
    assert [i18n.of_code(c) for c in ('ru', 'ru-RU', 'en', None, 'uk', 'de')] == ['ru', 'ru', 'en', 'en', 'en', 'en']


def test_language_setting():
    from bot.settings import parse_settings
    assert parse_settings('').language == ''
    assert parse_settings('language: auto').language == ''
    assert parse_settings('language: RU').language == 'ru'
    with pytest.raises(ValueError, match='language'):
        parse_settings('language: de')


SENDERS = {'reply_text', 'send_message', 'answer', 'edit_message_text', 'notify_admins', 'AIError', 'FeedError',
           'retire', '_retire', '_under', '_refresh', 'retire_notes', 'ask_owners', 'offer', '_tell'}
ALLOWED = {'Channel Keeper v'}                     # /version: the product name is the same in every language
CODES = {'profile', 'learned', 'ai'}                # ask_owners' «source» codes, never shown


def words_in(node) -> str:
    """The literal words of a string argument: a plain string, or the fixed parts of an f-string."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return ' '.join(v.value for v in node.values if isinstance(v, ast.Constant) and isinstance(v.value, str))
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return words_in(node.left) + ' ' + words_in(node.right)
    if isinstance(node, ast.IfExp):
        return words_in(node.body) + ' ' + words_in(node.orelse)
    return ''


def untranslated() -> list[str]:
    import re
    found = []
    for path in (ROOT / 'bot').glob('*.py'):
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
            if not isinstance(node, ast.Call):
                continue
            name = getattr(node.func, 'attr', None) or getattr(node.func, 'id', None)
            if name not in SENDERS:
                continue
            for arg in list(node.args) + [k.value for k in node.keywords if k.arg in ('text', 'note')]:
                text = words_in(arg)
                if (re.search(r'[A-Za-z]{3,}', text) and text not in CODES
                        and not any(text.startswith(a) for a in ALLOWED)):
                    found.append(f'{path.name}:{node.lineno}: {text[:60]!r}')
    return found


def test_no_english_sent_past_tr():
    """2.0: every text the bot sends to people goes through tr(); an English literal here would stay English
    for a Russian-speaking owner."""
    left = untranslated()
    assert untranslated.__code__ and words_in(ast.parse("f'Hi {x}'").body[0].value) == 'Hi '   # the guard reads f-strings
    assert not left, 'wrap these in tr(...) and add a Russian line:\n' + '\n'.join(left)
