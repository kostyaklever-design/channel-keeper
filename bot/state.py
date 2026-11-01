"""The bot's memory: sent posts, warnings, drafts, feed items, the queue and a log of what the bot did.

SQLite in one file on the persistent disk (/data/keeper.db). Nothing to install —
it is part of Python — and it keeps working as drafts and feeds are added later,
where a single JSON file would have to be rewritten on every change.

The 0.1–0.3 memory (state.json) is imported once on first start and renamed to
state.json.migrated, so nothing is published twice after the upgrade.
"""
import json
import os
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS sent    (post_id TEXT PRIMARY KEY, at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS warns   (user_id INTEGER PRIMARY KEY, count INTEGER NOT NULL, at REAL NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS notes (    -- admin notifications that still have buttons
    user_id    INTEGER NOT NULL,
    admin_id   INTEGER NOT NULL,
    message_id INTEGER NOT NULL,
    text       TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS drafts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,   -- short number for buttons; post ids can be long
    post_id    TEXT UNIQUE NOT NULL,
    status     TEXT NOT NULL,                       -- pending | approved | publishing | published | rejected | expired
    comment    TEXT NOT NULL DEFAULT '',
    created    REAL NOT NULL,                       -- when the current preview went out (48 h clock)
    decided_by INTEGER
);
CREATE TABLE IF NOT EXISTS draft_msgs (draft_id INTEGER NOT NULL, admin_id INTEGER NOT NULL, message_id INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS seen (key TEXT PRIMARY KEY, at REAL NOT NULL);   -- feed entries already handled
CREATE TABLE IF NOT EXISTS feeds (    -- one row per source: is it primed, how did the last check go
    id        TEXT PRIMARY KEY,
    signature TEXT NOT NULL,
    checked   REAL,
    ok        REAL,
    error     TEXT NOT NULL DEFAULT '',
    found     INTEGER NOT NULL DEFAULT 0,
    skipped   INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS items (    -- posts brought in from feeds
    id       INTEGER PRIMARY KEY AUTOINCREMENT,   -- short number for buttons
    post_id  TEXT UNIQUE NOT NULL,
    source   TEXT NOT NULL,                       -- source id
    name     TEXT NOT NULL,                       -- source name at the time
    label    TEXT NOT NULL,                       -- own | news
    text     TEXT NOT NULL,
    created  REAL NOT NULL,
    status   TEXT NOT NULL,                       -- draft | queued | publishing | published | rejected | expired | skipped
    notified INTEGER NOT NULL DEFAULT 0,          -- admins were told it is held by the 1 : 3 rule
    html     INTEGER NOT NULL DEFAULT 0,          -- 1 = text is Telegram HTML (items from 1.8.3 on)
    image    TEXT NOT NULL DEFAULT '',            -- picture address the feed gave
    material TEXT NOT NULL DEFAULT '',            -- the entry's own text, for the AI retelling
    link     TEXT NOT NULL DEFAULT '',
    publisher TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS item_msgs (item_id INTEGER NOT NULL, admin_id INTEGER NOT NULL, message_id INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS humans (user_id INTEGER PRIMARY KEY, at REAL NOT NULL);   -- passed the captcha, forever
CREATE TABLE IF NOT EXISTS captchas (  -- people who must press «I'm human»
    user_id    INTEGER PRIMARY KEY,
    message_id INTEGER,                -- the bot's message with the button
    deadline   REAL NOT NULL,
    reason     TEXT NOT NULL,          -- join | first_message
    name       TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS members (   -- wrote without trouble
    user_id INTEGER PRIMARY KEY,
    since   REAL NOT NULL,
    clean   INTEGER NOT NULL DEFAULT 0     -- clean messages so far: ends the newcomer probation
);
CREATE TABLE IF NOT EXISTS reviews (   -- messages waiting for an owner's Delete / Keep
    message_id INTEGER NOT NULL,
    user_id    INTEGER NOT NULL,
    text       TEXT NOT NULL,
    source     TEXT NOT NULL,             -- ai | profile
    at         REAL NOT NULL,
    PRIMARY KEY (message_id, user_id)
);
CREATE TABLE IF NOT EXISTS decisions ( -- the owners' verdicts, kept on this server only (a future spam filter learns from them)
    at      REAL NOT NULL,
    user_id INTEGER NOT NULL,
    text    TEXT NOT NULL,
    verdict TEXT NOT NULL,                -- spam | ok
    source  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS dm_posts (   -- posts an admin sent to the bot in a private chat
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_id   INTEGER NOT NULL,
    text       TEXT NOT NULL,                 -- Telegram HTML
    photo_id   TEXT,
    status     TEXT NOT NULL,                 -- new | scheduled | publishing | published | cancelled | missed
    at         REAL,                          -- when it goes out (scheduled)
    created    REAL NOT NULL,
    preview_id INTEGER,                       -- the preview message with the buttons
    links      TEXT NOT NULL DEFAULT '',      -- link buttons under the post, JSON [[label, url], …]
    pin_hours  INTEGER NOT NULL DEFAULT 0,    -- 0 = no pin, -1 = pinned until you unpin
    delete_hours INTEGER NOT NULL DEFAULT 0,  -- 0 = stays; else deleted from the channel after that many hours
    ad         INTEGER NOT NULL DEFAULT 0,    -- 1 = the ad label goes on top
    media      TEXT NOT NULL DEFAULT ''       -- JSON [[kind, file_id], …] for a video, GIF or album
);
CREATE TABLE IF NOT EXISTS timers (     -- things to do to a channel post later: unpin, delete
    message_id INTEGER NOT NULL,
    action     TEXT NOT NULL,             -- unpin | delete
    at         REAL NOT NULL,
    post_id    TEXT NOT NULL,
    PRIMARY KEY (message_id, action)
);
CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT NOT NULL);   -- choices made with /setup
CREATE TABLE IF NOT EXISTS chats (     -- channels and groups where the bot was made admin
    id     INTEGER PRIMARY KEY,
    type   TEXT NOT NULL,              -- channel | supergroup | group
    title  TEXT NOT NULL,
    admin  INTEGER NOT NULL,           -- 1 = the bot is admin there now
    at     REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS inbox (     -- messages people wrote to the channel, and suggested posts
    id         INTEGER PRIMARY KEY AUTOINCREMENT,   -- short number for buttons
    chat_id    INTEGER NOT NULL,          -- the channel's direct-messages chat
    topic_id   INTEGER NOT NULL,          -- one topic per person
    message_id INTEGER NOT NULL,
    user_id    INTEGER,
    name       TEXT NOT NULL,
    text       TEXT NOT NULL,
    kind       TEXT NOT NULL,             -- message | suggestion
    price      TEXT NOT NULL DEFAULT '',  -- «150 Stars» for a paid suggestion
    status     TEXT NOT NULL,             -- new | answered | approved | declined
    at         REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS join_requests (   -- people asking to join the group, waiting for a button
    user_id    INTEGER PRIMARY KEY,
    name       TEXT NOT NULL,
    deadline   REAL NOT NULL,
    message_id INTEGER                          -- the button in their private chat
);
CREATE TABLE IF NOT EXISTS actions (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    at        REAL NOT NULL,
    kind      TEXT NOT NULL,          -- warn | ban | unban | forgive | manual_ban | post
    user_id   INTEGER,
    user_name TEXT,
    reason    TEXT,
    excerpt   TEXT,
    by_admin  INTEGER
);
"""
KEEP_ACTIONS = 2000
KEEP_NOTES = 1000   # older log lines are dropped; the log is for recent history, not an archive


@dataclass(frozen=True)
class Draft:
    id: int
    post_id: str
    status: str
    comment: str
    created: float
    decided_by: int | None


@dataclass(frozen=True)
class DmPost:
    id: int
    admin_id: int
    text: str
    photo_id: str | None
    status: str
    at: float | None
    created: float
    preview_id: int | None
    links: str = ''
    pin_hours: int = 0
    delete_hours: int = 0
    ad: int = 0
    media: str = ''


@dataclass(frozen=True)
class InboxItem:
    id: int
    chat_id: int
    topic_id: int
    message_id: int
    user_id: int | None
    name: str
    text: str
    kind: str
    price: str
    status: str
    at: float


@dataclass(frozen=True)
class Feed:
    id: str
    signature: str
    checked: float | None
    ok: float | None
    error: str
    found: int
    skipped: int


@dataclass(frozen=True)
class Item:
    id: int
    post_id: str
    source: str
    name: str
    label: str
    text: str
    created: float
    status: str
    notified: int
    html: int = 0
    image: str = ''
    material: str = ''
    link: str = ''
    publisher: str = ''


@dataclass(frozen=True)
class Action:
    id: int
    at: float
    kind: str
    user_id: int | None
    user_name: str
    reason: str
    excerpt: str
    by_admin: int | None


class State:
    def __init__(self, data_dir: str):
        os.makedirs(data_dir, exist_ok=True)
        self.path = os.path.join(data_dir, 'keeper.db')
        # autocommit: every write is on disk at once. One event loop uses it, so the thread check is not needed.
        self.db = sqlite3.connect(self.path, isolation_level=None, check_same_thread=False)
        try:
            self.db.execute('PRAGMA journal_mode=WAL')
        except sqlite3.OperationalError as e:
            # Say what to fix instead of a bare traceback: the folder exists but this process may not write there.
            raise SystemExit(f'Cannot write the bot\'s memory in {data_dir} ({e}). The process runs as user id '
                             f'{os.getuid() if hasattr(os, "getuid") else "?"}; the folder must be writable for it. '
                             f'On Railway: Settings → Build → Builder «Railpack», or redeploy with the current Dockerfile.') from e
        self.db.executescript(SCHEMA)
        self._add_columns()
        self.migrated = self._import_json(os.path.join(data_dir, 'state.json'))

    def _add_columns(self) -> None:
        """Columns added after 0.4: old databases get them with values that keep their meaning."""
        have = {r[1] for r in self.db.execute('PRAGMA table_info(sent)')}
        if 'label' not in have:
            self.db.execute("ALTER TABLE sent ADD COLUMN label TEXT NOT NULL DEFAULT 'own'")
        if 'published' not in have:   # skipped old posts are remembered too, but never went out
            self.db.execute('ALTER TABLE sent ADD COLUMN published INTEGER NOT NULL DEFAULT 1')
        if 'at' not in {r[1] for r in self.db.execute('PRAGMA table_info(warns)')}:
            self.db.execute('ALTER TABLE warns ADD COLUMN at REAL NOT NULL DEFAULT 0')
            self.db.execute('UPDATE warns SET at=?', (time.time(),))   # warnings from before 1.8.6 count from now
        have = {r[1] for r in self.db.execute('PRAGMA table_info(items)')}
        for column, kind in (('html', 'INTEGER NOT NULL DEFAULT 0'), ('image', "TEXT NOT NULL DEFAULT ''"),
                             ('material', "TEXT NOT NULL DEFAULT ''"), ('link', "TEXT NOT NULL DEFAULT ''"),
                             ('publisher', "TEXT NOT NULL DEFAULT ''")):
            if have and column not in have:
                self.db.execute(f'ALTER TABLE items ADD COLUMN {column} {kind}')
        have = {r[1] for r in self.db.execute('PRAGMA table_info(dm_posts)')}
        for column, kind in (('links', "TEXT NOT NULL DEFAULT ''"), ('pin_hours', 'INTEGER NOT NULL DEFAULT 0'),
                             ('delete_hours', 'INTEGER NOT NULL DEFAULT 0'), ('ad', 'INTEGER NOT NULL DEFAULT 0'),
                             ('media', "TEXT NOT NULL DEFAULT ''")):
            if have and column not in have:
                self.db.execute(f'ALTER TABLE dm_posts ADD COLUMN {column} {kind}')
        have = {r[1] for r in self.db.execute('PRAGMA table_info(members)')}
        if 'clean' not in have:       # people known before 1.3 are regulars: no probation for them
            self.db.execute('ALTER TABLE members ADD COLUMN clean INTEGER NOT NULL DEFAULT 99')

    def _import_json(self, path: str) -> bool:
        if not os.path.exists(path):
            return False
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        now = time.time()
        with self.db:
            self.db.executemany('INSERT OR IGNORE INTO sent (post_id, at) VALUES (?, ?)',
                                [(str(pid), now) for pid in data.get('sent', [])])
            self.db.executemany('INSERT OR REPLACE INTO warns (user_id, count, at) VALUES (?, ?, ?)',
                                [(int(uid), int(n), now) for uid, n in (data.get('warns') or {}).items()])
        os.replace(path, path + '.migrated')
        return True

    # scheduled posts
    def is_sent(self, post_id: str) -> bool:
        return self.db.execute('SELECT 1 FROM sent WHERE post_id=?', (post_id,)).fetchone() is not None

    def mark_sent(self, post_id: str, label: str = 'own', published: bool = True, at: float | None = None) -> None:
        self.db.execute('INSERT OR IGNORE INTO sent (post_id, at, label, published) VALUES (?, ?, ?, ?)',
                        (post_id, time.time() if at is None else at, label, int(published)))

    def history(self, limit: int = 100) -> list[tuple[datetime, str]]:
        """[(when, label)] of posts that really went to the channel, newest first — for the channel rules."""
        rows = self.db.execute('SELECT at, label FROM sent WHERE published=1 ORDER BY at DESC LIMIT ?', (limit,))
        return [(datetime.fromtimestamp(at, timezone.utc), label) for at, label in rows]

    # feeds
    def is_seen(self, keys: list[str]) -> bool:
        marks = ','.join('?' * len(keys))
        return bool(keys) and self.db.execute(f'SELECT 1 FROM seen WHERE key IN ({marks})', keys).fetchone() is not None

    def mark_seen(self, keys: list[str]) -> None:
        now = time.time()
        # Refreshed every time: an entry still in the feed must not be forgotten after 30 days and come back as new.
        self.db.executemany('INSERT INTO seen VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET at=excluded.at',
                            [(k, now) for k in keys])

    def forget_seen(self, older_than: float) -> None:
        self.db.execute('DELETE FROM seen WHERE at < ?', (older_than,))

    def feed(self, source_id: str) -> Feed | None:
        r = self.db.execute('SELECT * FROM feeds WHERE id=?', (source_id,)).fetchone()
        return Feed(*r) if r else None

    def feed_primed(self, source_id: str, signature: str) -> None:
        self.db.execute('INSERT INTO feeds (id, signature) VALUES (?, ?) ON CONFLICT(id) DO UPDATE SET '
                        'signature=excluded.signature, found=0, skipped=0', (source_id, signature))

    def feed_checked(self, source_id: str, error: str = '', found: int = 0, skipped: int = 0) -> None:
        now = time.time()
        self.db.execute('UPDATE feeds SET checked=?, ok=CASE WHEN ?=\'\' THEN ? ELSE ok END, error=?, '
                        'found=found+?, skipped=skipped+? WHERE id=?',
                        (now, error, now, error[:300], found, skipped, source_id))

    def item_add(self, post_id: str, source: str, name: str, label: str, text: str, status: str,
                 html: bool = False, image: str = '', material: str = '', link: str = '', publisher: str = '') -> int:
        return self.db.execute('INSERT INTO items (post_id, source, name, label, text, created, status, html, image, '
                               'material, link, publisher) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                               (post_id, source, name, label, text, time.time(), status, int(html), image, material,
                                link, publisher)).lastrowid

    def item_set_text(self, item_id: int, text: str) -> None:
        self.db.execute('UPDATE items SET text=? WHERE id=?', (text, item_id))

    def item(self, item_id: int) -> Item | None:
        r = self.db.execute('SELECT * FROM items WHERE id=?', (item_id,)).fetchone()
        return Item(*r) if r else None

    def item_by_post(self, post_id: str) -> Item | None:
        r = self.db.execute('SELECT * FROM items WHERE post_id=?', (post_id,)).fetchone()
        return Item(*r) if r else None

    def item_move(self, item_id: int, to: str, frm: tuple) -> bool:
        """Like draft_move: only one caller wins, so nothing is published twice."""
        marks = ','.join('?' * len(frm))
        cur = self.db.execute(f'UPDATE items SET status=? WHERE id=? AND status IN ({marks})', (to, item_id, *frm))
        return cur.rowcount == 1

    def item_notified(self, item_id: int) -> None:
        self.db.execute('UPDATE items SET notified=1 WHERE id=?', (item_id,))

    def items_in(self, *statuses: str) -> list[Item]:
        marks = ','.join('?' * len(statuses))
        rows = self.db.execute(f'SELECT * FROM items WHERE status IN ({marks}) ORDER BY id', statuses).fetchall()
        return [Item(*r) for r in rows]

    def item_add_msg(self, item_id: int, admin_id: int, message_id: int) -> None:
        self.db.execute('INSERT INTO item_msgs VALUES (?, ?, ?)', (item_id, admin_id, message_id))

    def item_pop_msgs(self, item_id: int) -> list[tuple[int, int]]:
        rows = self.db.execute('SELECT admin_id, message_id FROM item_msgs WHERE item_id=?', (item_id,)).fetchall()
        self.db.execute('DELETE FROM item_msgs WHERE item_id=?', (item_id,))
        return [tuple(r) for r in rows]

    def items_today(self, source_id: str, since: float) -> int:
        return self.db.execute('SELECT COUNT(*) FROM items WHERE source=? AND created>=?', (source_id, since)).fetchone()[0]

    # warnings
    WARN_DAYS = 30            # a warning older than this is forgotten: one slip a year ago is not half a ban

    def add_warning(self, user_id: int) -> int:
        now = time.time()
        self.db.execute('INSERT INTO warns (user_id, count, at) VALUES (?, 1, ?) ON CONFLICT(user_id) DO UPDATE SET '
                        'count = CASE WHEN at < ? THEN 1 ELSE count + 1 END, at = ?',
                        (user_id, now, now - self.WARN_DAYS * 86400, now))
        return self.db.execute('SELECT count FROM warns WHERE user_id=?', (user_id,)).fetchone()[0]

    def clear_warnings(self, user_id: int) -> None:
        self.db.execute('DELETE FROM warns WHERE user_id=?', (user_id,))

    # action log
    def log_action(self, kind: str, user_id: int | None = None, user_name: str = '', reason: str = '',
                   excerpt: str = '', by_admin: int | None = None) -> int:
        cur = self.db.execute(
            'INSERT INTO actions (at, kind, user_id, user_name, reason, excerpt, by_admin) VALUES (?,?,?,?,?,?,?)',
            (time.time(), kind, user_id, user_name, reason, excerpt[:300], by_admin))
        self.db.execute('DELETE FROM actions WHERE id <= ?', (cur.lastrowid - KEEP_ACTIONS,))
        return cur.lastrowid

    # drafts
    def draft_for(self, post_id: str) -> Draft | None:
        r = self.db.execute('SELECT * FROM drafts WHERE post_id=?', (post_id,)).fetchone()
        return Draft(*r) if r else None

    def draft(self, draft_id: int) -> Draft | None:
        r = self.db.execute('SELECT * FROM drafts WHERE id=?', (draft_id,)).fetchone()
        return Draft(*r) if r else None

    def draft_create(self, post_id: str) -> int:
        return self.db.execute("INSERT INTO drafts (post_id, status, created) VALUES (?, 'pending', ?)",
                               (post_id, time.time())).lastrowid

    def draft_move(self, draft_id: int, to: str, frm: tuple, by: int | None = None) -> bool:
        """Change status only from one of `frm`. False when someone else already decided —
        that is what stops two admins publishing the same draft twice."""
        marks = ','.join('?' * len(frm))
        cur = self.db.execute(f'UPDATE drafts SET status=?, decided_by=COALESCE(?, decided_by) '
                              f'WHERE id=? AND status IN ({marks})', (to, by, draft_id, *frm))
        return cur.rowcount == 1

    def draft_comment(self, draft_id: int, comment: str) -> None:
        """New comment = new preview: back to pending, and the 48 h clock restarts."""
        self.db.execute("UPDATE drafts SET comment=?, status='pending', created=? WHERE id=?",
                        (comment, time.time(), draft_id))

    def drafts_in(self, *statuses: str) -> list[Draft]:
        marks = ','.join('?' * len(statuses))
        rows = self.db.execute(f'SELECT * FROM drafts WHERE status IN ({marks}) ORDER BY id', statuses).fetchall()
        return [Draft(*r) for r in rows]

    def draft_add_msg(self, draft_id: int, admin_id: int, message_id: int) -> None:
        self.db.execute('INSERT INTO draft_msgs VALUES (?, ?, ?)', (draft_id, admin_id, message_id))

    def draft_pop_msgs(self, draft_id: int) -> list[tuple[int, int]]:
        rows = self.db.execute('SELECT admin_id, message_id FROM draft_msgs WHERE draft_id=?', (draft_id,)).fetchall()
        self.db.execute('DELETE FROM draft_msgs WHERE draft_id=?', (draft_id,))
        return [tuple(r) for r in rows]

    def reconcile(self) -> int:
        """After a restart: anything left «publishing» (the bot stopped mid-send) either went out — then it is
        published — or goes back where it was, so it is not stuck with «Already done» forever."""
        n = 0
        for (pid,) in self.db.execute("SELECT post_id FROM items WHERE status='publishing'").fetchall():
            n += self.db.execute("UPDATE items SET status=? WHERE post_id=?",
                                 ('published' if self.is_sent(pid) else 'queued', pid)).rowcount
        for (did, pid) in self.db.execute("SELECT id, post_id FROM drafts WHERE status='publishing'").fetchall():
            n += self.db.execute('UPDATE drafts SET status=? WHERE id=?',
                                 ('published' if self.is_sent(pid) else 'approved', did)).rowcount
        for (did,) in self.db.execute("SELECT id FROM dm_posts WHERE status='publishing'").fetchall():
            n += self.db.execute('UPDATE dm_posts SET status=? WHERE id=?',
                                 ('published' if self.is_sent(f'dm:{did}') else 'missed', did)).rowcount
        return n

    # setup
    def get(self, key: str) -> str | None:
        row = self.db.execute('SELECT value FROM kv WHERE key=?', (key,)).fetchone()
        return row[0] if row else None

    def put(self, key: str, value: str) -> None:
        self.db.execute('INSERT INTO kv VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', (key, value))

    def chat_seen(self, chat_id: int, kind: str, title: str, admin: bool) -> None:
        self.db.execute('INSERT INTO chats VALUES (?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET '
                        'type=excluded.type, title=excluded.title, admin=excluded.admin, at=excluded.at',
                        (chat_id, kind, title or str(chat_id), int(admin), time.time()))

    def chats_where_admin(self, *kinds: str) -> list[tuple[int, str]]:
        marks = ','.join('?' * len(kinds))
        rows = self.db.execute(f'SELECT id, title FROM chats WHERE admin=1 AND type IN ({marks}) ORDER BY at DESC', kinds)
        return [tuple(r) for r in rows]

    def forget_person(self, user_id: int) -> int:
        """Everything the bot keeps about one person or channel — for a «delete my data» request."""
        n = 0
        for table, col in (('warns', 'user_id'), ('notes', 'user_id'), ('humans', 'user_id'), ('members', 'user_id'),
                           ('captchas', 'user_id'), ('actions', 'user_id'), ('reviews', 'user_id'),
                           ('decisions', 'user_id'), ('inbox', 'user_id'), ('join_requests', 'user_id')):
            n += self.db.execute(f'DELETE FROM {table} WHERE {col}=?', (user_id,)).rowcount
        return n

    def forget_old_actions(self, older_than: float) -> int:
        """The log, and everything already finished, older than keep_days. What is still open stays."""
        n = self.db.execute('DELETE FROM actions WHERE at < ?', (older_than,)).rowcount
        n += self.db.execute("DELETE FROM items WHERE created < ? AND status IN "
                             "('published', 'rejected', 'expired', 'skipped', 'failed')", (older_than,)).rowcount
        n += self.db.execute("DELETE FROM inbox WHERE at < ? AND status <> 'new'", (older_than,)).rowcount
        n += self.db.execute('DELETE FROM reviews WHERE at < ?', (older_than,)).rowcount
        n += self.db.execute("DELETE FROM drafts WHERE created < ? AND status IN "
                             "('published', 'rejected', 'expired', 'failed')", (older_than,)).rowcount
        n += self.db.execute("DELETE FROM dm_posts WHERE created < ? AND status IN ('published', 'cancelled')",
                             (older_than,)).rowcount
        self.db.execute("DELETE FROM kv WHERE key LIKE 'ai:%' AND key < ?",
                        (time.strftime('ai:%Y-%m', time.gmtime(older_than)),))
        return n

    # posts sent to the bot in a private chat
    def dm_add(self, admin_id: int, text: str, photo_id: str | None, media: str = '') -> int:
        return self.db.execute("INSERT INTO dm_posts (admin_id, text, photo_id, status, created, media) "
                               "VALUES (?,?,?,'new',?,?)", (admin_id, text, photo_id, time.time(), media)).lastrowid

    def dm(self, post_id: int) -> DmPost | None:
        r = self.db.execute('SELECT * FROM dm_posts WHERE id=?', (post_id,)).fetchone()
        return DmPost(*r) if r else None

    def dm_move(self, post_id: int, to: str, frm: tuple, at: float | None = None) -> bool:
        """Like draft_move: only one press wins, so a post never goes out twice."""
        marks = ','.join('?' * len(frm))
        cur = self.db.execute(f'UPDATE dm_posts SET status=?, at=COALESCE(?, at) WHERE id=? AND status IN ({marks})',
                              (to, at, post_id, *frm))
        return cur.rowcount == 1

    def dm_set(self, post_id: int, **fields) -> None:
        """Change the post's options: links, pin_hours, delete_hours, ad."""
        allowed = {'links', 'pin_hours', 'delete_hours', 'ad'}
        assert set(fields) <= allowed, fields
        sets = ', '.join(f'{k}=?' for k in fields)
        self.db.execute(f'UPDATE dm_posts SET {sets} WHERE id=?', (*fields.values(), post_id))

    # join requests
    def join_add(self, user_id: int, name: str, deadline: float) -> bool:
        return self.db.execute('INSERT OR IGNORE INTO join_requests (user_id, name, deadline) VALUES (?,?,?)',
                               (user_id, name, deadline)).rowcount == 1

    def join_set_message(self, user_id: int, message_id: int) -> None:
        self.db.execute('UPDATE join_requests SET message_id=? WHERE user_id=?', (message_id, user_id))

    def join_take(self, user_id: int) -> tuple[str, int | None] | None:
        """(name, message_id) and the request is closed; None if already closed — one outcome per request."""
        row = self.db.execute('SELECT name, message_id FROM join_requests WHERE user_id=?', (user_id,)).fetchone()
        if row is None or self.db.execute('DELETE FROM join_requests WHERE user_id=?', (user_id,)).rowcount != 1:
            return None
        return tuple(row)

    def joins_due(self, now: float) -> list[int]:
        return [r[0] for r in self.db.execute('SELECT user_id FROM join_requests WHERE deadline<=?', (now,))]

    # the channel's inbox
    def inbox_add(self, chat_id: int, topic_id: int, message_id: int, user_id: int | None, name: str, text: str,
                  kind: str, price: str = '') -> int:
        return self.db.execute('INSERT INTO inbox (chat_id, topic_id, message_id, user_id, name, text, kind, price, status, at) '
                               "VALUES (?,?,?,?,?,?,?,?,'new',?)",
                               (chat_id, topic_id, message_id, user_id, name, text[:3000], kind, price, time.time())).lastrowid

    def inbox(self, item_id: int) -> InboxItem | None:
        r = self.db.execute('SELECT * FROM inbox WHERE id=?', (item_id,)).fetchone()
        return InboxItem(*r) if r else None

    def inbox_move(self, item_id: int, to: str, frm: tuple) -> bool:
        marks = ','.join('?' * len(frm))
        return self.db.execute(f'UPDATE inbox SET status=? WHERE id=? AND status IN ({marks})',
                               (to, item_id, *frm)).rowcount == 1

    def inbox_open(self) -> list[InboxItem]:
        return [InboxItem(*r) for r in self.db.execute("SELECT * FROM inbox WHERE status='new' ORDER BY id").fetchall()]

    # timers on channel posts
    def timer_add(self, message_id: int, action: str, at: float, post_id: str) -> None:
        self.db.execute('INSERT OR REPLACE INTO timers VALUES (?,?,?,?)', (message_id, action, at, post_id))

    def timers_due(self, now: float) -> list[tuple[int, str, str]]:
        return [tuple(r) for r in self.db.execute('SELECT message_id, action, post_id FROM timers WHERE at<=? ORDER BY at',
                                                  (now,))]

    def timer_done(self, message_id: int, action: str) -> bool:
        return self.db.execute('DELETE FROM timers WHERE message_id=? AND action=?', (message_id, action)).rowcount == 1

    def timers_for(self, post_id: str) -> list[tuple[str, float]]:
        return [tuple(r) for r in self.db.execute('SELECT action, at FROM timers WHERE post_id=? ORDER BY at', (post_id,))]

    def dm_set_preview(self, post_id: int, message_id: int) -> None:
        self.db.execute('UPDATE dm_posts SET preview_id=? WHERE id=?', (message_id, post_id))

    def dm_in(self, *statuses: str) -> list[DmPost]:
        marks = ','.join('?' * len(statuses))
        rows = self.db.execute(f'SELECT * FROM dm_posts WHERE status IN ({marks}) ORDER BY at, id', statuses)
        return [DmPost(*r) for r in rows.fetchall()]

    # members the bot has seen behave
    def mark_known(self, user_id: int, clean_message: bool = False) -> None:
        """Seen behaving. clean_message: a real message (long enough) that counts toward ending probation."""
        self.db.execute('INSERT OR IGNORE INTO members (user_id, since, clean) VALUES (?, ?, 0)', (user_id, time.time()))
        if clean_message:
            self.db.execute('UPDATE members SET clean = clean + 1 WHERE user_id=?', (user_id,))

    def trust(self, user_id: int) -> None:
        """An owner vouched for this person: no probation, no more questions."""
        self.mark_known(user_id)
        self.db.execute('UPDATE members SET clean = MAX(clean, 99) WHERE user_id=?', (user_id,))

    def clean_count(self, user_id: int) -> int:
        row = self.db.execute('SELECT clean FROM members WHERE user_id=?', (user_id,)).fetchone()
        return row[0] if row else 0

    # owners' Delete / Keep
    def review_add(self, message_id: int, user_id: int, text: str, source: str) -> None:
        self.db.execute('INSERT OR REPLACE INTO reviews VALUES (?,?,?,?,?)', (message_id, user_id, text[:2000], source, time.time()))

    REVIEW_HOURS = 24         # an unanswered review lapses: the person is not stuck «under review» forever

    def review_open(self, user_id: int) -> bool:
        since = time.time() - self.REVIEW_HOURS * 3600
        return self.db.execute('SELECT 1 FROM reviews WHERE user_id=? AND at>=?', (user_id, since)).fetchone() is not None

    def review_decide(self, message_id: int, user_id: int, verdict: str) -> bool:
        """Store the verdict with the message text; False when it was already decided."""
        row = self.db.execute('SELECT text, source FROM reviews WHERE message_id=? AND user_id=?', (message_id, user_id)).fetchone()
        if row is None:
            return False
        if self.db.execute('DELETE FROM reviews WHERE message_id=? AND user_id=?', (message_id, user_id)).rowcount != 1:
            return False
        self.db.execute('INSERT INTO decisions VALUES (?,?,?,?,?)', (time.time(), user_id, row[0], verdict, row[1]))
        return True

    def examples(self) -> list[tuple[str, str]]:
        """What the learning filter learns from: owners' verdicts, and the start of messages the rules removed."""
        # Profile reviews are left out: there the text was clean and the ad sat in the profile, so «Delete»
        # says nothing about the words. Messages blocked for being sent as a channel are left out for the same reason.
        rows = self.db.execute("SELECT text, verdict FROM decisions WHERE source <> 'profile'").fetchall()
        rows += [(r[0], 'spam') for r in self.db.execute(
            "SELECT excerpt FROM actions WHERE kind IN ('warn', 'ban', 'manual_ban') AND excerpt <> '' "
            "AND reason NOT LIKE 'message on behalf of a channel%'")]
        return [tuple(r) for r in rows]

    def decisions_count(self) -> dict:
        return dict(self.db.execute('SELECT verdict, COUNT(*) FROM decisions GROUP BY verdict').fetchall())

    def known_since(self, user_id: int) -> float | None:
        row = self.db.execute('SELECT since FROM members WHERE user_id=?', (user_id,)).fetchone()
        return row[0] if row else None

    # captcha
    def is_human(self, user_id: int) -> bool:
        return self.db.execute('SELECT 1 FROM humans WHERE user_id=?', (user_id,)).fetchone() is not None

    def mark_human(self, user_id: int) -> None:
        self.db.execute('INSERT OR IGNORE INTO humans VALUES (?, ?)', (user_id, time.time()))

    def captcha_add(self, user_id: int, deadline: float, reason: str, name: str = '') -> bool:
        """False when this person already has a captcha open — one button per person."""
        cur = self.db.execute('INSERT OR IGNORE INTO captchas (user_id, deadline, reason, name) VALUES (?, ?, ?, ?)',
                              (user_id, deadline, reason, name))
        return cur.rowcount == 1

    def captcha_set_message(self, user_id: int, message_id: int) -> None:
        self.db.execute('UPDATE captchas SET message_id=? WHERE user_id=?', (message_id, user_id))

    def captcha_open(self, user_id: int) -> bool:
        return self.db.execute('SELECT 1 FROM captchas WHERE user_id=?', (user_id,)).fetchone() is not None

    def captcha_take(self, user_id: int) -> tuple[int | None, str, str] | None:
        """(message_id, reason, name) and the captcha is closed; None when it was already closed —
        so a press and the timeout cannot both act."""
        row = self.db.execute('SELECT message_id, reason, name FROM captchas WHERE user_id=?', (user_id,)).fetchone()
        if row is None:
            return None
        cur = self.db.execute('DELETE FROM captchas WHERE user_id=?', (user_id,))
        return tuple(row) if cur.rowcount == 1 else None

    def captchas_due(self, now: float) -> list[int]:
        return [r[0] for r in self.db.execute('SELECT user_id FROM captchas WHERE deadline<=?', (now,))]

    # admin notifications with buttons
    def add_note(self, user_id: int, admin_id: int, message_id: int, text: str) -> None:
        cur = self.db.execute('INSERT INTO notes VALUES (?, ?, ?, ?)', (user_id, admin_id, message_id, text))
        # Warnings nobody follows up stay here; keep only the newest ones.
        self.db.execute('DELETE FROM notes WHERE rowid <= ?', (cur.lastrowid - KEEP_NOTES,))

    def pop_notes(self, user_id: int) -> list[tuple[int, int, str]]:
        """[(admin_id, message_id, text)] still showing buttons about this user; forgotten after reading."""
        rows = self.db.execute('SELECT admin_id, message_id, text FROM notes WHERE user_id=?', (user_id,)).fetchall()
        self.db.execute('DELETE FROM notes WHERE user_id=?', (user_id,))
        return [tuple(r) for r in rows]

    def name_of(self, user_id: int) -> str:
        """The last name the log saw for this user — buttons carry only the id."""
        row = self.db.execute("SELECT user_name FROM actions WHERE user_id=? AND user_name<>'' ORDER BY id DESC LIMIT 1",
                              (user_id,)).fetchone()
        return row[0] if row else ''

    def recent_actions(self, limit: int = 20, who: str | None = None) -> list[Action]:
        """Newest first. `who` = a user or channel id, or a name like @someone — only their actions."""
        if who is None:
            rows = self.db.execute('SELECT * FROM actions ORDER BY id DESC LIMIT ?', (limit,))
        elif who.lstrip('-').isdigit():
            rows = self.db.execute('SELECT * FROM actions WHERE user_id=? ORDER BY id DESC LIMIT ?', (int(who), limit))
        else:
            rows = self.db.execute('SELECT * FROM actions WHERE lower(user_name)=lower(?) ORDER BY id DESC LIMIT ?',
                                   (who, limit))
        return [Action(*r) for r in rows.fetchall()]
