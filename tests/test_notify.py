import json

from bot.notify import FORGIVE, OK, UNBAN, action_text, buttons_for, log_text, parse_button
from bot.state import KEEP_ACTIONS, State


# ---------- memory (SQLite) ----------
def test_old_state_json_is_imported_once(tmp_path):
    (tmp_path / 'state.json').write_text(json.dumps({'sent': ['p1', 'p2'], 'warns': {'42': 1}}), encoding='utf-8')
    s = State(str(tmp_path))
    assert s.migrated
    assert s.is_sent('p1') and s.is_sent('p2') and not s.is_sent('p3')
    assert s.add_warning(42) == 2                       # the old warning was kept
    assert (tmp_path / 'state.json.migrated').exists()
    assert not (tmp_path / 'state.json').exists()
    assert not State(str(tmp_path)).migrated            # second start: nothing to import


def test_memory_survives_restart(tmp_path):
    s = State(str(tmp_path))
    s.mark_sent('a')
    s.mark_sent('a')                                    # twice is harmless
    assert s.add_warning(7) == 1
    s2 = State(str(tmp_path))
    assert s2.is_sent('a')
    assert s2.add_warning(7) == 2
    s2.clear_warnings(7)
    assert s2.add_warning(7) == 1


def test_action_log_newest_first_and_trimmed(tmp_path):
    s = State(str(tmp_path))
    for i in range(KEEP_ACTIONS + 5):
        s.log_action('warn', i, f'u{i}', 'link', 'x' * 500)
    recent = s.recent_actions(3)
    assert [a.user_id for a in recent] == [KEEP_ACTIONS + 4, KEEP_ACTIONS + 3, KEEP_ACTIONS + 2]
    assert len(recent[0].excerpt) == 300
    assert s.db.execute('SELECT COUNT(*) FROM actions').fetchone()[0] == KEEP_ACTIONS


# ---------- what admins see ----------
def test_ban_notification_has_unban_button():
    text = action_text('ban', '@spam', 99, 'link', 'buy now https://x.y')
    assert 'Banned' in text and '@spam (id 99)' in text and 'Why: link' in text and 'https://x.y' in text
    assert buttons_for('ban', 99)[0] == ('Unban', f'{UNBAN}:99')
    assert buttons_for('warn', 99)[0] == ('Clear warning', f'{FORGIVE}:99')
    assert buttons_for('post', 0) == []


def test_long_message_is_shortened():
    assert action_text('warn', 'a', 1, 'link', 'y' * 500).endswith('…')


def test_buttons_parse_only_what_we_sent():
    assert parse_button(f'{UNBAN}:123') == (UNBAN, 123)
    assert parse_button(f'{OK}:0') == (OK, 0)
    for bad in ('', 'unban', 'unban:abc', 'drop:1', 'unban:1:2'):
        assert parse_button(bad) is None


def test_log_text(tmp_path):
    s = State(str(tmp_path))
    assert log_text([]) == 'Nothing yet.'
    s.log_action('ban', 5, '@bob', 'spam word "casino"')
    s.log_action('post', reason='hello-post')
    out = log_text(s.recent_actions(), 'Europe/Amsterdam').splitlines()
    assert 'Published' in out[0] and 'hello-post' in out[0]
    assert '@bob' in out[1] and 'casino' in out[1]
    assert s.name_of(5) == '@bob' and s.name_of(6) == ''


# ---------- 0.4.1: mentions and stale buttons ----------
def test_chat_message_mentions_by_id_and_escapes():
    from bot.settings import parse_settings
    s = parse_settings('messages: {warn: "{name}, no <links> & ads"}')
    out = s.html('warn', 42, 'Ann <3')
    assert out == '<a href="tg://user?id=42">Ann &lt;3</a>, no &lt;links&gt; &amp; ads'


def test_default_ban_message_has_mention():
    from bot.settings import Settings
    assert Settings().html('ban', 7, '@bob').startswith('<a href="tg://user?id=7">@bob</a> was removed')


def test_notes_are_popped_once(tmp_path):
    s = State(str(tmp_path))
    s.add_note(42, 5, 100, 'warned')
    s.add_note(42, 6, 200, 'warned')
    s.add_note(43, 5, 101, 'other')
    assert sorted(s.pop_notes(42)) == [(5, 100, 'warned'), (6, 200, 'warned')]
    assert s.pop_notes(42) == []
    assert s.pop_notes(43) == [(5, 101, 'other')]
