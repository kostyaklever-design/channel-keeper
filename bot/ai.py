"""The AI: one small client for Anthropic or OpenAI, with a monthly limit — and nothing else.

This module only talks to the AI provider and returns text. It cannot publish, cannot delete,
cannot ban: those calls are not imported here, and a test checks it stays that way. Whatever
the AI writes becomes a preview in the owner's private chat; a person presses the button.
Without AI_API_KEY the bot works as before; AI features say how to turn them on.
"""
import html
import json
import re
import time

import httpx

from .config import AIConfig
from .i18n import tr

PROVIDERS = {
    'anthropic': ('https://api.anthropic.com/v1/messages', 'claude-haiku-5-5'),
    'openai': ('https://api.openai.com/v1/chat/completions', 'gpt-5-nano'),
}


class AIError(Exception):
    """The AI could not answer: no key, limit reached, provider error. The message is for the owner."""


def month() -> str:
    return time.strftime('%Y-%m', time.gmtime())


class AI:
    """ask() -> text. Counts requests and tokens per month in the bot's memory (kv table)."""

    KEY = 'ai_key'          # kv: a key the owner added in Telegram (/setup); AI_API_KEY always wins

    def __init__(self, config: AIConfig, state, transport=None):
        self.base, self.state, self.transport = config, state, transport

    @property
    def c(self) -> AIConfig:
        if self.base.key or self.state is None:
            return self.base
        stored = self.state.get(self.KEY) or ''
        return self.base.with_key(stored) if stored else self.base

    @property
    def key_from_env(self) -> bool:
        return bool(self.base.key)

    def usage(self) -> tuple[int, int]:
        raw = self.state.get(f'ai:{month()}') or '0,0'
        calls, tokens = (int(x) for x in raw.split(','))
        return calls, tokens

    def _count(self, calls_added: int, tokens: int) -> None:
        calls, total = self.usage()
        self.state.put(f'ai:{month()}', f'{calls + calls_added},{total + tokens}')

    async def ask(self, system: str, user: str, max_tokens: int = 800, timeout: float = 60,
                  config: AIConfig | None = None) -> str:
        c = config or self.c          # read once: a key added in Telegram lives in the bot's memory
        if not c.on:
            raise AIError(tr('AI is off. Add your OpenAI or Anthropic key: /setup → 🔑 Add AI key '
                             '(or AI_API_KEY in the server variables).'))
        calls, _ = self.usage()
        if calls >= c.monthly_limit:
            raise AIError(tr('The monthly AI limit ({n} requests) is reached. '
                             'Raise AI_MONTHLY_LIMIT or wait for the next month.', n=c.monthly_limit))
        self._count(1, 0)        # counted before sending: a request that times out may still be billed
        url, _ = PROVIDERS[c.provider]
        if c.provider == 'anthropic':
            headers = {'x-api-key': c.key, 'anthropic-version': '2023-06-01', 'content-type': 'application/json'}
            body = {'model': c.model, 'max_tokens': max_tokens, 'system': system,
                    'messages': [{'role': 'user', 'content': user}]}
        else:
            headers = {'Authorization': f'Bearer {c.key}', 'content-type': 'application/json'}
            body = openai_body(c.model, system, user, max_tokens)
        try:
            async with httpx.AsyncClient(timeout=timeout, transport=self.transport) as client:
                r = await client.post(url, headers=headers, json=body)
        except httpx.HTTPError as e:
            raise AIError(tr('Cannot reach the AI provider ({error}).', error=e.__class__.__name__)) from e
        if r.status_code in (401, 403):
            raise AIError(tr('The AI provider ({provider}) refused the key: {error} '
                             'Check the key, and that it may use the model {model}.', provider=c.provider,
                             error=provider_error(r), model=c.model))
        if r.status_code != 200:
            raise AIError(tr('The AI provider answered {code}: {error}', code=r.status_code, error=provider_error(r)))
        data = r.json()
        if c.provider == 'anthropic':
            text = ''.join(part.get('text', '') for part in data.get('content', []) if part.get('type') == 'text')
            u = data.get('usage') or {}
            tokens = int(u.get('input_tokens', 0)) + int(u.get('output_tokens', 0))
        else:
            text = ((data.get('choices') or [{}])[0].get('message') or {}).get('content') or ''
            tokens = int((data.get('usage') or {}).get('total_tokens', 0))
        self._count(0, tokens)
        return text.strip()

    async def try_key(self, key: str) -> AIConfig:
        """One tiny request with a key the owner pasted; raises AIError with the provider's words if refused."""
        config = self.base.with_key(key)
        await self.ask('Answer with one word.', 'Say OK.', max_tokens=5, timeout=30, config=config)
        return config


