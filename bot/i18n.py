"""The bot's own words in the owners' language — English or Russian.

The English text in the code is the key (as in gettext): tr('Only the owners can do this.') returns it as is
for English and its Russian line from texts_ru.RU for Russian. Placeholders are named: tr('Approved by {who}.',
who=name). A test reads every tr('…') in bot/ and fails when a text has no Russian line, or the Russian line
uses other {placeholders} — so a new English text cannot ship untranslated.

Which language: `language:` in keeper.yaml wins; else /lang; else the owner's Telegram language.
Members see the group's texts from keeper.yaml; a newcomer asked in a private chat gets their own language.
"""
from .texts_ru import RU

LANGS = ('en', 'ru')
_current = {'get': lambda: 'en'}       # runtime.py plugs in the owners' language at start


def use(get_language) -> None:
    _current['get'] = get_language


def current() -> str:
    try:
        return _current['get']() or 'en'
    except Exception:
        return 'en'


def of_code(code: str | None) -> str:
    """A Telegram language_code -> one of ours. Only Russian is translated; everything else reads English."""
    return 'ru' if (code or '').lower().startswith('ru') else 'en'


def tr(text: str, lang: str | None = None, /, **values) -> str:
    out = RU.get(text, text) if (lang or current()) == 'ru' else text
    return out.format(**values) if values else out
