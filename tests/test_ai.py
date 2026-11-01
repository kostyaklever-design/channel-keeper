"""1.1.0: the AI — a fake provider, the limit, and the rule that matters most:
the AI never publishes and never deletes on its own."""
import asyncio
import json
import ast
import pathlib
import types

import httpx
import pytest

from bot import ai as A
from bot.config import AIConfig
from bot.state import State
from tests import fresh

ROOT = pathlib.Path(__file__).parent.parent


# ---------- the guard ----------
def names_used(path) -> set[str]:
    """Every name the code touches: variables, attributes, imports (comments and docstrings do not count)."""
    tree = ast.parse(path.read_text(encoding='utf-8'))
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            out.add(node.id)
        elif isinstance(node, ast.Attribute):
            out.add(node.attr)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            out |= {a.asname or a.name for a in node.names}
    return out


def test_ai_modules_cannot_reach_the_channel():
    """Neither module may publish, send posts, ban, restrict or even know the channel's id."""
    forbidden = {'publish', 'publish_item', 'send_post', 'channel_id', 'ban_chat_member', 'ban_chat_sender_chat',
                 'restrict_chat_member', 'set_chat_permissions'}
    for name in ('ai.py', 'ai_flow.py'):
        used = names_used(ROOT / 'bot' / name) & forbidden
        assert not used, f'{name} uses {sorted(used)}'
    assert 'publish' in names_used(ROOT / 'bot' / 'dm_posts.py')        # the guard sees real code


# ---------- config ----------
def test_config(monkeypatch):
    for k in ('AI_API_KEY', 'AI_PROVIDER', 'AI_MODEL', 'AI_MONTHLY_LIMIT'):
        monkeypatch.delenv(k, raising=False)
    assert not AIConfig.from_env().on
    monkeypatch.setenv('AI_API_KEY', 'k')
    c = AIConfig.from_env()
    assert (c.provider, c.model, c.monthly_limit) == ('openai', 'gpt-5-nano', 300)
    monkeypatch.setenv('AI_PROVIDER', 'anthropic')
    assert AIConfig.from_env().model == 'claude-haiku-5-5'
    monkeypatch.setenv('AI_PROVIDER', 'gemini')
    with pytest.raises(SystemExit, match='AI_PROVIDER'):
        AIConfig.from_env()
    monkeypatch.setenv('AI_PROVIDER', 'openai')
    monkeypatch.setenv('AI_MODEL', 'some-model'); monkeypatch.setenv('AI_MONTHLY_LIMIT', 'lots')
    with pytest.raises(SystemExit, match='AI_MONTHLY_LIMIT'):
        AIConfig.from_env()


def test_provider_is_told_by_the_key(monkeypatch):
    """1.9.0: an OpenAI key without AI_PROVIDER used to go to Anthropic and be «refused»."""
    for k in ('AI_PROVIDER', 'AI_MODEL', 'AI_MONTHLY_LIMIT'):
        monkeypatch.delenv(k, raising=False)
    for key, provider, model in (('sk-proj-abc', 'openai', 'gpt-5-nano'), ('sk-abc', 'openai', 'gpt-5-nano'),
                                 ('sk-ant-api03-abc', 'anthropic', 'claude-haiku-5-5'),
                                 ('"sk-proj-abc"', 'openai', 'gpt-5-nano')):
        monkeypatch.setenv('AI_API_KEY', key)
        c = AIConfig.from_env()
        assert (c.provider, c.model, c.key.startswith('sk-')) == (provider, model, True), key
    monkeypatch.setenv('AI_API_KEY', 'sk-proj-abc'); monkeypatch.setenv('AI_PROVIDER', 'anthropic')
    with pytest.raises(SystemExit, match='looks like a openai key'):
        AIConfig.from_env()
    monkeypatch.setenv('AI_API_KEY', 'sk-ant-api03-abc'); monkeypatch.setenv('AI_PROVIDER', 'openai')
    with pytest.raises(SystemExit, match='looks like a anthropic key'):
        AIConfig.from_env()


