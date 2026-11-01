"""keeper.yaml — channel settings that are not secrets: timezone, spam words, the bot's words in chat,
channel rules for posts from feeds.

The file is optional. Without it the bot uses the English defaults below, so a
fresh install works before anyone writes a line of YAML.
"""
import html
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml

from .i18n import current, tr
from .hygiene import Rules, parse_rules

DEFAULT_SPAM_WORDS = (
    'casino', 'crypto', 'airdrop', 'giveaway', 'onlyfans', 'forex', 'binance', 'usdt',
    'earn money', 'make money', 'dm me', 'write me in private',
)

# {name} becomes @username or the first name of the person.
DEFAULT_MESSAGES = {
    'warn': '{name}, links and ads are not allowed here. Next time it is a ban.',
    'ban': '{name} was removed for repeated spam.',
    'flood': '{name}, too many messages in a row — you can write again in a few minutes.',
    'first_minutes': '{name}, new members can comment a few minutes after a post.',
    'probation': '{name}, pictures without words, forwards and contacts open up after your first few messages.',
}

KNOWN_KEYS = {'timezone', 'spam_words', 'warn_seconds', 'messages', 'channel_rules', 'captcha', 'channel_messages',
              'flood', 'first_minutes', 'keep_days', 'ai_moderation', 'probation', 'profile_check', 'ad_label',
              'join_requests', 'learning_filter', 'read_more', 'ai_language', 'language'}
# Messages written «on behalf of a channel» (not the own channel): a favourite trick of spammers,
# because a channel cannot press a captcha button and has no personal account to ban.
CHANNEL_MESSAGES = ('block', 'check')


DEFAULT_CAPTCHA_TEXT = '{name}, press the button within {seconds} seconds to write in this chat.'


@dataclass(frozen=True)
class Captcha:
    enabled: bool = True       # on: spam bots join and post in the first second; turn off with enabled: false
    seconds: int = 120         # slow connections (throttled Telegram) need time to even see the button
    text: str = DEFAULT_CAPTCHA_TEXT
    button: str = "I'm human"

    def label(self, lang: str | None = None) -> str:
        """The button's words: your own from keeper.yaml, or the default in the bot's language."""
        return tr("I'm human", lang) if self.button == "I'm human" else self.button

    def html(self, user_id: int, display: str) -> str:
        """The captcha message, {name} as a mention that notifies the person."""
        mark = '\x00NAME\x00'
        text = tr(DEFAULT_CAPTCHA_TEXT) if self.text == DEFAULT_CAPTCHA_TEXT else self.text
        safe = html.escape(text.format(name=mark, seconds=self.seconds), quote=False)
        link = f'<a href="tg://user?id={int(user_id)}">{html.escape(display, quote=False)}</a>'
        return safe.replace(html.escape(mark, quote=False), link)


def parse_captcha(raw) -> Captcha:
    if raw is None:
        return Captcha()
    if not isinstance(raw, dict):
        raise ValueError('keeper.yaml: captcha must be a mapping')
    known = {'enabled', 'seconds', 'text', 'button'}
    unknown = set(raw) - known
    if unknown:
        raise ValueError(f'keeper.yaml: unknown captcha settings {sorted(unknown)}; known: {sorted(known)}')
    enabled = raw.get('enabled', True)
    if not isinstance(enabled, bool):
        raise ValueError('keeper.yaml: captcha.enabled must be true or false')
    seconds = raw.get('seconds', 120)
    if not isinstance(seconds, int) or isinstance(seconds, bool) or not 15 <= seconds <= 600:
        raise ValueError('keeper.yaml: captcha.seconds must be a whole number from 15 to 600')
    text = str(raw.get('text') or DEFAULT_CAPTCHA_TEXT).strip()
    try:
        text.format(name='x', seconds=1)
    except (KeyError, IndexError, ValueError) as e:
        raise ValueError('keeper.yaml: captcha.text may use only {name} and {seconds}') from e
    button = str(raw.get('button') or "I'm human").strip()
    if not 1 <= len(button) <= 30:
        raise ValueError('keeper.yaml: captcha.button must be 1–30 characters')
    return Captcha(enabled, seconds, text, button)


def mention(user_id: int, display: str) -> str:
    """A person: a link to the account that notifies them. A channel (negative id) cannot be
    mentioned that way, so it is just its name."""
    name = html.escape(display, quote=False)
    return name if int(user_id) < 0 else f'<a href="tg://user?id={int(user_id)}">{name}</a>'


@dataclass(frozen=True)
class Flood:
    messages: int = 5          # this many messages ...
    seconds: int = 10          # ... within this time -> read-only; 0 messages = off
    mute_minutes: int = 10