def openai_body(model: str, system: str, user: str, max_tokens: int) -> dict:
    """OpenAI chat request. Newer models take max_completion_tokens (max_tokens is refused by reasoning models).
    Reasoning models (gpt-5…, o…) think before answering and the thinking counts toward the limit: they get the
    lowest effort and room for it, or a short answer like the spam check would come back empty."""
    body = {'model': model, 'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}]}
    name = model.lower()
    if name.startswith('gpt-5'):
        body.update(reasoning_effort='minimal', max_completion_tokens=max_tokens + 1000)
    elif name[:2] in ('o1', 'o3', 'o4'):
        body.update(reasoning_effort='low', max_completion_tokens=max_tokens + 2000)
    else:
        body['max_completion_tokens'] = max_tokens
    return body


def provider_error(r) -> str:
    """The provider's own words about what went wrong (a wrong model name, a bad parameter), shortened."""
    try:
        err = r.json().get('error') or {}
        return str(err.get('message') if isinstance(err, dict) else err)[:200] or r.text[:200]
    except Exception:
        return r.text[:200]


# ---------- what we ask, and how we read the answers (pure) ----------
SPAM_SYSTEM = (
    'You check comments in the discussion group of a Telegram channel. Spam includes: ads, job offers '
    'that ask to write privately, crypto and betting, «free money», adult content, and generic AI-written '
    'praise that adds nothing and exists to promote the author\'s profile. Ordinary questions, '
    'disagreement, rudeness and short replies are NOT spam. Answer with JSON only: '
    '{"spam": 0.0-1.0, "why": "a few words in English"}'
)


def spam_system(language: str = 'English') -> str:
    """The spam check, its «why» in the owners' language — it is shown to them as is."""
    return SPAM_SYSTEM.replace('a few words in English', f'a few words in {language}')


def spam_prompt(text: str) -> str:
    return f'Comment:\n"""\n{text[:1500]}\n"""'


def read_spam(answer: str) -> tuple[float, str]:
    """(probability, reason). Anything unreadable counts as «not spam»: the AI never removes on a guess."""
    m = re.search(r'\{.*\}', answer or '', re.S)
    try:
        data = json.loads(m.group(0)) if m else {}
        p = float(data.get('spam', 0))
    except (ValueError, TypeError, AttributeError):
        return 0.0, ''
    return max(0.0, min(1.0, p)), str(data.get('why', ''))[:80]


EDITOR_SYSTEM = (
    'You help the owner of a Telegram channel write posts. Write in the language the owner writes to you '
    'unless they ask for another. Posts are plain text for Telegram: short paragraphs, no markdown headings, '
    'no hashtags unless asked, at most 900 characters each. Never invent facts, numbers or quotes that are '
    'not in the material. When asked for several posts, separate them with a line containing only ---. '
    'Return only the post texts.'
)
POST_LIMIT = 1000
RETELL_SYSTEM = (
    'You retell a news item for a Telegram channel in {language}. Write 2–3 short sentences in your own words: '
    'what happened and why it matters to a small business owner. Use only facts from the material; never add '
    'numbers, names or quotes that are not there. No title, no link, no hashtags, no emoji at the start. '
    'Return only the sentences.'
)


HEADLINE_SYSTEM = (
    'You write a short news post for a Telegram channel in {language}, but you have ONLY a headline, not the '
    'article. Write 2–3 short paragraphs: (1) what the headline reports, attributed to the source (for example '
    '«По данным {{source}}, …» in Russian); (2) widely known background on the topic; (3) why it matters to a small '
    'business owner. Never invent details of the event itself: no numbers, dates, names, quotes, methods or '
    'consequences that are not in the headline. If something is unknown, do not guess it. No title, no link, '
    'no hashtags. Return only the paragraphs.'
)


def headline_prompt(title: str, source: str) -> str:
    return f'Headline: {title}\nSource: {source}'


def retell_prompt(title: str, material: str) -> str:
    return f'Title: {title}\n\nMaterial:\n"""\n{material[:8000]}\n"""'


def split_posts(answer: str, limit: int = 3) -> list[str]:
    parts = [p.strip() for p in re.split(r'^\s*-{3,}\s*$', answer or '', flags=re.M)]
    return [p[:POST_LIMIT] for p in parts if p][:limit]


def editor_prompt(request: str, material: str = '', context: str = '') -> str:
    out = [f'Request from the owner:\n{request}']
    if material:
        out.append(f'Material (from a web page; use only what is written here):\n"""\n{material[:12000]}\n"""')
    if context:
        out.append(f'The channel right now:\n{context[:3000]}')
    return '\n\n'.join(out)


def page_text(html_text: str) -> str:
    """Readable text of a web page — scripts, styles and tags removed."""
    t = re.sub(r'(?is)<(script|style|noscript|svg|nav|footer|header)[^>]*>.*?</\1>', ' ', html_text or '')
    t = re.sub(r'(?s)<[^>]+>', ' ', t)
    t = re.sub(r'&nbsp;|&#160;', ' ', t)
    return re.sub(r'\s+', ' ', html.unescape(t)).strip()
