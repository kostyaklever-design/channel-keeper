"""0.8.0: disguised spam words, flood, the first minutes after a post, /log filters."""
import asyncio
import importlib
import time
import types

import pytest

from tests import fresh

from bot.moderation import joined_letters, skeleton, spam_reason
from bot.settings import Flood, Settings, parse_settings

WORDS = ('casino', 'казино', 'пиши в лс', 'crypto', 'заработок')


# ---------- disguised words ----------
@pytest.mark.parametrize('text', ['kаzино', 'ка3ино', 'к а з и н о', 'к.а.з.и.н.о', 'cas​ino', '𝐜𝐚𝐬𝐢𝐧𝐨',
                                  'c r y p t o', 'ПИШИ   В  ЛС', 'зарабoтoк от 1000', 'CASINO'])
def test_disguised_spam_words_are_caught(text):
    assert spam_reason(text, [], WORDS, False)


@pytest.mark.parametrize('text', ['Отличный пост, спасибо!', 'Казань классная', 'и т.д. и т.п.', 'я и ты',
                                  'В 3 часа созвон', 'Пишите в комментариях', 'а б в'])
def test_ordinary_russian_is_not_spam(text):
    assert spam_reason(text, [], WORDS, False) is None


def test_disguised_link():
    assert spam_reason('пиши т.mе/spam_ch', [], (), False) == 'disguised link'
    assert spam_reason('www​.spam', [], (), False) == 'disguised link'


def test_helpers():
    assert skeleton('Ка3ино') == skeleton('kazино')
    assert joined_letters('к а з и н о and more') == 'казино and more'
    assert joined_letters('я и') == 'я и'                         # two letters are not a word


# ---------- settings ----------
def test_settings_defaults_and_validation():
    s = parse_settings('')
    assert s.flood == Flood(5, 10, 10) and s.first_minutes == 0     # first minutes off until turned on
    assert parse_settings('flood: off').flood.messages == 0
    assert parse_settings('first_minutes: 5\nflood:\n  messages: 8\n').flood == Flood(8, 10, 10)
    for bad in ('flood:\n  messages: 1\n', 'flood:\n  per: 3\n', 'first_minutes: 90', 'first_minutes: soon'):
        with pytest.raises(ValueError):
            parse_settings(bad)


# ---------- the group on a fake Telegram ----------
@pytest.fixture()
def group(tmp_path, monkeypatch):
    monkeypatch.setenv('BOT_TOKEN', '1:x'); monkeypatch.setenv('CHANNEL_ID', '-1001')
    monkeypatch.setenv('GROUP_ID', '-1002'); monkeypatch.setenv('ADMIN_IDS', '5')
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    fresh.drop()
    main = importlib.import_module('bot.main')
    main.current['settings'] = Settings(captcha=Settings().captcha.__class__(enabled=False), first_minutes=5)
    calls = []

    class Bot:
        id, n = 999, 100

        async def send_message(self, chat, text, **kw):
            Bot.n += 1
            calls.append(('send', chat, text))
            return types.SimpleNamespace(message_id=Bot.n)

        async def restrict_chat_member(self, chat, uid, perms, until_date=None):
            calls.append(('restrict', uid, until_date is not None))

        async def ban_chat_member(self, chat, uid): calls.append(('ban', uid))
        async def delete_message(self, chat, mid): pass
        async def get_chat_administrators(self, g): return []

    jobs = types.SimpleNamespace(run_once=lambda *a, **k: None)
    ctx = types.SimpleNamespace(bot=Bot(), bot_data={}, job_queue=jobs)
    yield types.SimpleNamespace(main=main, state=main.state, ctx=ctx, calls=calls)
    fresh.drop()


def send(g, uid, text='hello', thread=None, album=None, auto=False, mid=1):
    deleted = []

    async def delete(): deleted.append(True)
    msg = types.SimpleNamespace(
        is_automatic_forward=auto, text=text, caption=None, entities=(), caption_entities=(), forward_origin=None,
        sender_chat=types.SimpleNamespace(id=-1001, username='ch', title='Ch') if auto else None,
        from_user=types.SimpleNamespace(id=uid, is_bot=False, username=f'u{uid}', first_name='U'),
        message_thread_id=thread, reply_to_message=None, media_group_id=album, message_id=mid, delete=delete)
    asyncio.run(g.main.on_group_message(types.SimpleNamespace(effective_message=msg), g.ctx))
    return bool(deleted)


def test_flood_mutes_for_a_while_and_albums_count_once(group):
    for _ in range(4):
        assert not send(group, 42)
    assert send(group, 42)                                          # 5th within 10 s
    assert ('restrict', 42, True) in group.calls                    # with an end time, not forever
    assert group.state.recent_actions(1)[0].kind == 'flood'
    for _ in range(8):
        send(group, 43, album='A1')                                 # one album of 8 photos
    assert ('restrict', 43, True) not in group.calls


def test_strangers_wait_in_a_fresh_thread_regulars_do_not(group):
    send(group, 50, 'I was here before')                            # a regular
    time.sleep(0.01)
    send(group, 0, auto=True, mid=777)                              # the channel post arrives
    assert not send(group, 50, 'first!', thread=777)
    assert send(group, 60, 'buy now', thread=777)                   # unknown before the post: deleted
    assert send(group, 60, 'buy now', thread=777)
    notes = [c for c in group.calls if c[0] == 'send' and 'tg://user?id=60' in c[2]]
    assert len(notes) == 1                                          # told once per post
    assert not send(group, 60, 'elsewhere')                         # outside the fresh thread: normal rules


def test_window_closes_and_rule_is_off_by_default(group):
    send(group, 0, auto=True, mid=777)
    group.ctx.bot_data['fresh_posts'][777] -= 6 * 60                # 6 minutes later
    assert not send(group, 60, 'late comment', thread=777)
    group.main.current['settings'] = Settings(captcha=Settings().captcha.__class__(enabled=False))
    send(group, 0, auto=True, mid=778)
    assert not send(group, 61, 'hi', thread=778)


def test_log_filters_and_splits(group):
    st = group.state
    for i in range(30):
        st.log_action('warn', 7 if i % 2 else 8, '@seven' if i % 2 else '@eight', 'link', 'x' * 150)
    assert {a.user_id for a in st.recent_actions(100, who='7')} == {7}
    assert {a.user_id for a in st.recent_actions(100, who='@SEVEN')} == {7}
    chunks = group.main.split_text('\n'.join('line %d %s' % (i, 'y' * 90) for i in range(100)))
    assert len(chunks) > 1 and all(len(c) <= 4000 for c in chunks)
