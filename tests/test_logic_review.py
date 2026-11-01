"""1.8.6: logic errors found by three independent reviews. Each test is one scenario that used to go wrong."""
import asyncio
import time
import types
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx
import pytest

from bot.dm_rules import quick_time
from bot.settings import Captcha, Probation, Settings, parse_settings
from bot.state import State
from tests import fresh


# ---------- pure ----------
def test_in_one_hour_is_real_time_across_the_clock_change():
    ams = ZoneInfo('Europe/Amsterdam')
    before = datetime(2026, 10, 25, 2, 30, tzinfo=ams, fold=0)                 # summer time, the first 02:30
    after = quick_time('h1', before)
    assert after.astimezone(timezone.utc) - before.astimezone(timezone.utc) == timedelta(hours=1)


def test_empty_values_in_keeper_yaml_keep_defaults():
    s = parse_settings('messages:\n  warn:\nread_more:\nai_language:\n')
    assert 'None' not in s.messages['warn'] and s.read_more.startswith('Read on') and s.ai_language == 'English'


def test_warnings_expire_after_30_days(tmp_path):
    s = State(str(tmp_path))
    assert s.add_warning(1) == 1
    s.db.execute('UPDATE warns SET at = ?', (time.time() - 31 * 86400,))
    assert s.add_warning(1) == 1                         # an old slip is forgotten, not half a ban
    assert s.add_warning(1) == 2


def test_seen_entries_are_refreshed(tmp_path):
    s = State(str(tmp_path))
    s.mark_seen(['l:x']); s.db.execute('UPDATE seen SET at = 0')
    s.mark_seen(['l:x'])
    s.forget_seen(time.time() - 3600)
    assert s.is_seen(['l:x'])


def test_restart_puts_publishing_right(tmp_path):
    s = State(str(tmp_path))
    a = s.item_add('feed:a', 'f', 'F', 'news', 'x', 'queued'); s.item_move(a, 'publishing', ('queued',))
    b = s.item_add('feed:b', 'f', 'F', 'news', 'y', 'queued'); s.item_move(b, 'publishing', ('queued',))
    s.mark_sent('feed:b', 'news')
    d = s.dm_add(5, 'post', None); s.dm_move(d, 'publishing', ('new',))
    assert s.reconcile() == 3
    assert (s.item(a).status, s.item(b).status, s.dm(d).status) == ('queued', 'published', 'missed')


def test_ai_request_is_counted_even_when_it_times_out(tmp_path):
    from bot import ai as A
    from bot.config import AIConfig

    def slow(request): raise httpx.ReadTimeout('slow', request=request)
    ai = A.AI(AIConfig('openai', 'k', 'gpt-5-nano', 10), State(str(tmp_path)), httpx.MockTransport(slow))
    with pytest.raises(A.AIError):
        asyncio.run(ai.ask('s', 'u', timeout=1))
    assert ai.usage()[0] == 1


# ---------- in the running bot ----------
@pytest.fixture()
def bot(tmp_path, monkeypatch):
    monkeypatch.setenv('BOT_TOKEN', '1:x'); monkeypatch.setenv('CHANNEL_ID', '-1001')
    monkeypatch.setenv('GROUP_ID', '-1002'); monkeypatch.setenv('ADMIN_IDS', '5')
    monkeypatch.setenv('DATA_DIR', str(tmp_path)); monkeypatch.delenv('AI_API_KEY', raising=False)
    main = fresh.load('main')
    rules = main.current['settings'].rules.__class__(quiet=None, gap_minutes=0)
    main.current['settings'] = Settings(captcha=Captcha(enabled=False), probation=Probation(messages=0), rules=rules)
    log, fail = [], {'channel': None, 'ban': None}

    class Bot:
        id, n = 999, 100

        def _m(self):
            Bot.n += 1
            return types.SimpleNamespace(message_id=Bot.n)

        async def send_message(self, chat, text, reply_markup=None, **kw):
            if chat == -1001 and fail['channel']:
                raise RuntimeError(fail['channel'])
            log.append(('send', chat, text, kw.get('direct_messages_topic_id'))); return self._m()

        async def ban_chat_member(self, chat, uid):
            if fail['ban']:
                raise RuntimeError(fail['ban'])
            log.append(('ban', chat, uid, None))

        async def unban_chat_member(self, chat, uid, only_if_banned=False): log.append(('unban', chat, uid, None))
        async def unban_chat_sender_chat(self, chat, cid): log.append(('unban_channel', chat, cid, None))
        async def restrict_chat_member(self, chat, uid, perms, until_date=None): log.append(('restrict', chat, uid, perms.can_send_messages))
        async def get_chat(self, chat): return types.SimpleNamespace(permissions=None, bio='', linked_chat_id=None)
        async def delete_message(self, chat, mid): log.append(('delete', chat, mid, None))
        async def edit_message_reply_markup(self, **kw): pass
        async def get_chat_administrators(self, g): return []

    ctx = types.SimpleNamespace(bot=Bot(), bot_data={}, job_queue=types.SimpleNamespace(run_once=lambda *a, **k: None))
    yield types.SimpleNamespace(main=main, state=main.state, ctx=ctx, log=log, fail=fail)
    fresh.drop()