# ---------- the client against a fake provider ----------
def provider(reply_text='ok', status=200, seen=None):
    def handle(request):
        if seen is not None:
            seen.append((str(request.url), dict(request.headers), json.loads(request.content)))
        if 'anthropic' in str(request.url):
            body = {'content': [{'type': 'text', 'text': reply_text}], 'usage': {'input_tokens': 10, 'output_tokens': 5}}
        else:
            body = {'choices': [{'message': {'content': reply_text}}], 'usage': {'total_tokens': 15}}
        return httpx.Response(status, json=body)
    return httpx.MockTransport(handle)


def test_anthropic_request_and_usage(tmp_path):
    seen = []
    ai = A.AI(AIConfig('anthropic', 'secret', 'claude-haiku-5-5', 2), State(str(tmp_path)), provider('hi', seen=seen))
    assert asyncio.run(ai.ask('sys', 'user')) == 'hi'
    url, headers, body = seen[0]
    assert url.endswith('/v1/messages') and headers['x-api-key'] == 'secret' and body['system'] == 'sys'
    assert ai.usage() == (1, 15)
    asyncio.run(ai.ask('sys', 'user'))
    with pytest.raises(A.AIError, match='limit'):
        asyncio.run(ai.ask('sys', 'user'))                     # the third request this month is refused


def test_openai_and_errors(tmp_path):
    st = State(str(tmp_path))
    ai = A.AI(AIConfig('openai', 'k', 'm', 10), st, provider('yo'))
    assert asyncio.run(ai.ask('s', 'u')) == 'yo'
    bad = A.AI(AIConfig('openai', 'k', 'm', 10), st, provider(status=401))
    with pytest.raises(A.AIError, match='refused the key'):
        asyncio.run(bad.ask('s', 'u'))
    said = httpx.MockTransport(lambda r: httpx.Response(401, json={'error': {'message': 'Incorrect API key provided'}}))
    with pytest.raises(A.AIError, match=r'\(openai\) refused the key: Incorrect API key provided'):
        asyncio.run(A.AI(AIConfig('openai', 'k', 'm', 10), st, said).ask('s', 'u'))
    with pytest.raises(A.AIError, match='AI is off'):
        asyncio.run(A.AI(AIConfig(), st).ask('s', 'u'))


def test_reading_answers():
    assert A.read_spam('Sure! {"spam": 0.92, "why": "job offer in DM"}') == (0.92, 'job offer in DM')
    assert A.read_spam('no json here') == (0.0, '')            # unreadable = not spam: no action on a guess
    assert A.read_spam('{"spam": 7}')[0] == 1.0
    assert A.split_posts('one\n---\ntwo\n---\nthree\n---\nfour') == ['one', 'two', 'three']
    assert A.page_text('<html><script>x()</script><p>Hello&nbsp;<b>world</b></p></html>') == 'Hello world'


