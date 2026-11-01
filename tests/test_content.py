import asyncio
import base64
import pathlib

import httpx
import pytest

from bot import content as content_mod
from bot.content import ContentError, ContentSource
from bot.schedule import parse_posts
from bot.settings import DEFAULT_MESSAGES, Settings, parse_settings

ROOT = pathlib.Path(__file__).parent.parent
run = asyncio.run


# ---------- settings (keeper.yaml) ----------
def test_no_settings_file_gives_defaults():
    s = parse_settings(None)
    assert s == Settings()
    assert s.text('warn', name='@ann') == DEFAULT_MESSAGES['warn'].format(name='@ann')


def test_repo_keeper_yaml_is_valid():
    """Fails on GitHub if keeper.yaml in this repository is broken."""
    path = ROOT / 'keeper.yaml'
    if path.exists():
        parse_settings(path.read_text(encoding='utf-8'))


def test_custom_settings_and_messages():
    s = parse_settings('''
timezone: Europe/Amsterdam
spam_words: [Casino, " Крипта "]
warn_seconds: 30
messages:
  warn: "{name}, ссылки здесь нельзя."
''')
    assert s.timezone == 'Europe/Amsterdam'
    assert s.spam_words == ('casino', 'крипта')
    assert s.warn_seconds == 30
    assert s.text('warn', name='Ann') == 'Ann, ссылки здесь нельзя.'
    assert s.text('ban', name='Ann') == DEFAULT_MESSAGES['ban'].format(name='Ann')


@pytest.mark.parametrize('body,err', [
    ('timezone: Mars/Base', 'unknown timezone'),
    ('spam_words: casino', 'must be a list'),
    ('warn_seconds: 0', 'warn_seconds'),
    ('messages: {hello: hi}', 'unknown message'),
    ('messages: {warn: "{user} no"}', 'only {name}'),
    ('colour: blue', 'unknown settings'),
    ('timezone: [', 'not valid YAML'),
])
def test_bad_settings_rejected(body, err):
    with pytest.raises(ValueError, match=err):
        parse_settings(body)


# ---------- posts from text ----------
def test_posts_default_timezone_comes_from_settings():
    posts = parse_posts('posts:\n  - {id: a, at: "2026-07-01 10:00", text: x}\n', 'Europe/Amsterdam')
    assert posts[0].at.utcoffset().total_seconds() == 7200   # CEST in July


def test_missing_posts_file_means_no_posts():
    assert parse_posts(None) == []


def test_post_must_be_a_block():
    with pytest.raises(ValueError, match='must be a block'):
        parse_posts('posts:\n  - just text\n')


# ---------- content source ----------
def test_local_source(tmp_path):
    (tmp_path / 'posts.yaml').write_text('posts: []', encoding='utf-8')
    src = ContentSource(local_dir=str(tmp_path))
    assert run(src.read_text('posts.yaml')) == 'posts: []'
    assert run(src.read_text('keeper.yaml')) is None
    with pytest.raises(ContentError, match='not allowed'):
        run(src.read_bytes('../secret.txt'))


def _fake_github(monkeypatch, handler):
    real = httpx.AsyncClient

    def client(*a, **kw):
        kw['transport'] = httpx.MockTransport(handler)
        return real(*a, **kw)
    monkeypatch.setattr(content_mod.httpx, 'AsyncClient', client)


def test_github_source_reads_file_with_token(monkeypatch):
    seen = {}

    def handler(request):
        seen['url'] = str(request.url)
        seen['auth'] = request.headers.get('Authorization')
        return httpx.Response(200, json={'type': 'file', 'encoding': 'base64',
                                         'content': base64.b64encode('posts: []'.encode()).decode()})
    _fake_github(monkeypatch, handler)
    src = ContentSource('me/content', 'secret-token', 'main')
    assert run(src.read_text('posts.yaml')) == 'posts: []'
    assert seen['url'] == 'https://api.github.com/repos/me/content/contents/posts.yaml?ref=main'
    assert seen['auth'] == 'Bearer secret-token'


def test_github_missing_file_and_errors(monkeypatch):
    def handler(request):
        return httpx.Response(404 if 'keeper' in request.url.path else 401)
    _fake_github(monkeypatch, handler)
    src = ContentSource('me/content', 'bad')
    assert run(src.read_text('keeper.yaml')) is None
    with pytest.raises(ContentError, match='401'):
        run(src.read_text('posts.yaml'))
