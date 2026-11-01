"""1.8.0: the filter that learns from this channel's own Delete / Keep — and still never deletes."""
import asyncio
import types

import pytest

from bot import learn
from bot.settings import Captcha, Probation, Settings, parse_settings
from tests import fresh

SPAM = ['Удалённая работа, 500$ в день, напиши мне в личку', 'Заработок без вложений, пиши в лс срочно',
        'Работа на дому 300$ в день, пишите в личные сообщения', 'Лёгкий заработок онлайн, подробности в лс']
OK = ['Спасибо за пост, очень полезно', 'А когда будет следующий выпуск про голосовых ассистентов?',
      'Интересно, как это работает для салонов красоты', 'Согласен с автором, у нас тот же опыт']


def examples(n=learn.MIN_EACH):
    return [(SPAM[i % 4] + f' {i}', 'spam') for i in range(n)] + [(OK[i % 4] + f' {i}', 'ok') for i in range(n)]


def test_tokens_fold_disguises():
    assert learn.tokens('З а р а б о т о к') == learn.tokens('заработок')
    assert any('_' in t for t in learn.tokens('пиши в лс'))           # word pairs are features too


def test_waits_for_enough_examples_then_separates():
    small = learn.train(examples(5))
    assert not small.ready and small.spam_probability('напиши мне в личку') == 0.0 and '5/20' in small.progress()
    m = learn.train(examples())
    assert m.ready and m.spam_probability('Работа 400$ в день, пиши в лс') > learn.THRESHOLD
    assert m.spam_probability('Спасибо, очень полезный выпуск про ассистентов') < 0.5


def test_setting():
    assert parse_settings('').learning_filter is True
    with pytest.raises(ValueError):
        parse_settings('learning_filter: sometimes')


@pytest.fixture()
def grp(tmp_path, monkeypatch):
    monkeypatch.setenv('BOT_TOKEN', '1:x'); monkeypatch.setenv('CHANNEL_ID', '-1001')
    monkeypatch.setenv('GROUP_ID', '-1002'); monkeypatch.setenv('ADMIN_IDS', '5')
    monkeypatch.setenv('DATA_DIR', str(tmp_path)); monkeypatch.delenv('AI_API_KEY', raising=False)
    main = fresh.load('main')
    main.current['settings'] = Settings(captcha=Captcha(enabled=False), probation=Probation(messages=0),
                                        spam_words=('casino',))
    st = main.state
    for text, verdict in examples():
        st.db.execute('INSERT INTO decisions VALUES (0, 1, ?, ?, ?)', (text, verdict, 'ai'))
    sent = []

    class Bot:
        id, n = 999, 100

        async def send_message(self, chat, text, reply_markup=None, **kw):
            Bot.n += 1
            sent.append((chat, text))
            return types.SimpleNamespace(message_id=Bot.n)

        async def get_chat(self, uid): raise RuntimeError('no bio')
        async def get_chat_administrators(self, g): return []

    ctx = types.SimpleNamespace(bot=Bot(), bot_data={}, job_queue=types.SimpleNamespace(run_once=lambda *a, **k: None))
    yield types.SimpleNamespace(main=main, state=st, ctx=ctx, sent=sent)
    fresh.drop()


def comment(g, uid, text):
    gone = []

    async def delete(): gone.append(True)
    msg = types.SimpleNamespace(
        is_automatic_forward=False, text=text, caption=None, entities=(), caption_entities=(), forward_origin=None,
        sender_chat=None, message_thread_id=None, reply_to_message=None, media_group_id=None, message_id=900,
        photo=None, video=None, animation=None, document=None, video_note=None, contact=None, story=None, via_bot=None,
        reply_markup=None, from_user=types.SimpleNamespace(id=uid, is_bot=False, username=f'u{uid}', first_name='U'),
        delete=delete)
    asyncio.run(g.main.on_group_message(types.SimpleNamespace(effective_message=msg, edited_message=None), g.ctx))
    return bool(gone)


def test_learned_spam_goes_to_owners_and_stays(grp):
    assert not comment(grp, 42, 'Работа 400$ в день без опыта, пиши в лс')      # no rule matched, not deleted
    asks = [s for s in grp.sent if s[0] == 5 and s[1].startswith('🧠')]
    assert len(asks) == 1 and grp.state.known_since(42) is None
    assert not comment(grp, 43, 'Спасибо, очень полезный выпуск про ассистентов')
    assert not [s for s in grp.sent if s[0] == 5 and 'id 43' in s[1]]


def test_off_and_known_people(grp):
    grp.state.mark_known(44)
    comment(grp, 44, 'Работа 400$ в день без опыта, пиши в лс')                 # a regular: not asked
    grp.main.current['settings'] = Settings(captcha=Captcha(enabled=False), probation=Probation(messages=0),
                                            learning_filter=False)
    comment(grp, 45, 'Работа 400$ в день без опыта, пиши в лс')
    assert not [s for s in grp.sent if s[0] == 5]
    assert 'Learning filter' not in grp.main.report.report_text()
