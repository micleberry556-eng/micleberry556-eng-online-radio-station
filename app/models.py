"""Database models and initialization for the radio station.

Uses raw SQLite via the sqlite3 module — no ORM dependency, works everywhere.
The database file is created automatically on first run.
"""

import sqlite3
import os
import time
from typing import Optional

from flask import Flask, g
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------


def get_db_path(app: Optional[Flask] = None) -> str:
    """Return the absolute path to the SQLite database file."""
    if app is not None:
        return app.config["DATABASE_PATH"]
    from flask import current_app

    return current_app.config["DATABASE_PATH"]


def get_db() -> sqlite3.Connection:
    """Return a per-request database connection (stored on Flask *g*)."""
    if "db" not in g:
        g.db = sqlite3.connect(get_db_path())
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db


def close_db(_exc: Optional[BaseException] = None) -> None:
    """Close the per-request database connection."""
    db: Optional[sqlite3.Connection] = g.pop("db", None)
    if db is not None:
        db.close()


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    username    TEXT    NOT NULL UNIQUE,
    password    TEXT    NOT NULL,
    is_admin    INTEGER NOT NULL DEFAULT 1,
    created_at  REAL    NOT NULL
);

CREATE TABLE IF NOT EXISTS stations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    slug        TEXT    NOT NULL UNIQUE,
    description TEXT    NOT NULL DEFAULT '',
    genre       TEXT    NOT NULL DEFAULT '',
    image_url   TEXT    NOT NULL DEFAULT '',
    image_file  TEXT    NOT NULL DEFAULT '',
    is_active   INTEGER NOT NULL DEFAULT 1,
    sort_order  INTEGER NOT NULL DEFAULT 0,
    created_at  REAL    NOT NULL
);

CREATE TABLE IF NOT EXISTS tracks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    station_id  INTEGER NOT NULL REFERENCES stations(id) ON DELETE CASCADE,
    title       TEXT    NOT NULL,
    artist      TEXT    NOT NULL DEFAULT '',
    filename    TEXT    NOT NULL,
    duration    REAL    NOT NULL DEFAULT 0,
    file_size   INTEGER NOT NULL DEFAULT 0,
    sort_order  INTEGER NOT NULL DEFAULT 0,
    created_at  REAL    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tracks_station ON tracks(station_id, sort_order);

CREATE TABLE IF NOT EXISTS domains (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    domain      TEXT    NOT NULL UNIQUE,
    is_primary  INTEGER NOT NULL DEFAULT 0,
    is_active   INTEGER NOT NULL DEFAULT 1,
    created_at  REAL    NOT NULL
);

CREATE TABLE IF NOT EXISTS pages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT    NOT NULL,
    slug        TEXT    NOT NULL UNIQUE,
    page_type   TEXT    NOT NULL DEFAULT 'custom',
    content     TEXT    NOT NULL DEFAULT '',
    is_active   INTEGER NOT NULL DEFAULT 1,
    sort_order  INTEGER NOT NULL DEFAULT 0,
    created_at  REAL    NOT NULL
);