def private(b, text, uid=5, reply_to=None):
    replies = []

    async def reply_text(t, **kw): replies.append(t)
    msg = types.SimpleNamespace(text=text, text_html=text, caption=None, caption_html=None, media_group_id=None,
                                photo=[], video=None, animation=None, forward_origin=None, reply_text=reply_text,
                                reply_to_message=types.SimpleNamespace(message_id=reply_to) if reply_to else None)
    asyncio.run(b.main.on_private(types.SimpleNamespace(effective_message=msg,
                                                        effective_user=types.SimpleNamespace(id=uid, username='b', first_name='B')),
                                  b.ctx))
    return replies


def press(b, data, uid=5):
    answers = []

    async def answer(text=None, show_alert=False): answers.append(text)
    async def edit(*a, **k): pass
    q = types.SimpleNamespace(data=data, answer=answer, edit_message_text=edit, edit_message_reply_markup=edit, message=None,
                              from_user=types.SimpleNamespace(id=uid, username='boss', first_name='B'))
    asyncio.run(b.main.on_button(types.SimpleNamespace(callback_query=q), b.ctx))
    return answers


def test_a_forgotten_reply_never_sends_a_later_message_to_a_stranger(bot):
    item = bot.state.inbox_add(-1005, 7, 1, 42, '@stranger', 'hi', 'message')
    press(bot, f'i:re:{item}')                           # Reply pressed, never answered
    private(bot, 'My new post')                          # …then the owner writes a post
    private(bot, '18:30')
    assert not [x for x in bot.log if x[1] == -1005]     # nothing reached the stranger
    press(bot, f'i:re:{item}')
    prompt = bot.ctx.bot_data['waits'][5][1][1]
    private(bot, 'Real answer', reply_to=prompt)          # a reply to the bot's prompt — the only way out
    assert [x[2] for x in bot.log if x[1] == -1005] == ['Real answer']


def test_a_wait_lapses_after_10_minutes(bot):
    item = bot.state.inbox_add(-1005, 7, 1, 42, '@stranger', 'hi', 'message')
    press(bot, f'i:re:{item}')
    kind, value, at = bot.ctx.bot_data['waits'][5]
    bot.ctx.bot_data['waits'][5] = (kind, value, at - 601)
    private(bot, 'This is a new post, not an answer')
    assert not [x for x in bot.log if x[1] == -1005] and bot.state.dm_in('new')


def test_one_broken_post_does_not_block_the_queue(bot):
    st = bot.state
    a = st.item_add('feed:a', 'f', 'F', 'own', 'broken', 'queued')
    b = st.item_add('feed:b', 'f', 'F', 'own', 'fine', 'queued')
    bot.fail['channel'] = "Bad Request: can't parse entities"
    for _ in range(3):
        asyncio.run(__import__('bot.channel_queue', fromlist=['x']).queue_tick(bot.ctx))
    assert st.item(a).status == 'failed'
    assert any('set aside' in x[2] for x in bot.log if x[1] == 5)
    bot.fail['channel'] = None
    asyncio.run(__import__('bot.channel_queue', fromlist=['x']).queue_tick(bot.ctx))
    assert st.item(b).status == 'published'


