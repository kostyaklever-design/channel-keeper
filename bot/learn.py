"""A spam filter that learns from this channel's own decisions — pure logic, no Telegram calls.

Examples: messages the owners marked «Delete» or «Keep» on a review, plus messages the rules
removed (links, spam words — the start of each, as kept in the log). Ordinary chat messages are
never stored, so «Keep» examples come only from reviews; the filter waits until it has enough of
both kinds. It is naive Bayes over words folded the same way as the spam-word check (look-alike
letters, spaced letters), small enough to retrain in a blink after every decision.
It never deletes anything: a high score only sends the message to the owners.
"""
import math
import re
from collections import Counter
from dataclasses import dataclass, field

from .moderation import joined_letters, skeleton

MIN_EACH = 20          # examples of each kind before the filter says anything
THRESHOLD = 0.9


def tokens(text: str) -> list[str]:
    folded = joined_letters(skeleton(text or ''))
    words = re.findall(r'\w{2,}', folded)
    return words + [f'{a}_{b}' for a, b in zip(words, words[1:])]     # pairs catch «пиши в лс», «free money»


@dataclass
class Model:
    spam: Counter = field(default_factory=Counter)
    ok: Counter = field(default_factory=Counter)
    docs: Counter = field(default_factory=Counter)      # {'spam': n, 'ok': n}

    @property
    def ready(self) -> bool:
        return self.docs['spam'] >= MIN_EACH and self.docs['ok'] >= MIN_EACH

    def progress(self) -> str:
        if self.ready:
            return f'on — learned from {self.docs["spam"]} spam and {self.docs["ok"]} kept messages'
        return (f'learning — {min(self.docs["spam"], MIN_EACH)}/{MIN_EACH} spam, '
                f'{min(self.docs["ok"], MIN_EACH)}/{MIN_EACH} kept (press Keep on reviews to teach it)')

    def spam_probability(self, text: str) -> float:
        words = tokens(text)
        if not words or not self.ready:
            return 0.0
        vocab = len(set(self.spam) | set(self.ok)) or 1
        s_total, o_total = sum(self.spam.values()), sum(self.ok.values())
        # Equal priors: the examples are not a fair sample of the chat (rules feed many spam examples).
        log_s = log_o = 0.0
        for w in words:
            log_s += math.log((self.spam[w] + 1) / (s_total + vocab))
            log_o += math.log((self.ok[w] + 1) / (o_total + vocab))
        diff = max(-50.0, min(50.0, log_o - log_s))
        return 1.0 / (1.0 + math.exp(diff))


def train(examples) -> Model:
    """examples: [(text, 'spam' | 'ok')]."""
    m = Model()
    for text, verdict in examples:
        words = tokens(text)
        if not words or verdict not in ('spam', 'ok'):
            continue
        (m.spam if verdict == 'spam' else m.ok).update(words)
        m.docs[verdict] += 1
    return m
