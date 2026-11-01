"""1.9.5: the AI key added in Telegram (/setup → 🔑 Add AI key, /ai key, /ai off).
The key is checked with one tiny request, the owner's message with it is deleted, and a key pasted by
mistake never becomes a post. AI_API_KEY in the server variables always wins."""
import asyncio
import json
import types

import httpx
import pytest

from tests import fresh

KEY = 'sk-proj-' + 'a' * 40


@pytest.fixture()
def bot(tmp_path, monkeypatch):
    monkeypatch.setenv('BOT_TOKEN', '1:x'); monkeypatch.setenv('CHANNEL_ID', '-1001')
    monkeypatch.setenv('GROUP_ID', '-1002'); monkeypatch.setenv('ADMIN_IDS', '5')
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    for k in ('AI_API_KEY', 'AI_PROVIDER', 'AI_MODEL'):
        monkeypatch.delenv(k, raising=False)
    main = fresh.load('main')
    rt = __import__('bot.runtime', fromlist=['x'])
    seen, answer = [], {'status': 200}

    def provider(request):
        seen.append((str(request.url), request.headers.get('authorization'), json.loads(request.content)))
        if answer['status'] != 200:
            return httpx.Response(answer['status'], json={'error': {'message': 'Incorrect API key provided'}})
        return httpx.Response(200, json={'choices': [{'message': {'content': 'OK'}}], 'usage': {'total_tokens': 3}})
    rt.ai.transport = httpx.MockTransport(provider)
    sent = []

    class Bot:
        id, n = 999, 100

        async def send_message(self, chat, text, reply_markup=None, **kw):
            Bot.n += 1
            sent.append((chat, text, reply_markup))
            return types.SimpleNamespace(message_id=Bot.n)

        async def send_photo(self, chat, photo=None, caption='', reply_markup=None, **kw):
            return await self.send_message(chat, caption, reply_markup)

        async def get_chat_administrators(self, g): return []

    ctx = types.SimpleNamespace(bot=Bot(), bot_data={}, args=[],
                                job_queue=types.SimpleNamespace(run_once=lambda *a, **k: None))
    yield types.SimpleNamespace(main=main, rt=rt, state=main.state, ctx=ctx, sent=sent, seen=seen, answer=answer)
    fresh.drop()


def dm(b, text, uid=5):
    """A private message; returns True if it was deleted."""
    gone, replies = [], []

    async def delete(): gone.append(True)
    async def reply_text(t, **kw): replies.append(t)
    msg = types.SimpleNamespace(text=text, text_html=text, caption=None, caption_html=None, photo=None, video=None,
                                animation=None, media_group_id=None, forward_origin=None, reply_to_message=None,
                                message_id=50, delete=delete, reply_text=reply_text)
    upd = types.SimpleNamespace(effective_message=msg, effective_user=types.SimpleNamespace(id=uid),
                                effective_chat=types.SimpleNamespace(id=uid, type='private'))
    asyncio.run(b.main.on_private(upd, b.ctx))
    return bool(gone), replies


def press(b, data, uid=5):
    async def answer(text=None, show_alert=False): pass
    q = types.SimpleNamespace(data=data, answer=answer, from_user=types.SimpleNamespace(id=uid, username='o', first_name='O'),
                              message=types.SimpleNamespace(text='', chat=types.SimpleNamespace(id=uid), message_id=1))
    asyncio.run(b.main.on_button(types.SimpleNamespace(callback_query=q), b.ctx))


def last(b):
    return b.sent[-1][1]


def test_off_without_a_key_and_setup_offers_the_button(bot):
    from bot import setup
    assert not bot.rt.ai.c.on
    assert setup.ai_button() == [('🔑 Add AI key', 's:ai:0')] and 'Needs your own' in setup.ai_line()


def test_add_a_key_in_telegram(bot):
    press(bot, 's:ai:0')
    assert 'Paste your key' in last(bot)
    deleted, _ = dm(bot, f'  "{KEY}"  ')
    assert deleted                                                          # the key leaves the chat at once
    url, auth, body = bot.seen[-1]
    assert url.endswith('/chat/completions') and auth == f'Bearer {KEY}' and body['model'] == 'gpt-5-nano'
    assert bot.state.get('ai_key') == KEY
    c = bot.rt.ai.c
    assert (c.on, c.provider, c.model) == (True, 'openai', 'gpt-5-nano')
    assert last(bot).startswith('✅ AI is on — openai, gpt-5-nano')
    assert KEY not in ''.join(s[1] for s in bot.sent)                       # never repeated back
    assert bot.state.dm_in('new') == []                                     # not a post


def test_a_refused_key_is_not_saved(bot):
    bot.answer['status'] = 401
    press(bot, 's:ai:0')
    deleted, _ = dm(bot, KEY)
    assert deleted and not bot.state.get('ai_key') and not bot.rt.ai.c.on
    assert last(bot).startswith('Not saved.') and 'Incorrect API key provided' in last(bot)


def test_not_a_key_is_not_deleted_and_goes_on_as_usual(bot):
    press(bot, 's:ai:0')
    deleted, _ = dm(bot, 'changed my mind, here is a post')
    assert not deleted and not bot.state.get('ai_key')
    assert any('no key was saved' in s[1] for s in bot.sent)
    assert [p.text for p in bot.state.dm_in('new')] == ['changed my mind, here is a post']   # became a post as usual


def test_a_key_with_other_words_is_deleted_but_not_saved(bot):
    press(bot, 's:ai:0')
    deleted, _ = dm(bot, f'{KEY} thanks')
    assert deleted and not bot.state.get('ai_key') and 'Send the key alone' in last(bot)


def test_a_key_pasted_without_asking_is_deleted_not_posted(bot):
    deleted, _ = dm(bot, f'here: {KEY}')
    assert deleted and bot.state.dm_in('new') == [] and not bot.state.get('ai_key')
    assert 'deleted it instead of making a post' in last(bot)


def test_strangers_cannot_add_a_key(bot):
    deleted, _ = dm(bot, KEY, uid=77)
    assert not deleted and not bot.state.get('ai_key') and bot.sent == []


def test_ai_off_and_ai_key(bot):
    from bot import ai_flow
    bot.state.put('ai_key', KEY)
    assert bot.rt.ai.c.on
    replies = []

    async def reply_text(t, **kw): replies.append(t)
    upd = types.SimpleNamespace(effective_message=types.SimpleNamespace(reply_text=reply_text),
                                effective_user=types.SimpleNamespace(id=5))
    bot.ctx.args = ['off']
    asyncio.run(ai_flow.cmd_ai(upd, bot.ctx))
    assert replies[-1].startswith('🗑') and not bot.rt.ai.c.on
    bot.ctx.args = ['key']
    asyncio.run(ai_flow.cmd_ai(upd, bot.ctx))
    assert 'Paste your key' in last(bot)


def test_the_server_variable_wins(bot, monkeypatch):
    from bot import setup
    from bot.config import AIConfig
    monkeypatch.setenv('AI_API_KEY', 'sk-ant-' + 'b' * 40)
    bot.rt.ai.base = AIConfig.from_env()
    bot.state.put('ai_key', KEY)
    assert bot.rt.ai.c.provider == 'anthropic'                              # the variable, not the stored key
    assert setup.ai_button() is None and 'server variables' in setup.ai_line()