# ---------- in Telegram ----------
@pytest.fixture()
def bot(tmp_path, monkeypatch):
    monkeypatch.setenv('BOT_TOKEN', '1:x'); monkeypatch.setenv('CHANNEL_ID', '-1001')
    monkeypatch.setenv('GROUP_ID', '-1002'); monkeypatch.setenv('ADMIN_IDS', '5')
    monkeypatch.setenv('DATA_DIR', str(tmp_path)); monkeypatch.setenv('AI_API_KEY', 'sk-ant-k'); monkeypatch.delenv('AI_PROVIDER', raising=False)
    main = fresh.load('main')
    from bot.settings import Captcha, Settings
    main.current['settings'] = Settings(captcha=Captcha(enabled=False))
    answer = {'text': '{"spam": 0.9, "why": "job offer"}'}
    rt = __import__('bot.runtime', fromlist=['x'])
    rt.ai.transport = httpx.MockTransport(
        lambda r: httpx.Response(200, json={'content': [{'type': 'text', 'text': answer['text']}], 'usage': {}}))
    sent, deleted = [], []

    class Bot:
        id, n = 999, 100

        async def send_message(self, chat, text, reply_markup=None, **kw):
            Bot.n += 1
            sent.append((chat, text, reply_markup))
            return types.SimpleNamespace(message_id=Bot.n)

        async def send_photo(self, chat, photo=None, caption='', reply_markup=None, **kw):
            return await self.send_message(chat, caption, reply_markup)

        async def delete_message(self, chat, mid): deleted.append((chat, mid))
        async def edit_message_reply_markup(self, **kw): pass
        async def get_chat_administrators(self, g): return []

    ctx = types.SimpleNamespace(bot=Bot(), bot_data={}, job_queue=types.SimpleNamespace(run_once=lambda *a, **k: None))
    yield types.SimpleNamespace(main=main, rt=rt, state=main.state, ctx=ctx, sent=sent, deleted=deleted, answer=answer)
    fresh.drop()


def comment(b, uid, text):
    gone = []

    async def delete(): gone.append(True)
    msg = types.SimpleNamespace(
        is_automatic_forward=False, text=text, caption=None, entities=(), caption_entities=(), forward_origin=None,
        sender_chat=None, message_thread_id=None, reply_to_message=None, media_group_id=None, message_id=555,
        from_user=types.SimpleNamespace(id=uid, is_bot=False, username=f'u{uid}', first_name='U'), delete=delete)
    asyncio.run(b.main.on_group_message(types.SimpleNamespace(effective_message=msg), b.ctx))
    return bool(gone)


def press(b, data, uid=5):
    answers, edits = [], []

    async def answer(text=None, show_alert=False): answers.append(text)
    async def edit(text, reply_markup=None): edits.append(text)
    q = types.SimpleNamespace(data=data, answer=answer, edit_message_text=edit,
                              from_user=types.SimpleNamespace(id=uid, username='boss', first_name='B'),
                              message=types.SimpleNamespace(text='note', chat=types.SimpleNamespace(id=uid), message_id=1))
    asyncio.run(b.main.on_button(types.SimpleNamespace(callback_query=q), b.ctx))
    return answers, edits


def test_doubtful_comment_waits_for_an_owner(bot):
    assert not comment(bot, 42, 'Hi all! Remote job, 500$ a day, message me for details today')   # stays
    asks = [s for s in bot.sent if s[0] == 5 and s[1].startswith('🤖')]
    assert len(asks) == 1 and 'job offer' in asks[0][1]
    assert bot.state.known_since(42) is None
    press(bot, 'm:del:555:42')
    assert bot.deleted == [(-1002, 555)]                                        # deleted only after the press


def test_keep_makes_the_person_known_and_known_people_are_not_checked(bot):
    comment(bot, 42, 'A long and perfectly normal question about the post?')
    press(bot, 'm:keep:555:42')
    assert bot.state.known_since(42) is not None
    before = bot.rt.ai.usage()[0]
    comment(bot, 42, 'Another long message from the same person, now known')
    comment(bot, 43, 'ok')                                                      # too short to be worth a request
    assert bot.rt.ai.usage()[0] == before


def test_ai_saying_no_spam_marks_known(bot):
    bot.answer['text'] = '{"spam": 0.1}'
    comment(bot, 44, 'A long and perfectly normal question about the post?')
    assert bot.state.known_since(44) is not None and not [s for s in bot.sent if s[1].startswith('🤖')]


def test_non_owner_cannot_press_review(bot):
    comment(bot, 42, 'Hi all! Remote job, 500$ a day, message me for details today')
    assert press(bot, 'm:del:555:42', uid=77)[0] == ['Only the owners can do this.'] and bot.deleted == []