CREATE TABLE IF NOT EXISTS site_settings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    key         TEXT    NOT NULL UNIQUE,
    value       TEXT    NOT NULL DEFAULT ''
);
"""

# Allowed page types for the pages section.
PAGE_TYPES = [
    ("charts", "Чарты"),
    ("ads", "Реклама"),
    ("subscription", "Подписка"),
    ("custom", "Произвольная"),
]

# ---------------------------------------------------------------------------
# Migration helpers — add columns that may not exist in older databases.
# ---------------------------------------------------------------------------

_MIGRATIONS_SQL = [
    "ALTER TABLE stations ADD COLUMN image_file TEXT NOT NULL DEFAULT ''",
]


# ---------------------------------------------------------------------------
# Seed data — demo Radio Record stations
# ---------------------------------------------------------------------------

_DEMO_STATIONS = [
    {
        "name": "Record",
        "slug": "record",
        "description": "Главная станция Radio Record — лучшая электронная и танцевальная музыка",
        "genre": "Dance / Electronic",
        "image_url": "/static/img/stations/record.png",
    },
    {
        "name": "Deep",
        "slug": "deep",
        "description": "Глубокий хаус и мелодичная электроника",
        "genre": "Deep House",
        "image_url": "/static/img/stations/deep.png",
    },
    {
        "name": "Chill-Out",
        "slug": "chillout",
        "description": "Расслабляющая музыка для отдыха и работы",
        "genre": "Chill-Out / Lounge",
        "image_url": "/static/img/stations/chillout.png",
    },
    {
        "name": "Trancemission",
        "slug": "trancemission",
        "description": "Лучший транс от мировых диджеев",
        "genre": "Trance",
        "image_url": "/static/img/stations/trancemission.png",
    },
    {
        "name": "Супердискотека 90-х",
        "slug": "sd90",
        "description": "Хиты 90-х, которые знает каждый",
        "genre": "Eurodance / Pop 90s",
        "image_url": "/static/img/stations/sd90.png",
    },
    {
        "name": "Russian Mix",
        "slug": "russianmix",
        "description": "Лучшие русские хиты в танцевальных ремиксах",
        "genre": "Russian Dance",
        "image_url": "/static/img/stations/russianmix.png",
    },
    {
        "name": "Lo-Fi",
        "slug": "lofi",
        "description": "Lo-Fi биты для учёбы и концентрации",
        "genre": "Lo-Fi / Beats",
        "image_url": "/static/img/stations/lofi.png",
    },
    {
        "name": "Techno",
        "slug": "techno",
        "description": "Жёсткий техно для настоящих ценителей",
        "genre": "Techno",
        "image_url": "/static/img/stations/techno.png",
    },
    {
        "name": "Drum'n'Bass",
        "slug": "dnb",
        "description": "Быстрые брейки и мощный бас",
        "genre": "Drum and Bass",
        "image_url": "/static/img/stations/dnb.png",
    },
    {
        "name": "Rock",
        "slug": "rock",
        "description": "Лучший рок всех времён",
        "genre": "Rock",
        "image_url": "/static/img/stations/rock.png",
    },
]


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


def _run_migrations(conn: sqlite3.Connection) -> None:
    """Apply schema migrations that add columns to existing tables."""
    for sql in _MIGRATIONS_SQL:
        try:
            conn.execute(sql)
        except sqlite3.OperationalError:
            # Column already exists — safe to ignore.
            pass


def _seed_site_settings(conn: sqlite3.Connection) -> None:
    """Insert default site settings if the table is empty."""
    row = conn.execute("SELECT COUNT(*) FROM site_settings").fetchone()
    if row[0] == 0:
        defaults = [
            ("theme", "default"),
            ("background_image", ""),
            ("site_title", "Онлайн Радио"),
        ]
        conn.executemany(
            "INSERT INTO site_settings (key, value) VALUES (?, ?)", defaults
        )


def get_site_settings(db: sqlite3.Connection) -> dict[str, str]:
    """Return all site_settings rows as a ``{key: value}`` dict."""
    rows = db.execute("SELECT key, value FROM site_settings").fetchall()
    return {r["key"]: r["value"] for r in rows}


def set_site_setting(db: sqlite3.Connection, key: str, value: str) -> None:
    """Upsert a single site setting."""
    db.execute(
        "INSERT INTO site_settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


def init_db(app: Flask) -> None:
    """Create tables and seed demo data if the database is empty."""
    db_path = app.config["DATABASE_PATH"]
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.executescript(_SCHEMA_SQL)
    _run_migrations(conn)

    # Seed admin user if none exists
    row = conn.execute("SELECT COUNT(*) FROM users").fetchone()
    if row[0] == 0:
        now = time.time()
        conn.execute(
            "INSERT INTO users (username, password, is_admin, created_at) VALUES (?, ?, 1, ?)",
            (
                app.config["DEFAULT_ADMIN_USERNAME"],
                generate_password_hash(app.config["DEFAULT_ADMIN_PASSWORD"]),
                now,
            ),
        )

    # Seed demo stations if none exist
    row = conn.execute("SELECT COUNT(*) FROM stations").fetchone()
    if row[0] == 0:
        now = time.time()
        for idx, st in enumerate(_DEMO_STATIONS):
            conn.execute(
                "INSERT INTO stations (name, slug, description, genre, image_url, sort_order, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    st["name"],
                    st["slug"],
                    st["description"],
                    st["genre"],
                    st["image_url"],
                    idx,
                    now,
                ),
            )

    _seed_site_settings(conn)

    conn.commit()
    conn.close()

    # Register teardown
    app.teardown_appcontext(close_db)


# ---------------------------------------------------------------------------
# User model for Flask-Login
# ---------------------------------------------------------------------------


class User(UserMixin):
    """Lightweight user object backed by a SQLite row."""

    def __init__(
        self, user_id: int, username: str, password_hash: str, is_admin: bool
    ) -> None:
        self.id = user_id
        self.username = username
        self.password_hash = password_hash
        self.is_admin = is_admin

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @staticmethod
    def get_by_id(user_id: int) -> Optional["User"]:
        db = get_db()
        row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if row is None:
            return None
        return User(row["id"], row["username"], row["password"], bool(row["is_admin"]))

    @staticmethod
    def get_by_username(username: str) -> Optional["User"]:
        db = get_db()
        row = db.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        if row is None:
            return None
        return User(row["id"], row["username"], row["password"], bool(row["is_admin"]))