def test_missing_rights_are_reported_not_counted(bot):
    a = bot.state.item_add('feed:a', 'f', 'F', 'own', 'post', 'queued')
    bot.fail['channel'] = 'Forbidden: bot is not a member of the channel chat'
    for _ in range(5):
        asyncio.run(__import__('bot.channel_queue', fromlist=['x']).queue_tick(bot.ctx))
    assert bot.state.item(a).status == 'queued'                       # waits for the rights, not thrown away
    assert len([x for x in bot.log if x[1] == 5 and 'Cannot publish to the channel' in x[2]]) == 1


def test_unban_in_a_comment_thread_hits_the_user_not_the_channel(bot):
    thread_root = types.SimpleNamespace(is_automatic_forward=True, sender_chat=types.SimpleNamespace(id=-1001))
    replies = []

    async def reply_text(t, **kw): replies.append(t)
    msg = types.SimpleNamespace(reply_to_message=thread_root, reply_text=reply_text)
    upd = types.SimpleNamespace(effective_message=msg, effective_user=types.SimpleNamespace(id=5))
    asyncio.run(bot.main.cmd_unban(upd, types.SimpleNamespace(args=['42'], bot=bot.ctx.bot, bot_data=bot.ctx.bot_data)))
    assert ('unban', -1002, 42, None) in bot.log and not [x for x in bot.log if x[0] == 'unban_channel']
    assert ('restrict', -1002, 42, True) in bot.log                    # and can really write again


def test_a_forwarded_album_is_one_violation(bot):
    def part(mid):
        gone = []

        async def delete(): gone.append(True)
        msg = types.SimpleNamespace(
            is_automatic_forward=False, text=None, caption=None, entities=(), caption_entities=(),
            forward_origin=types.SimpleNamespace(type='channel'), sender_chat=None, message_thread_id=None,
            reply_to_message=None, media_group_id='alb', message_id=mid, photo=[1], video=None, animation=None,
            document=None, video_note=None, contact=None, story=None, via_bot=None, reply_markup=None,
            from_user=types.SimpleNamespace(id=42, is_bot=False, username='s', first_name='S'), delete=delete)
        asyncio.run(bot.main.on_group_message(types.SimpleNamespace(effective_message=msg, edited_message=None), bot.ctx))
    for mid in (1, 2, 3):
        part(mid)
    assert not [x for x in bot.log if x[0] == 'ban'] and bot.state.add_warning(42) == 2


def test_captcha_removal_failure_does_not_leave_someone_read_only(bot):
    bot.state.captcha_add(42, 0, 'join', '@x')
    bot.fail['ban'] = 'Bad Request: not enough rights'
    asyncio.run(bot.main.captcha.captcha_tick(bot.ctx))
    assert ('restrict', -1002, 42, True) in bot.log


def test_second_owner_cannot_undo_the_first(bot, monkeypatch):
    bot.main.cfg.admin_ids.add(6)
    bot.state.review_add(777, 42, 'text', 'ai')
    press(bot, 'm:keep:777:42', uid=5)
    assert press(bot, 'm:del:777:42', uid=6) == ['Already decided by another owner.']
    assert not [x for x in bot.log if x[0] == 'delete']


def test_retelling_an_approved_feed_draft_takes_it_out_of_the_queue(bot):
    st = bot.state
    item = st.item_add('feed:r', 'habr', 'Habr', 'news', 'Title', 'draft', html=True, material='text', link='https://h/1')
    d = st.draft_create('feed:r')
    press(bot, f'd:sch:{d}')
    assert st.item(item).status == 'queued'
    st.draft_comment(d, 'my take')                       # what a comment (or a retelling) does to the draft
    st.item_move(item, 'draft', ('queued',))
    asyncio.run(__import__('bot.channel_queue', fromlist=['x']).queue_tick(bot.ctx))
    assert not [x for x in bot.log if x[1] == -1001]     # not published without a new approval


def test_admin_ids_win_over_an_owner_claimed_earlier(tmp_path, monkeypatch):
    monkeypatch.setenv('BOT_TOKEN', '1:x'); monkeypatch.setenv('DATA_DIR', str(tmp_path))
    monkeypatch.delenv('ADMIN_IDS', raising=False)
    rt = fresh.load('runtime')
    rt.claim_owner(77)                                    # a stranger claimed the bot first
    monkeypatch.setenv('ADMIN_IDS', '5')
    rt = fresh.load('runtime')
    assert rt.cfg.admin_ids == {5}
    fresh.drop()
