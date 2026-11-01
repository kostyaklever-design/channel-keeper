"""1.6.0: videos, GIFs and albums through the private chat."""
import asyncio
import types

import pytest

from bot.settings import Settings
from tests import fresh


@pytest.fixture()
def dm(tmp_path, monkeypatch):
    monkeypatch.setenv('BOT_TOKEN', '1:x'); monkeypatch.setenv('CHANNEL_ID', '-1001')
    monkeypatch.setenv('GROUP_ID', '-1002'); monkeypatch.setenv('ADMIN_IDS', '5')
    monkeypatch.setenv('DATA_DIR', str(tmp_path)); monkeypatch.delenv('AI_API_KEY', raising=False)
    main = fresh.load('main')
    main.current['settings'] = Settings(timezone='Europe/Amsterdam')
    log, jobs = [], []

    class Bot:
        id, n = 999, 100

        def _m(self):
            Bot.n += 1
            return types.SimpleNamespace(message_id=Bot.n)

        async def send_message(self, chat, text, reply_markup=None, **kw):
            log.append(('text', chat, text, reply_markup)); return self._m()

        async def send_video(self, chat, video, caption=None, reply_markup=None, **kw):
            log.append(('video', chat, f'{video}|{caption}', reply_markup)); return self._m()

        async def send_animation(self, chat, animation, caption=None, reply_markup=None, **kw):
            log.append(('gif', chat, f'{animation}|{caption}', reply_markup)); return self._m()

        async def send_photo(self, chat, photo=None, caption=None, reply_markup=None, **kw):
            log.append(('photo', chat, f'{photo}|{caption}', reply_markup)); return self._m()

        async def send_media_group(self, chat, media, **kw):
            log.append(('album', chat, [(type(m).__name__, m.media, m.caption) for m in media], None))
            return [self._m() for _ in media]

        async def delete_message(self, chat, mid): log.append(('delete', chat, mid, None))
        async def edit_message_reply_markup(self, **kw): pass
        async def get_chat_administrators(self, g): return []

    queue = types.SimpleNamespace(run_once=lambda cb, when, data=None: jobs.append((cb, data)))
    ctx = types.SimpleNamespace(bot=Bot(), bot_data={}, job_queue=queue)
    yield types.SimpleNamespace(main=main, dp=main.dm_posts, state=main.state, ctx=ctx, log=log, jobs=jobs)
    fresh.drop()


def write(t, text=None, caption=None, photo=None, video=None, animation=None, group=None):
    replies = []

    async def reply_text(x, **kw): replies.append(x)
    msg = types.SimpleNamespace(text=text, text_html=text, caption=caption, caption_html=caption, media_group_id=group,
                                photo=[types.SimpleNamespace(file_id='s'), types.SimpleNamespace(file_id=photo)] if photo else [],
                                video=types.SimpleNamespace(file_id=video) if video else None,
                                animation=types.SimpleNamespace(file_id=animation) if animation else None,
                                reply_text=reply_text)
    asyncio.run(t.main.on_private(types.SimpleNamespace(effective_message=msg,
                                                        effective_user=types.SimpleNamespace(id=5)), t.ctx))
    return replies


def finish_albums(t):
    for cb, data in t.jobs:
        asyncio.run(cb(types.SimpleNamespace(bot=t.ctx.bot, bot_data=t.ctx.bot_data, job=types.SimpleNamespace(data=data),
                                             job_queue=t.ctx.job_queue)))
    t.jobs.clear()


def press(t, data):
    answers = []

    async def answer(text=None, show_alert=False): answers.append(text)
    q = types.SimpleNamespace(data=data, answer=answer, from_user=types.SimpleNamespace(id=5, username='b', first_name='B'))
    asyncio.run(t.main.on_button(types.SimpleNamespace(callback_query=q), t.ctx))
    return answers


def channel(t):
    return [x for x in t.log if x[1] == -1001]


def test_video_post(dm):
    write(dm, video='VID', caption='New episode')
    press(dm, 'p:now:1')
    assert channel(dm) == [('video', -1001, 'VID|New episode', None)]


def test_album_is_collected_into_one_post(dm):
    write(dm, photo='P1', caption='Our trip', group='g1')
    write(dm, photo='P2', group='g1')
    write(dm, video='V3', group='g1')
    assert dm.state.dm_in('new') == []                              # waits for all parts
    finish_albums(dm)
    preview = [x for x in dm.log if x[0] == 'album' and x[1] == 5]
    assert len(preview) == 1 and len(preview[0][2]) == 3
    control = [x for x in dm.log if x[0] == 'text' and x[1] == 5 and x[3] is not None]
    assert control and control[-1][2] == '⬆️ The album above'      # buttons under the album
    press(dm, 'p:del:1')                                            # delete after 24 h
    press(dm, 'p:now:1')
    sent = [x for x in channel(dm) if x[0] == 'album']
    assert sent[0][2] == [('InputMediaPhoto', 'P1', 'Our trip'), ('InputMediaPhoto', 'P2', None),
                          ('InputMediaVideo', 'V3', None)]           # caption on the first item only
    assert not [x for x in channel(dm) if x[0] == 'text']           # no stray button message in the channel
    assert len(dm.state.timers_for('dm:1')) == 3                    # every part will be deleted


def test_album_rules(dm):
    write(dm, photo='P1', group='g2'); write(dm, animation='G', group='g2')
    finish_albums(dm)
    assert any('GIFs cannot be in an album' in x[2] for x in dm.log if x[0] == 'text')
    for i in range(11):
        write(dm, photo=f'P{i}', group='g3')
    finish_albums(dm)
    assert any('Up to 10' in x[2] for x in dm.log if x[0] == 'text')
    assert dm.state.dm_in('new') == []
    write(dm, photo='A', group='g4'); write(dm, photo='B', group='g4')
    finish_albums(dm)
    assert 'not allow buttons under an album' in press(dm, 'p:lnk:1')[0]


def test_gif_and_single_photo(dm):
    write(dm, animation='GIF', caption='Ha')
    write(dm, photo='BIG', caption='Pic')
    press(dm, 'p:now:1'); press(dm, 'p:now:2')
    assert [x[0] for x in channel(dm)] == ['gif', 'photo'] and channel(dm)[1][2] == 'BIG|Pic'
