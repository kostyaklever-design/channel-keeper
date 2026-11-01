import pathlib
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from bot.moderation import spam_reason
from bot.schedule import CAPTION_LIMIT, due_posts, load_posts

ROOT = pathlib.Path(__file__).parent.parent
WORDS = ('casino', 'заработок')  # spam words now come from keeper.yaml
AMS = ZoneInfo('Europe/Amsterdam')


# ---------- moderation ----------
@pytest.mark.parametrize('text', [
    'check https://scam.example', 'go to t.me/somechannel', 'www.cheap.shop now',
    'visit bestdeal.xyz', 'WIN at CASINO tonight', 'Лёгкий заработок без вложений',
])
def test_spam_detected(text):
    assert spam_reason(text, [], WORDS, False)


@pytest.mark.parametrize('text', [
    'Можно поменять скрипт приветствия?', 'How long does setup take?', 'Does it speak Dutch?', 'Booked for 15:00, thanks!', '',
])
def test_normal_messages_pass(text):
    assert spam_reason(text, [], WORDS, False) is None


def test_link_entity_and_channel_forward():
    assert spam_reason('click here', ['text_link'], WORDS, False) == 'link'
    assert spam_reason('nice post', [], WORDS, True)


# ---------- schedule ----------
def _yaml(tmp_path, body):
    p = tmp_path / 'posts.yaml'
    p.write_text(body, encoding='utf-8')
    return str(p)


def test_repo_posts_yaml_is_valid():
    """Fails on GitHub if posts.yaml is broken (bad date, duplicate id, too long)."""
    posts = load_posts(str(ROOT / 'posts.yaml')) if (ROOT / 'posts.yaml').exists() else []
    for p in posts:
        if p.image:
            assert (ROOT / p.image).exists(), f'image not found: {p.image}'


def test_due_and_grace(tmp_path):
    path = _yaml(tmp_path, '''
posts:
  - {id: past, at: "2026-11-03 09:58", text: a}
  - {id: old, at: "2026-11-02 09:00", text: b}
  - {id: future, at: "2026-11-03 12:00", text: c}
''')
    posts = load_posts(path, 'Europe/Amsterdam')
    now = datetime(2026, 11, 3, 10, 0, tzinfo=AMS)
    send, skip = due_posts(posts, now, lambda i: False)
    assert [p.id for p in send] == ['past']
    assert [p.id for p in skip] == ['old']
    send, _ = due_posts(posts, now, lambda i: i == 'past')
    assert send == []


def test_timezone_from_posts_file_wins(tmp_path):
    posts = load_posts(_yaml(tmp_path, 'timezone: Europe/Amsterdam\nposts:\n  - {id: a, at: "2026-11-03 10:00", text: x}\n'))
    assert posts[0].at.utcoffset() == timedelta(hours=1)  # CET in November


@pytest.mark.parametrize('body,err', [
    ('posts:\n  - {id: a, at: "2026-11-03 10:00", text: x}\n  - {id: a, at: "2026-11-04 10:00", text: y}\n', 'duplicate'),
    ('posts:\n  - {id: a, at: "3 Nov 10am", text: x}\n', 'must look like'),
    ('posts:\n  - {id: a, at: "2026-11-03 10:00", text: ""}\n', 'empty'),
    (f'posts:\n  - {{id: a, at: "2026-11-03 10:00", image: x.png, text: "{"x" * (CAPTION_LIMIT + 1)}"}}\n', 'limit'),
])
def test_bad_posts_rejected(tmp_path, body, err):
    with pytest.raises(ValueError, match=err):
        load_posts(_yaml(tmp_path, body))
