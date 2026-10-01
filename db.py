import sqlite3
import time

from flask import current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT UNIQUE NOT NULL COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    lang1         TEXT,
    lang2         TEXT,
    lang3         TEXT,
    created_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ranked_at     TEXT
);

CREATE TABLE IF NOT EXISTS rankings (
    ranker_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    ranked_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    position  INTEGER NOT NULL,
    PRIMARY KEY (ranker_id, ranked_id)
);

CREATE TABLE IF NOT EXISTS login_failures (
    key TEXT NOT NULL,
    at  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS login_failures_key ON login_failures (key, at);
"""


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(app):
    with app.app_context():
        get_db().executescript(SCHEMA)
    app.teardown_appcontext(close_db)


def pool():
    """Users who have finished their profile, in signup order."""
    return get_db().execute(
        "SELECT * FROM users WHERE lang1 IS NOT NULL ORDER BY id"
    ).fetchall()


def rankings_for(user_ids):
    rows = get_db().execute(
        "SELECT ranker_id, ranked_id FROM rankings ORDER BY ranker_id, position"
    ).fetchall()
    wanted = set(user_ids)
    out = {}
    for r in rows:
        if r["ranker_id"] in wanted:
            out.setdefault(r["ranker_id"], []).append(r["ranked_id"])
    return out


def save_ranking(user_id, ordered_ids):
    db = get_db()
    with db:
        db.execute("DELETE FROM rankings WHERE ranker_id = ?", (user_id,))
        db.executemany(
            "INSERT INTO rankings (ranker_id, ranked_id, position) VALUES (?, ?, ?)",
            [(user_id, other, i) for i, other in enumerate(ordered_ids)],
        )
        db.execute("UPDATE users SET ranked_at = CURRENT_TIMESTAMP WHERE id = ?", (user_id,))


def recent_failures(key, window):
    """Failed logins recorded against `key` in the last `window` seconds."""
    return get_db().execute(
        "SELECT COUNT(*) FROM login_failures WHERE key = ? AND at > ?",
        (key, time.time() - window),
    ).fetchone()[0]


def record_failure(keys, window):
    db = get_db()
    now = time.time()
    with db:
        db.execute("DELETE FROM login_failures WHERE at <= ?", (now - window,))
        db.executemany("INSERT INTO login_failures (key, at) VALUES (?, ?)", [(k, now) for k in keys])


def clear_failures(key):
    db = get_db()
    with db:
        db.execute("DELETE FROM login_failures WHERE key = ?", (key,))
