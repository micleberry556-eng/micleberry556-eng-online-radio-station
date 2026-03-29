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
# Seed pages — pre-built content pages with styled HTML
# ---------------------------------------------------------------------------

_DEMO_PAGES = [
    {
        "title": "Топ чарт",
        "slug": "charts",
        "page_type": "charts",
        "sort_order": 0,
        "content": """
<div class="pg-section">
    <p class="pg-lead">Самые горячие треки этой недели по версии наших слушателей.</p>

    <div class="chart-list">
        <div class="chart-item chart-gold">
            <span class="chart-pos">1</span>
            <div class="chart-info">
                <span class="chart-title">Blinding Lights</span>
                <span class="chart-artist">The Weeknd</span>
            </div>
            <span class="chart-badge">&#9733; HIT</span>
        </div>
        <div class="chart-item chart-silver">
            <span class="chart-pos">2</span>
            <div class="chart-info">
                <span class="chart-title">Levitating</span>
                <span class="chart-artist">Dua Lipa</span>
            </div>
            <span class="chart-badge">&#9650; +3</span>
        </div>
        <div class="chart-item chart-bronze">
            <span class="chart-pos">3</span>
            <div class="chart-info">
                <span class="chart-title">Save Your Tears</span>
                <span class="chart-artist">The Weeknd & Ariana Grande</span>
            </div>
            <span class="chart-badge">&#9650; +1</span>
        </div>
        <div class="chart-item">
            <span class="chart-pos">4</span>
            <div class="chart-info">
                <span class="chart-title">Stay</span>
                <span class="chart-artist">The Kid LAROI & Justin Bieber</span>
            </div>
            <span class="chart-badge">NEW</span>
        </div>
        <div class="chart-item">
            <span class="chart-pos">5</span>
            <div class="chart-info">
                <span class="chart-title">Heat Waves</span>
                <span class="chart-artist">Glass Animals</span>
            </div>
            <span class="chart-badge">&#9650; +2</span>
        </div>
        <div class="chart-item">
            <span class="chart-pos">6</span>
            <div class="chart-info">
                <span class="chart-title">Peaches</span>
                <span class="chart-artist">Justin Bieber ft. Daniel Caesar</span>
            </div>
            <span class="chart-badge">&#9660; -1</span>
        </div>
        <div class="chart-item">
            <span class="chart-pos">7</span>
            <div class="chart-info">
                <span class="chart-title">Montero</span>
                <span class="chart-artist">Lil Nas X</span>
            </div>
            <span class="chart-badge">&#9650; +4</span>
        </div>
        <div class="chart-item">
            <span class="chart-pos">8</span>
            <div class="chart-info">
                <span class="chart-title">Kiss Me More</span>
                <span class="chart-artist">Doja Cat ft. SZA</span>
            </div>
            <span class="chart-badge">&#9660; -2</span>
        </div>
        <div class="chart-item">
            <span class="chart-pos">9</span>
            <div class="chart-info">
                <span class="chart-title">Astronaut In The Ocean</span>
                <span class="chart-artist">Masked Wolf</span>
            </div>
            <span class="chart-badge">NEW</span>
        </div>
        <div class="chart-item">
            <span class="chart-pos">10</span>
            <div class="chart-info">
                <span class="chart-title">drivers license</span>
                <span class="chart-artist">Olivia Rodrigo</span>
            </div>
            <span class="chart-badge">&#9660; -3</span>
        </div>
    </div>
</div>
""",
    },
    {
        "title": "Реклама",
        "slug": "ads",
        "page_type": "ads",
        "sort_order": 1,
        "content": """
<div class="pg-section">
    <p class="pg-lead">Размещайте рекламу на нашем радио и достигайте тысяч слушателей ежедневно.</p>

    <div class="pg-cards">
        <div class="pg-card pg-card-accent">
            <div class="pg-card-icon">&#127897;</div>
            <h3>Аудио-ролики</h3>
            <p>Ваш рекламный ролик в эфире между треками. До 30 секунд, профессиональная озвучка.</p>
            <div class="pg-price">от 5 000 &#8381;/нед</div>
        </div>
        <div class="pg-card pg-card-accent">
            <div class="pg-card-icon">&#127912;</div>
            <h3>Баннер на сайте</h3>
            <p>Графический баннер на главной странице и страницах станций. Видят все посетители.</p>
            <div class="pg-price">от 3 000 &#8381;/нед</div>
        </div>
        <div class="pg-card pg-card-accent">
            <div class="pg-card-icon">&#11088;</div>
            <h3>Спонсорство станции</h3>
            <p>Ваш бренд — спонсор целой станции. Логотип, упоминания в эфире, эксклюзивность.</p>
            <div class="pg-price">от 15 000 &#8381;/мес</div>
        </div>
    </div>

    <div class="pg-cta-box">
        <h3>Готовы начать?</h3>
        <p>Свяжитесь с нами для обсуждения индивидуальных условий размещения.</p>
        <div class="pg-cta-contacts">
            <span>&#9993; ads@onlineradio.ru</span>
            <span>&#9742; +7 (999) 123-45-67</span>
        </div>
    </div>
</div>
""",
    },
    {
        "title": "Подписка",
        "slug": "subscription",
        "page_type": "subscription",
        "sort_order": 2,
        "content": """
<div class="pg-section">
    <p class="pg-lead">Выберите план и наслаждайтесь музыкой без ограничений.</p>

    <div class="pg-pricing">
        <div class="pg-plan">
            <div class="pg-plan-header">
                <h3>Free</h3>
                <div class="pg-plan-price">0 &#8381;<span>/мес</span></div>
            </div>
            <ul class="pg-plan-features">
                <li>&#10003; Все станции</li>
                <li>&#10003; Стандартное качество 128 kbps</li>
                <li>&#10003; Реклама в эфире</li>
                <li class="pg-plan-disabled">&#10007; Без рекламы</li>
                <li class="pg-plan-disabled">&#10007; Высокое качество</li>
                <li class="pg-plan-disabled">&#10007; Офлайн-режим</li>
            </ul>
            <div class="pg-plan-action">
                <span class="pg-btn pg-btn-outline">Текущий план</span>
            </div>
        </div>

        <div class="pg-plan pg-plan-popular">
            <div class="pg-plan-badge">Популярный</div>
            <div class="pg-plan-header">
                <h3>Premium</h3>
                <div class="pg-plan-price">299 &#8381;<span>/мес</span></div>
            </div>
            <ul class="pg-plan-features">
                <li>&#10003; Все станции</li>
                <li>&#10003; Качество 320 kbps</li>
                <li>&#10003; Без рекламы</li>
                <li>&#10003; Эквалайзер</li>
                <li class="pg-plan-disabled">&#10007; Офлайн-режим</li>
                <li class="pg-plan-disabled">&#10007; Эксклюзивный контент</li>
            </ul>
            <div class="pg-plan-action">
                <span class="pg-btn pg-btn-primary">Выбрать</span>
            </div>
        </div>

        <div class="pg-plan">
            <div class="pg-plan-header">
                <h3>VIP</h3>
                <div class="pg-plan-price">599 &#8381;<span>/мес</span></div>
            </div>
            <ul class="pg-plan-features">
                <li>&#10003; Все станции</li>
                <li>&#10003; Lossless качество</li>
                <li>&#10003; Без рекламы</li>
                <li>&#10003; Эквалайзер</li>
                <li>&#10003; Офлайн-режим</li>
                <li>&#10003; Эксклюзивные миксы</li>
            </ul>
            <div class="pg-plan-action">
                <span class="pg-btn pg-btn-primary">Выбрать</span>
            </div>
        </div>
    </div>
</div>
""",
    },
    {
        "title": "Расписание эфира",
        "slug": "schedule",
        "page_type": "custom",
        "sort_order": 3,
        "content": """
<div class="pg-section">
    <p class="pg-lead">Программа передач на эту неделю. Не пропустите любимые шоу!</p>

    <div class="schedule-grid">
        <div class="schedule-day">
            <h3 class="schedule-day-title">Понедельник — Пятница</h3>
            <div class="schedule-items">
                <div class="schedule-item">
                    <span class="schedule-time">06:00 — 10:00</span>
                    <div class="schedule-show">
                        <span class="schedule-name">Утреннее шоу</span>
                        <span class="schedule-desc">Бодрые хиты и новости для отличного начала дня</span>
                    </div>
                </div>
                <div class="schedule-item">
                    <span class="schedule-time">10:00 — 14:00</span>
                    <div class="schedule-show">
                        <span class="schedule-name">Дневной микс</span>
                        <span class="schedule-desc">Лучшие треки всех жанров нон-стоп</span>
                    </div>
                </div>
                <div class="schedule-item">
                    <span class="schedule-time">14:00 — 18:00</span>
                    <div class="schedule-show">
                        <span class="schedule-name">Хит-парад</span>
                        <span class="schedule-desc">Топ-20 треков недели по голосованию слушателей</span>
                    </div>
                </div>
                <div class="schedule-item">
                    <span class="schedule-time">18:00 — 22:00</span>
                    <div class="schedule-show">
                        <span class="schedule-name">Вечерний драйв</span>
                        <span class="schedule-desc">Энергичная музыка для вечера</span>
                    </div>
                </div>
                <div class="schedule-item">
                    <span class="schedule-time">22:00 — 02:00</span>
                    <div class="schedule-show">
                        <span class="schedule-name">Ночной сет</span>
                        <span class="schedule-desc">Deep house и chill-out для ночных слушателей</span>
                    </div>
                </div>
            </div>
        </div>

        <div class="schedule-day">
            <h3 class="schedule-day-title">Суббота — Воскресенье</h3>
            <div class="schedule-items">
                <div class="schedule-item">
                    <span class="schedule-time">08:00 — 12:00</span>
                    <div class="schedule-show">
                        <span class="schedule-name">Weekend Vibes</span>
                        <span class="schedule-desc">Расслабленные хиты для ленивого утра</span>
                    </div>
                </div>
                <div class="schedule-item">
                    <span class="schedule-time">12:00 — 18:00</span>
                    <div class="schedule-show">
                        <span class="schedule-name">Дискотека 90-х</span>
                        <span class="schedule-desc">Легендарные хиты золотой эпохи</span>
                    </div>
                </div>
                <div class="schedule-item">
                    <span class="schedule-time">18:00 — 00:00</span>
                    <div class="schedule-show">
                        <span class="schedule-name">DJ-сет Live</span>
                        <span class="schedule-desc">Живые миксы от приглашённых диджеев</span>
                    </div>
                </div>
                <div class="schedule-item">
                    <span class="schedule-time">00:00 — 08:00</span>
                    <div class="schedule-show">
                        <span class="schedule-name">Ambient Night</span>
                        <span class="schedule-desc">Атмосферная электроника до утра</span>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>
""",
    },
    {
        "title": "О нас",
        "slug": "about",
        "page_type": "custom",
        "sort_order": 4,
        "content": """
<div class="pg-section">
    <p class="pg-lead">Мы — команда меломанов, которые создали радио для таких же, как мы.</p>

    <div class="pg-cards">
        <div class="pg-card">
            <div class="pg-card-icon">&#127911;</div>
            <h3>10 станций</h3>
            <p>От deep house до рока — каждый найдёт свою волну.</p>
        </div>
        <div class="pg-card">
            <div class="pg-card-icon">&#127760;</div>
            <h3>24/7 в эфире</h3>
            <p>Музыка не останавливается ни на секунду, круглосуточно.</p>
        </div>
        <div class="pg-card">
            <div class="pg-card-icon">&#128101;</div>
            <h3>Синхронный эфир</h3>
            <p>Все слушатели на одной волне — как настоящее радио.</p>
        </div>
    </div>

    <div class="pg-about-story">
        <h2>Наша история</h2>
        <p>Проект стартовал в 2024 году как небольшой эксперимент — можно ли сделать онлайн-радио, где все слушатели слышат одно и то же одновременно? Оказалось, можно. И это оказалось невероятно круто.</p>
        <p>Сегодня нас слушают тысячи людей каждый день. Мы тщательно подбираем плейлисты, приглашаем диджеев и постоянно добавляем новые станции.</p>
        <p>Наша миссия — дарить людям настоящее радио в цифровую эпоху. Без алгоритмов, без пузырей фильтров — просто отличная музыка для всех.</p>
    </div>

    <div class="pg-cta-box">
        <h3>Хотите сотрудничать?</h3>
        <p>Мы открыты для диджеев, музыкантов и партнёров.</p>
        <div class="pg-cta-contacts">
            <span>&#9993; hello@onlineradio.ru</span>
            <span>&#9742; +7 (999) 000-00-00</span>
        </div>
    </div>
</div>
""",
    },
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

    # Seed demo pages if none exist
    row = conn.execute("SELECT COUNT(*) FROM pages").fetchone()
    if row[0] == 0:
        now = time.time()
        for pg in _DEMO_PAGES:
            conn.execute(
                "INSERT INTO pages (title, slug, page_type, content, is_active, sort_order, created_at) "
                "VALUES (?, ?, ?, ?, 1, ?, ?)",
                (
                    pg["title"],
                    pg["slug"],
                    pg["page_type"],
                    pg["content"],
                    pg["sort_order"],
                    now,
                ),
            )

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