@dataclass(frozen=True)
class Probation:
    messages: int = 2          # clean messages before pictures without words, forwards, contacts are allowed; 0 = off
    min_length: int = 15       # shorter messages («+», «спасибо») do not count


def parse_probation(raw) -> Probation:
    if raw is None:
        return Probation()
    if raw is False or raw == 'off':
        return Probation(messages=0)
    if not isinstance(raw, dict) or set(raw) - {'messages', 'min_length'}:
        raise ValueError('keeper.yaml: probation must have messages and min_length, or be off')
    d, values = Probation(), {}
    for key, low, high in (('messages', 0, 50), ('min_length', 1, 500)):
        v = raw.get(key, getattr(d, key))
        if not isinstance(v, int) or isinstance(v, bool) or not low <= v <= high:
            raise ValueError(f'keeper.yaml: probation.{key} must be a whole number from {low} to {high}')
        values[key] = v
    return Probation(**values)


def parse_flood(raw) -> Flood:
    if raw is None:
        return Flood()
    if raw is False or raw == 'off':
        return Flood(messages=0)
    if not isinstance(raw, dict):
        raise ValueError('keeper.yaml: flood must be a mapping or off')
    known = {'messages', 'seconds', 'mute_minutes'}
    unknown = set(raw) - known
    if unknown:
        raise ValueError(f'keeper.yaml: unknown flood settings {sorted(unknown)}; known: {sorted(known)}')
    d, values = Flood(), {}
    for key, low, high in (('messages', 0, 50), ('seconds', 2, 300), ('mute_minutes', 1, 1440)):
        v = raw.get(key, getattr(d, key))
        if not isinstance(v, int) or isinstance(v, bool) or not low <= v <= high:
            raise ValueError(f'keeper.yaml: flood.{key} must be a whole number from {low} to {high}')
        values[key] = v
    if values['messages'] == 1:
        raise ValueError('keeper.yaml: flood.messages 1 would mute everyone — use 3 or more, or 0 to turn off')
    return Flood(**values)


@dataclass(frozen=True)
class Settings:
    timezone: str = 'UTC'
    spam_words: tuple[str, ...] = DEFAULT_SPAM_WORDS
    warn_seconds: int = 60
    messages: dict = field(default_factory=lambda: dict(DEFAULT_MESSAGES))
    rules: Rules = Rules()
    captcha: Captcha = Captcha()
    channel_messages: str = 'block'
    flood: Flood = Flood()
    first_minutes: int = 0     # off by default: the bot first has to learn who the regular members are
    keep_days: int = 90        # log lines older than this are deleted
    ai_moderation: bool = True # with AI_API_KEY: newcomers' first comments get a second opinion
    probation: Probation = Probation()
    profile_check: bool = True # a link or spam word in a newcomer's profile -> owners decide
    ad_label: str = 'Advertisement'   # the first line of a post marked as an ad
    join_requests: str = 'captcha'    # captcha | owners | off — only when the group approves new members
    learning_filter: bool = True      # learns from your Delete / Keep; only asks you, never deletes
    read_more: str = 'Read on {source} →'   # the short link under a news post from a feed
    ai_language: str = 'English'      # the language the AI writes retellings in
    language: str = ''                # the bot's own language for the owners: '' = each owner's Telegram language

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    def text(self, key: str, **values) -> str:
        """What the bot says in the chat: your words from keeper.yaml, or the default in the bot's language."""
        value = self.messages.get(key) or DEFAULT_MESSAGES[key]
        if value == DEFAULT_MESSAGES[key]:
            value = tr(value)
        return value.format(**values)

    # Defaults that the channel's readers see follow the bot's language too; your own values stay as written.
    def ad_text(self) -> str:
        return tr('Advertisement') if self.ad_label == 'Advertisement' else self.ad_label

    def read_more_text(self) -> str:
        return tr('Read on {source} →') if self.read_more == 'Read on {source} →' else self.read_more

    def ai_language_name(self) -> str:
        if self.ai_language == 'English' and current() == 'ru':
            return 'Russian'
        return self.ai_language

    def html(self, key: str, user_id: int, display: str) -> str:
        """The message as Telegram HTML, {name} as a mention linked to the account by id.
        A plain name does not notify anyone; a link to tg://user?id= notifies the person
        even when they have no @username."""
        mark = '\x00NAME\x00'
        safe = html.escape(self.text(key, name=mark), quote=False)
        link = mention(user_id, display)
        return safe.replace(html.escape(mark, quote=False), link)


def _read_more(raw: dict) -> str:
    value = str(raw.get('read_more') or 'Read on {source} →').strip()
    try:
        value.format(source='x')
    except (KeyError, IndexError, ValueError) as e:
        raise ValueError('keeper.yaml: read_more may use only {source}') from e
    if not 1 <= len(value) <= 60:
        raise ValueError('keeper.yaml: read_more must be 1–60 characters')
    return value