def test_ai_editor_makes_previews_only(bot, monkeypatch):
    bot.answer['text'] = 'First post\n---\nSecond post'

    async def page(url): return 'Article text'
    monkeypatch.setattr(bot.main.ai_flow, 'read_page', page)
    replies = []

    async def reply_text(t, **kw): replies.append(t)
    upd = types.SimpleNamespace(effective_message=types.SimpleNamespace(reply_text=reply_text),
                                effective_user=types.SimpleNamespace(id=5))
    asyncio.run(bot.main.ai_flow.cmd_ai(upd, types.SimpleNamespace(args=['2', 'posts', 'from', 'https://x.example/a'],
                                                                   bot=bot.ctx.bot, bot_data=bot.ctx.bot_data)))
    assert [p.text for p in bot.state.dm_in('new')] == ['First post', 'Second post']
    assert [s for s in bot.sent if s[0] == -1001] == []                          # nothing in the channel
    assert any('✨ Edit with AI' in str(s[2]) for s in bot.sent if s[2] is not None)


def test_edit_with_ai_gives_a_new_preview(bot):
    bot.answer['text'] = 'Shorter version'
    bot.state.dm_add(5, 'A very long original post', None)
    press(bot, 'p:ai:1')
    msg = types.SimpleNamespace(text='shorter', reply_text=lambda *a, **k: asyncio.sleep(0))
    asyncio.run(bot.main.on_private(types.SimpleNamespace(effective_message=msg, effective_user=types.SimpleNamespace(id=5)),
                                    bot.ctx))
    assert [p.text for p in bot.state.dm_in('new')] == ['A very long original post', 'Shorter version']


def test_report(bot):
    st = bot.state
    st.mark_sent('a', 'own'); st.mark_sent('b', 'news'); st.log_action('ban', 1, '@x', 'link')
    text = bot.main.report.report_text()
    assert 'Posts: 2 — 1 yours, 1 news' in text and 'bans: 1' in text and 'AI this month' in text


def test_openai_request_fits_the_model():
    nano = A.openai_body('gpt-5-nano', 's', 'u', 60)
    assert 'max_tokens' not in nano and nano['reasoning_effort'] == 'minimal' and nano['max_completion_tokens'] > 60
    old = A.openai_body('gpt-4.1-nano', 's', 'u', 60)
    assert old['max_completion_tokens'] == 60 and 'reasoning_effort' not in old


def test_provider_error_is_shown(tmp_path):
    bad = httpx.MockTransport(lambda r: httpx.Response(400, json={'error': {'message': "The model `gpt-9` does not exist"}}))
    ai = A.AI(AIConfig('openai', 'k', 'gpt-9', 10), State(str(tmp_path)), bad)
    with pytest.raises(A.AIError, match='gpt-9` does not exist'):
        asyncio.run(ai.ask('s', 'u'))


def test_after_the_captcha_the_first_comment_still_gets_a_second_opinion(bot):
    """1.9.3: pressing «I'm human» made a person «known», so the AI, profile and learning checks never saw them.
    Live spammers press the button; their first real comment must still reach the owners."""
    from bot.settings import Captcha, Settings
    bot.main.current['settings'] = Settings(captcha=Captcha(enabled=True, seconds=60))
    B = type(bot.ctx.bot)

    async def restrict(self, chat, uid, perms): pass
    async def get_chat(self, chat):
        from telegram import ChatPermissions
        return types.SimpleNamespace(permissions=ChatPermissions(can_send_messages=True), bio=None)
    B.restrict_chat_member, B.get_chat = restrict, get_chat
    assert comment(bot, 42, 'hello')                                            # captcha: first message removed
    press(bot, 'c:42', uid=42)
    assert bot.state.is_human(42) and bot.state.known_since(42) is None         # a person, not known yet
    assert not comment(bot, 42, 'Hi all! Remote job, 500$ a day, message me for details today')
    assert [s for s in bot.sent if s[0] == 5 and s[1].startswith('🤖')]         # the owners get the card
    assert bot.state.known_since(42) is None
