"""Drafts: the pure rules, and the flow on a fake Telegram — above all, that nothing reaches
the channel without an admin's press."""
import asyncio
import importlib
import types
from datetime import datetime, timedelta, timezone

import pytest

from tests import fresh

from bot import drafts as D
from bot.schedule import CAPTION_LIMIT, Post, due_posts, parse_posts
from bot.state import State

NOW = datetime(2026, 11, 3, 10, 0, tzinfo=timezone.utc)
# Modules that hold the running bot's memory: reloaded per test so each test gets a fresh database.


def post(**kw):
    base = dict(id='n1', at=NOW - timedelta(minutes=1), text='News text', image=None, status='draft')
    base.update(kw)
    return Post(**base)


# ---------- pure rules ----------
def test_status_parsed_and_validated():
    posts = parse_posts('posts:\n  - {id: a, at: "2026-11-03 10:00", text: x, status: Draft}\n')
    assert posts[0].status == 'draft'
    with pytest.raises(ValueError, match='status must be'):
        parse_posts('posts:\n  - {id: a, at: "2026-11-03 10:00", text: x, status: maybe}\n')


def test_drafts_never_due_as_scheduled_posts():
    send, skip = due_posts([post(), post(id='old', at=NOW - timedelta(days=2))], NOW, lambda i: False)
    assert send == [] and skip == []


def test_buttons_round_trip_and_reject_foreign_data():
    flat = [d for row in D.buttons(12) for _, d in row]
    assert [D.parse_button(d) for d in flat] == [('pub', 12), ('sch', 12), ('com', 12), ('rej', 12)]
    for bad in ('', 'd:pub', 'd:pub:x', 'd:drop:1', 'unban:1', 'd:pub:1:2'):
        assert D.parse_button(bad) is None
    assert all(len(d.encode()) <= 64 for d in flat)          # Telegram limit for button data


def test_comment_goes_on_top_and_is_checked():
    p = post(image='posts/x.png', text='x' * (CAPTION_LIMIT - 10))
    assert D.compose(post(), 'Why it matters') == 'Why it matters\n\nNews text'
    assert D.comment_problem(post(), '  ') == 'The comment is empty.'
    assert 'Shorten by' in D.comment_problem(p, 'a fairly long comment here')
    assert D.comment_problem(post(), 'ok') is None


def test_expiry_after_48h():
    created = (NOW - timedelta(hours=47)).timestamp()
    assert not D.expired(created, NOW)
    assert D.expired((NOW - timedelta(hours=49)).timestamp(), NOW)


def test_only_one_decision_wins(tmp_path):
    s = State(str(tmp_path))
    i = s.draft_create('n1')
    assert s.draft_move(i, 'publishing', D.OPEN, by=1)
    assert not s.draft_move(i, 'rejected', D.OPEN, by=2)        # second admin is too late
    assert not s.draft_move(i, 'publishing', D.OPEN, by=2)      # double press
    s.draft_move(i, 'published', ('publishing',))
    assert s.draft(i).status == 'published' and s.draft(i).decided_by == 1


def test_comment_reopens_draft(tmp_path):
    s = State(str(tmp_path))
    i = s.draft_create('n1')
    s.draft_move(i, 'approved', ('pending',))
    s.draft_comment(i, 'my take')
    d = s.draft(i)
    assert (d.status, d.comment) == ('pending', 'my take')     # new text must be approved again