def _language(raw: dict) -> str:
    value = str(raw.get('ai_language') or 'English').strip()
    if not 2 <= len(value) <= 30:
        raise ValueError('keeper.yaml: ai_language must be a language name like Russian or English')
    return value


LANGUAGES = ('en', 'ru')


def _bot_language(raw: dict) -> str:
    value = str(raw.get('language') or 'auto').strip().lower()
    if value == 'auto':
        return ''
    if value not in LANGUAGES:
        raise ValueError('keeper.yaml: language must be auto, en or ru')
    return value


def _bool(raw: dict, key: str, default: bool) -> bool:
    value = raw.get(key, default)
    if not isinstance(value, bool):
        raise ValueError(f'keeper.yaml: {key} must be true or false')
    return value


def parse_settings(text: str | None) -> Settings:
    """Settings from keeper.yaml text; None or empty -> defaults. Raises ValueError with a readable reason."""
    if not text or not text.strip():
        return Settings()
    try:
        raw = yaml.safe_load(text) or {}
    except yaml.YAMLError as e:
        raise ValueError(f'keeper.yaml is not valid YAML: {e}') from e
    if not isinstance(raw, dict):
        raise ValueError('keeper.yaml must be a mapping of settings')
    unknown = set(raw) - KNOWN_KEYS
    if unknown:
        raise ValueError(f'keeper.yaml: unknown settings {sorted(unknown)}; known: {sorted(KNOWN_KEYS)}')

    tz = str(raw.get('timezone') or 'UTC')
    try:
        ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError) as e:
        raise ValueError(f'keeper.yaml: unknown timezone "{tz}" (example: Europe/Amsterdam)') from e

    words = raw.get('spam_words', DEFAULT_SPAM_WORDS)
    if not isinstance(words, (list, tuple)):
        raise ValueError('keeper.yaml: spam_words must be a list')
    words = tuple(str(w).strip().lower() for w in words if str(w).strip())

    warn_seconds = raw.get('warn_seconds', 60)
    if not isinstance(warn_seconds, int) or not 5 <= warn_seconds <= 3600:
        raise ValueError('keeper.yaml: warn_seconds must be a whole number from 5 to 3600')

    msgs = dict(DEFAULT_MESSAGES)
    given = raw.get('messages') or {}
    if not isinstance(given, dict):
        raise ValueError('keeper.yaml: messages must be a mapping')
    for key, value in given.items():
        if key not in DEFAULT_MESSAGES:
            raise ValueError(f'keeper.yaml: unknown message "{key}"; known: {sorted(DEFAULT_MESSAGES)}')
        if value is None or not str(value).strip():
            continue                          # «warn:» with nothing after it keeps the default, not the text «None»
        value = str(value).strip()
        try:
            value.format(name='x')
        except (KeyError, IndexError, ValueError) as e:
            raise ValueError(f'keeper.yaml: message "{key}" may use only {{name}}') from e
        msgs[key] = value
    channel_messages = str(raw.get('channel_messages', 'block')).strip().lower()
    if channel_messages not in CHANNEL_MESSAGES:
        raise ValueError('keeper.yaml: channel_messages must be block or check')
    first = raw.get('first_minutes', 0)
    if not isinstance(first, int) or isinstance(first, bool) or not 0 <= first <= 60:
        raise ValueError('keeper.yaml: first_minutes must be a whole number from 0 to 60')
    keep = raw.get('keep_days', 90)
    if not isinstance(keep, int) or isinstance(keep, bool) or not 7 <= keep <= 3650:
        raise ValueError('keeper.yaml: keep_days must be a whole number from 7 to 3650')
    ai_mod = raw.get('ai_moderation', True)
    if not isinstance(ai_mod, bool):
        raise ValueError('keeper.yaml: ai_moderation must be true or false')
    profile = raw.get('profile_check', True)
    if not isinstance(profile, bool):
        raise ValueError('keeper.yaml: profile_check must be true or false')
    ad_label = str(raw.get('ad_label') or 'Advertisement').strip()
    if not 1 <= len(ad_label) <= 60:
        raise ValueError('keeper.yaml: ad_label must be 1–60 characters')
    joins = str(raw.get('join_requests', 'captcha')).strip().lower()
    if joins not in ('captcha', 'owners', 'off'):
        raise ValueError('keeper.yaml: join_requests must be captcha, owners or off')
    return Settings(tz, words, warn_seconds, msgs, parse_rules(raw.get('channel_rules')),
                    parse_captcha(raw.get('captcha')), channel_messages, parse_flood(raw.get('flood')), first, keep,
                    ai_mod, parse_probation(raw.get('probation')), profile, ad_label, joins,
                    _bool(raw, 'learning_filter', True), _read_more(raw), _language(raw), _bot_language(raw))
