"""Pure spam rules, no Telegram calls — easy to test.

Spammers dodge word lists: «kаzino» with a Cyrillic а, «к а з и н о» with spaces, invisible
characters inside a word. Before comparing, text and spam words are folded to one «skeleton»:
look-alike letters become one letter, invisible characters go, single letters split by spaces
are joined back into a word.
"""
import re
import unicodedata

LINK_RE = re.compile(
    r'(https?://|www\.|t\.me/|telegram\.me/|wa\.me/|bit\.ly/'
    r'|\b[\w-]+\.(com|net|org|io|ru|ua|xyz|top|site|online|shop|info|biz|me|cc|link)\b)',
    re.IGNORECASE,
)
# On the skeleton only the unmistakable link starts are checked: a Russian sentence folded to
# Latin letters must not look like «word.com».
SKELETON_LINK_RE = re.compile(r'(https?://|www\.|t\.me/|telegram\.me/|wa\.me/|bit\.ly/)')
LINK_ENTITY_TYPES = {'url', 'text_link'}

INVISIBLE = dict.fromkeys(map(ord, '​‌‍⁠﻿­᠎'), None)
# Look-alikes -> one Latin letter. Cyrillic and Greek letters that look Latin; digits used as letters.
LOOKALIKE = str.maketrans({
    'а': 'a', 'в': 'b', 'е': 'e', 'ё': 'e', 'к': 'k', 'м': 'm', 'н': 'h', 'о': 'o', 'р': 'p',
    'с': 'c', 'т': 't', 'у': 'y', 'х': 'x', 'і': 'i', 'ї': 'i', 'ј': 'j', 'ѕ': 's', 'ԁ': 'd',
    'з': 'z', 'п': 'n', 'г': 'r',
    'α': 'a', 'β': 'b', 'ε': 'e', 'η': 'n', 'ι': 'i', 'κ': 'k', 'μ': 'm', 'ν': 'v', 'ο': 'o',
    'ρ': 'p', 'τ': 't', 'υ': 'u', 'χ': 'x', 'ω': 'w',
    '0': 'o', '1': 'i', '3': 'z', '@': 'a', '$': 's',
})
SEPARATORS = re.compile(r'[\s.\-_*·•|/\\]+')


def skeleton(text: str) -> str:
    """Lowercase, compatibility forms folded (𝐜𝐚𝐬𝐢𝐧𝐨 -> casino), invisible characters removed,
    look-alike letters made the same."""
    t = unicodedata.normalize('NFKC', text or '').translate(INVISIBLE).lower()
    return ' '.join(t.translate(LOOKALIKE).split())


def joined_letters(text: str) -> str:
    """«к а з и н о» -> «казино»: runs of single letters split by spaces or dots become one word."""
    out, run = [], []
    for token in SEPARATORS.split(text):
        if len(token) == 1:
            run.append(token)
            continue
        out.extend([''.join(run)] if len(run) >= 3 else run)   # two single letters stay as they were
        run = []
        if token:
            out.append(token)
    out.extend([''.join(run)] if len(run) >= 3 else run)
    return ' '.join(out)


def spam_reason(text: str, entity_types: list[str], spam_words: tuple[str, ...],
                forwarded_from_channel: bool) -> str | None:
    """Return why a message is spam, or None if it is fine."""
    if forwarded_from_channel:
        return 'forward from another channel'
    if any(t in LINK_ENTITY_TYPES for t in entity_types):
        return 'link'
    if text and LINK_RE.search(text):
        return 'link'
    folded = skeleton(text)
    if SKELETON_LINK_RE.search(folded):
        return 'disguised link'
    variants = (folded, joined_letters(folded))
    for w in spam_words:
        sw = skeleton(w)
        if sw and any(sw in v for v in variants):
            return f'spam word "{w}"'
    return None