# ---------- the flow on a fake Telegram ----------
@pytest.fixture()
def flow(tmp_path, monkeypatch):
    monkeypatch.setenv('BOT_TOKEN', '1:x'); monkeypatch.setenv('CHANNEL_ID', '-1001')
    monkeypatch.setenv('GROUP_ID', '-1002'); monkeypatch.setenv('ADMIN_IDS', '5,6')
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    fresh.drop()
    rt = importlib.import_module('bot.runtime')
    df = importlib.import_module('bot.draft_flow')
    sent = []

    class Bot:
        id = 999
        n = 100

        async def _msg(self, chat, text, kw):
            Bot.n += 1
            sent.append((chat, text, kw.get('reply_markup') is not None))
            return types.SimpleNamespace(message_id=Bot.n)

        async def send_message(self, chat, text, **kw): return await self._msg(chat, text, kw)
        async def send_photo(self, chat, photo=None, caption='', **kw): return await self._msg(chat, caption, kw)
        async def edit_message_reply_markup(self, **kw): sent.append(('edit', kw['chat_id'], kw['message_id']))
        async def get_chat_administrators(self, g): return []

    ctx = types.SimpleNamespace(bot=Bot(), bot_data={})
    yield rt, df, ctx, sent
    fresh.drop()


def press(df, ctx, data, user=5):
    answers = []

    async def answer(text=None, show_alert=False): answers.append(text)
    q = types.SimpleNamespace(data=data, from_user=types.SimpleNamespace(id=user, username='boss', first_name='B'),
                              message=types.SimpleNamespace(chat=types.SimpleNamespace(id=user), message_id=1),
                              answer=answer)
    asyncio.run(df.on_draft_button(types.SimpleNamespace(callback_query=q), ctx, *D.parse_button(data)))
    return answers


def channel(sent):
    return [s for s in sent if s[0] == -1001]


def test_draft_waits_for_a_press_then_publishes_once(flow):
    rt, df, ctx, sent = flow
    rt.current['posts'] = [post()]
    for _ in range(3):
        asyncio.run(df.drafts_tick(ctx))                       # due, but a draft: never goes out alone
    assert channel(sent) == []
    previews = [s for s in sent if s[0] in (5, 6) and s[2]]
    assert len(previews) == 2                                  # one preview per admin, sent once
    press(df, ctx, 'd:pub:1', user=5)
    assert [s[1] for s in channel(sent)] == ['News text']
    assert press(df, ctx, 'd:pub:1', user=6) == ['Already decided.']
    assert len(channel(sent)) == 1


def test_schedule_publishes_on_tick_with_comment(flow):
    rt, df, ctx, sent = flow
    rt.current['posts'] = [post(at=datetime.now(timezone.utc) + timedelta(hours=1))]
    asyncio.run(df.drafts_tick(ctx))
    press(df, ctx, 'd:com:1')
    msg = types.SimpleNamespace(text='Our take', reply_text=lambda t: asyncio.sleep(0))
    upd = types.SimpleNamespace(effective_message=msg, effective_user=types.SimpleNamespace(id=5, username='boss', first_name='B'))
    asyncio.run(df.on_private_text(upd, ctx))
    press(df, ctx, 'd:sch:1')
    asyncio.run(df.drafts_tick(ctx))
    assert channel(sent) == []                                 # its time has not come
    rt.current['posts'] = [post(at=datetime.now(timezone.utc) - timedelta(minutes=1))]
    asyncio.run(df.drafts_tick(ctx))
    assert [s[1] for s in channel(sent)] == ['Our take\n\nNews text']


def test_non_admin_cannot_press(flow):
    rt, df, ctx, sent = flow
    rt.current['posts'] = [post()]
    asyncio.run(df.drafts_tick(ctx))
    assert press(df, ctx, 'd:pub:1', user=77) == ['Only admins can do this.']
    assert channel(sent) == []


def test_reject_and_expiry(flow):
    rt, df, ctx, sent = flow
    rt.current['posts'] = [post(), post(id='n2')]
    asyncio.run(df.drafts_tick(ctx))
    press(df, ctx, 'd:rej:1')
    rt.state.db.execute('UPDATE drafts SET created = created - 49*3600 WHERE id = 2')
    asyncio.run(df.drafts_tick(ctx))
    assert rt.state.draft(1).status == 'rejected' and rt.state.draft(2).status == 'expired'
    assert channel(sent) == []
