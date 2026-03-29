"""Admin panel blueprint — full CRUD for stations, tracks, and settings."""

import os
import time
import uuid

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import login_required
from mutagen.mp3 import MP3  # type: ignore[import-untyped]
from werkzeug.utils import secure_filename

from app.models import PAGE_TYPES, get_db, get_site_settings, set_site_setting

admin_bp = Blueprint("admin", __name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _allowed_file(filename: str) -> bool:
    """Return True if *filename* has an allowed extension."""
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in current_app.config["ALLOWED_EXTENSIONS"]
    )


def _allowed_image(filename: str) -> bool:
    """Return True if *filename* has an allowed image extension."""
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in current_app.config["ALLOWED_IMAGE_EXTENSIONS"]
    )


def _save_image(file) -> str:  # type: ignore[no-untyped-def]
    """Save an uploaded image and return the stored filename."""
    original = secure_filename(file.filename or "image.png")
    unique_name = f"{uuid.uuid4().hex}_{original}"
    dest = os.path.join(current_app.config["UPLOAD_FOLDER"], unique_name)
    file.save(dest)
    return unique_name


def _save_mp3(file) -> tuple[str, float, int]:  # type: ignore[no-untyped-def]
    """Save an uploaded MP3 and return (filename, duration_sec, file_size)."""
    original = secure_filename(file.filename or "track.mp3")
    unique_name = f"{uuid.uuid4().hex}_{original}"
    dest = os.path.join(current_app.config["UPLOAD_FOLDER"], unique_name)
    file.save(dest)
    audio = MP3(dest)
    duration: float = audio.info.length  # type: ignore[union-attr]
    file_size = os.path.getsize(dest)
    return unique_name, duration, file_size


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


@admin_bp.route("/")
@login_required
def dashboard() -> str:
    """Admin dashboard with overview stats."""
    db = get_db()
    station_count = db.execute("SELECT COUNT(*) FROM stations").fetchone()[0]
    track_count = db.execute("SELECT COUNT(*) FROM tracks").fetchone()[0]
    user_count = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    domain_count = db.execute("SELECT COUNT(*) FROM domains").fetchone()[0]
    page_count = db.execute("SELECT COUNT(*) FROM pages").fetchone()[0]
    return render_template(
        "admin/dashboard.html",
        station_count=station_count,
        track_count=track_count,
        user_count=user_count,
        domain_count=domain_count,
        page_count=page_count,
    )


# ---------------------------------------------------------------------------
# Stations CRUD
# ---------------------------------------------------------------------------


@admin_bp.route("/stations")
@login_required
def stations_list() -> str:
    db = get_db()
    stations = db.execute("SELECT * FROM stations ORDER BY sort_order").fetchall()
    return render_template("admin/stations.html", stations=stations)


@admin_bp.route("/stations/add", methods=["GET", "POST"])
@login_required
def station_add() -> str:
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        slug = request.form.get("slug", "").strip()
        description = request.form.get("description", "").strip()
        genre = request.form.get("genre", "").strip()
        sort_order = int(request.form.get("sort_order", "0"))
        is_active = 1 if request.form.get("is_active") else 0

        # Handle image file upload.
        image_file = ""
        img = request.files.get("image_file")
        if img and img.filename and _allowed_image(img.filename):
            image_file = _save_image(img)

        if not name or not slug:
            flash("Название и slug обязательны", "error")
            return render_template("admin/station_form.html", station=None)

        db = get_db()
        existing = db.execute(
            "SELECT id FROM stations WHERE slug = ?", (slug,)
        ).fetchone()
        if existing:
            flash("Станция с таким slug уже существует", "error")
            return render_template("admin/station_form.html", station=None)

        db.execute(
            "INSERT INTO stations (name, slug, description, genre, image_url, image_file, is_active, sort_order, created_at) "
            "VALUES (?, ?, ?, ?, '', ?, ?, ?, ?)",
            (
                name,
                slug,
                description,
                genre,
                image_file,
                is_active,
                sort_order,
                time.time(),
            ),
        )
        db.commit()
        flash("Станция добавлена", "success")
        return redirect(url_for("admin.stations_list"))  # type: ignore[return-value]

    return render_template("admin/station_form.html", station=None)


@admin_bp.route("/stations/<int:station_id>/edit", methods=["GET", "POST"])
@login_required
def station_edit(station_id: int) -> str:
    db = get_db()
    station = db.execute(
        "SELECT * FROM stations WHERE id = ?", (station_id,)
    ).fetchone()
    if station is None:
        flash("Станция не найдена", "error")
        return redirect(url_for("admin.stations_list"))  # type: ignore[return-value]

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        slug = request.form.get("slug", "").strip()
        description = request.form.get("description", "").strip()
        genre = request.form.get("genre", "").strip()
        sort_order = int(request.form.get("sort_order", "0"))
        is_active = 1 if request.form.get("is_active") else 0

        # Handle optional image file upload; keep existing if none provided.
        image_file = station["image_file"]
        img = request.files.get("image_file")
        if img and img.filename and _allowed_image(img.filename):
            image_file = _save_image(img)

        if not name or not slug:
            flash("Название и slug обязательны", "error")
            return render_template("admin/station_form.html", station=station)

        # Check slug uniqueness (excluding current station)
        dup = db.execute(
            "SELECT id FROM stations WHERE slug = ? AND id != ?", (slug, station_id)
        ).fetchone()
        if dup:
            flash("Станция с таким slug уже существует", "error")
            return render_template("admin/station_form.html", station=station)

        db.execute(
            "UPDATE stations SET name=?, slug=?, description=?, genre=?, image_file=?, "
            "is_active=?, sort_order=? WHERE id=?",
            (
                name,
                slug,
                description,
                genre,
                image_file,
                is_active,
                sort_order,
                station_id,
            ),
        )
        db.commit()
        flash("Станция обновлена", "success")
        return redirect(url_for("admin.stations_list"))  # type: ignore[return-value]

    return render_template("admin/station_form.html", station=station)


@admin_bp.route("/stations/<int:station_id>/delete", methods=["POST"])
@login_required
def station_delete(station_id: int) -> str:
    db = get_db()
    # Delete associated track files from disk
    tracks = db.execute(
        "SELECT filename FROM tracks WHERE station_id = ?", (station_id,)
    ).fetchall()
    for track in tracks:
        filepath = os.path.join(current_app.config["UPLOAD_FOLDER"], track["filename"])
        if os.path.exists(filepath):
            os.remove(filepath)
    db.execute("DELETE FROM tracks WHERE station_id = ?", (station_id,))
    db.execute("DELETE FROM stations WHERE id = ?", (station_id,))
    db.commit()
    flash("Станция удалена", "success")
    return redirect(url_for("admin.stations_list"))  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Tracks CRUD
# ---------------------------------------------------------------------------


@admin_bp.route("/stations/<int:station_id>/tracks")
@login_required
def tracks_list(station_id: int) -> str:
    db = get_db()
    station = db.execute(
        "SELECT * FROM stations WHERE id = ?", (station_id,)
    ).fetchone()
    if station is None:
        flash("Станция не найдена", "error")
        return redirect(url_for("admin.stations_list"))  # type: ignore[return-value]
    tracks = db.execute(
        "SELECT * FROM tracks WHERE station_id = ? ORDER BY sort_order", (station_id,)
    ).fetchall()
    return render_template("admin/tracks.html", station=station, tracks=tracks)


@admin_bp.route("/stations/<int:station_id>/tracks/upload", methods=["GET", "POST"])
@login_required
def track_upload(station_id: int) -> str:
    db = get_db()
    station = db.execute(
        "SELECT * FROM stations WHERE id = ?", (station_id,)
    ).fetchone()
    if station is None:
        flash("Станция не найдена", "error")
        return redirect(url_for("admin.stations_list"))  # type: ignore[return-value]

    if request.method == "POST":
        files = request.files.getlist("files")
        if not files or all(f.filename == "" for f in files):
            flash("Выберите хотя бы один MP3 файл", "error")
            return render_template("admin/track_upload.html", station=station)

        uploaded = 0
        max_order_row = db.execute(
            "SELECT MAX(sort_order) FROM tracks WHERE station_id = ?", (station_id,)
        ).fetchone()
        next_order: int = (max_order_row[0] or 0) + 1

        for f in files:
            if f.filename and _allowed_file(f.filename):
                filename, duration, file_size = _save_mp3(f)
                title = (
                    os.path.splitext(secure_filename(f.filename))[0]
                    .replace("_", " ")
                    .replace("-", " ")
                )
                db.execute(
                    "INSERT INTO tracks (station_id, title, artist, filename, duration, file_size, sort_order, created_at) "
                    "VALUES (?, ?, '', ?, ?, ?, ?, ?)",
                    (
                        station_id,
                        title,
                        filename,
                        duration,
                        file_size,
                        next_order,
                        time.time(),
                    ),
                )
                next_order += 1
                uploaded += 1

        db.commit()
        flash(f"Загружено треков: {uploaded}", "success")
        return redirect(url_for("admin.tracks_list", station_id=station_id))  # type: ignore[return-value]

    return render_template("admin/track_upload.html", station=station)


@admin_bp.route("/tracks/<int:track_id>/edit", methods=["GET", "POST"])
@login_required
def track_edit(track_id: int) -> str:
    db = get_db()
    track = db.execute("SELECT * FROM tracks WHERE id = ?", (track_id,)).fetchone()
    if track is None:
        flash("Трек не найден", "error")
        return redirect(url_for("admin.stations_list"))  # type: ignore[return-value]

    station = db.execute(
        "SELECT * FROM stations WHERE id = ?", (track["station_id"],)
    ).fetchone()

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        artist = request.form.get("artist", "").strip()
        sort_order = int(request.form.get("sort_order", "0"))

        if not title:
            flash("Название трека обязательно", "error")
            return render_template(
                "admin/track_form.html", track=track, station=station
            )

        db.execute(
            "UPDATE tracks SET title=?, artist=?, sort_order=? WHERE id=?",
            (title, artist, sort_order, track_id),
        )
        db.commit()
        flash("Трек обновлён", "success")
        return redirect(url_for("admin.tracks_list", station_id=track["station_id"]))  # type: ignore[return-value]

    return render_template("admin/track_form.html", track=track, station=station)


@admin_bp.route("/tracks/<int:track_id>/delete", methods=["POST"])
@login_required
def track_delete(track_id: int) -> str:
    db = get_db()
    track = db.execute("SELECT * FROM tracks WHERE id = ?", (track_id,)).fetchone()
    if track is None:
        flash("Трек не найден", "error")
        return redirect(url_for("admin.stations_list"))  # type: ignore[return-value]

    # Remove file from disk
    filepath = os.path.join(current_app.config["UPLOAD_FOLDER"], track["filename"])
    if os.path.exists(filepath):
        os.remove(filepath)

    station_id = track["station_id"]
    db.execute("DELETE FROM tracks WHERE id = ?", (track_id,))
    db.commit()
    flash("Трек удалён", "success")
    return redirect(url_for("admin.tracks_list", station_id=station_id))  # type: ignore[return-value]


@admin_bp.route("/tracks/<int:track_id>/move/<direction>", methods=["POST"])
@login_required
def track_move(track_id: int, direction: str) -> str:
    """Move a track up or down in the playlist order."""
    db = get_db()
    track = db.execute("SELECT * FROM tracks WHERE id = ?", (track_id,)).fetchone()
    if track is None:
        flash("Трек не найден", "error")
        return redirect(url_for("admin.stations_list"))  # type: ignore[return-value]

    station_id = track["station_id"]
    current_order = track["sort_order"]

    if direction == "up":
        neighbor = db.execute(
            "SELECT * FROM tracks WHERE station_id = ? AND sort_order < ? ORDER BY sort_order DESC LIMIT 1",
            (station_id, current_order),
        ).fetchone()
    else:
        neighbor = db.execute(
            "SELECT * FROM tracks WHERE station_id = ? AND sort_order > ? ORDER BY sort_order ASC LIMIT 1",
            (station_id, current_order),
        ).fetchone()

    if neighbor:
        db.execute(
            "UPDATE tracks SET sort_order = ? WHERE id = ?",
            (neighbor["sort_order"], track_id),
        )
        db.execute(
            "UPDATE tracks SET sort_order = ? WHERE id = ?",
            (current_order, neighbor["id"]),
        )
        db.commit()

    return redirect(url_for("admin.tracks_list", station_id=station_id))  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------


@admin_bp.route("/users")
@login_required
def users_list() -> str:
    db = get_db()
    users = db.execute(
        "SELECT id, username, is_admin, created_at FROM users ORDER BY id"
    ).fetchall()
    return render_template("admin/users.html", users=users)


@admin_bp.route("/users/add", methods=["GET", "POST"])
@login_required
def user_add() -> str:
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not username or not password:
            flash("Имя пользователя и пароль обязательны", "error")
            return render_template("admin/user_form.html", user=None)

        db = get_db()
        existing = db.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()
        if existing:
            flash("Пользователь с таким именем уже существует", "error")
            return render_template("admin/user_form.html", user=None)

        from werkzeug.security import generate_password_hash

        db.execute(
            "INSERT INTO users (username, password, is_admin, created_at) VALUES (?, ?, 1, ?)",
            (username, generate_password_hash(password), time.time()),
        )
        db.commit()
        flash("Пользователь добавлен", "success")
        return redirect(url_for("admin.users_list"))  # type: ignore[return-value]

    return render_template("admin/user_form.html", user=None)


@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@login_required
def user_delete(user_id: int) -> str:
    db = get_db()
    # Prevent deleting the last admin
    count = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if count <= 1:
        flash("Нельзя удалить последнего администратора", "error")
        return redirect(url_for("admin.users_list"))  # type: ignore[return-value]

    db.execute("DELETE FROM users WHERE id = ?", (user_id,))
    db.commit()
    flash("Пользователь удалён", "success")
    return redirect(url_for("admin.users_list"))  # type: ignore[return-value]


@admin_bp.route("/users/<int:user_id>/password", methods=["GET", "POST"])
@login_required
def user_change_password(user_id: int) -> str:
    db = get_db()
    user = db.execute(
        "SELECT id, username FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    if user is None:
        flash("Пользователь не найден", "error")
        return redirect(url_for("admin.users_list"))  # type: ignore[return-value]

    if request.method == "POST":
        password = request.form.get("password", "").strip()
        if not password:
            flash("Пароль не может быть пустым", "error")
            return render_template("admin/user_password.html", user=user)

        from werkzeug.security import generate_password_hash

        db.execute(
            "UPDATE users SET password = ? WHERE id = ?",
            (generate_password_hash(password), user_id),
        )
        db.commit()
        flash("Пароль изменён", "success")
        return redirect(url_for("admin.users_list"))  # type: ignore[return-value]

    return render_template("admin/user_password.html", user=user)


# ---------------------------------------------------------------------------
# Domain management
# ---------------------------------------------------------------------------


@admin_bp.route("/domains")
@login_required
def domains_list() -> str:
    """List all configured domains."""
    db = get_db()
    domains = db.execute(
        "SELECT * FROM domains ORDER BY is_primary DESC, id"
    ).fetchall()
    return render_template("admin/domains.html", domains=domains)


@admin_bp.route("/domains/add", methods=["GET", "POST"])
@login_required
def domain_add() -> str:
    """Add a new domain."""
    if request.method == "POST":
        domain = request.form.get("domain", "").strip().lower()
        is_primary = 1 if request.form.get("is_primary") else 0
        is_active = 1 if request.form.get("is_active") else 0

        if not domain:
            flash("Доменное имя обязательно", "error")
            return render_template("admin/domain_form.html", domain=None)

        db = get_db()
        existing = db.execute(
            "SELECT id FROM domains WHERE domain = ?", (domain,)
        ).fetchone()
        if existing:
            flash("Такой домен уже добавлен", "error")
            return render_template("admin/domain_form.html", domain=None)

        # If marking as primary, unset other primaries.
        if is_primary:
            db.execute("UPDATE domains SET is_primary = 0")

        db.execute(
            "INSERT INTO domains (domain, is_primary, is_active, created_at) "
            "VALUES (?, ?, ?, ?)",
            (domain, is_primary, is_active, time.time()),
        )
        db.commit()
        flash("Домен добавлен", "success")
        return redirect(url_for("admin.domains_list"))  # type: ignore[return-value]

    return render_template("admin/domain_form.html", domain=None)


@admin_bp.route("/domains/<int:domain_id>/edit", methods=["GET", "POST"])
@login_required
def domain_edit(domain_id: int) -> str:
    """Edit an existing domain."""
    db = get_db()
    domain = db.execute("SELECT * FROM domains WHERE id = ?", (domain_id,)).fetchone()
    if domain is None:
        flash("Домен не найден", "error")
        return redirect(url_for("admin.domains_list"))  # type: ignore[return-value]

    if request.method == "POST":
        domain_name = request.form.get("domain", "").strip().lower()
        is_primary = 1 if request.form.get("is_primary") else 0
        is_active = 1 if request.form.get("is_active") else 0

        if not domain_name:
            flash("Доменное имя обязательно", "error")
            return render_template("admin/domain_form.html", domain=domain)

        dup = db.execute(
            "SELECT id FROM domains WHERE domain = ? AND id != ?",
            (domain_name, domain_id),
        ).fetchone()
        if dup:
            flash("Такой домен уже добавлен", "error")
            return render_template("admin/domain_form.html", domain=domain)

        if is_primary:
            db.execute("UPDATE domains SET is_primary = 0")

        db.execute(
            "UPDATE domains SET domain=?, is_primary=?, is_active=? WHERE id=?",
            (domain_name, is_primary, is_active, domain_id),
        )
        db.commit()
        flash("Домен обновлён", "success")
        return redirect(url_for("admin.domains_list"))  # type: ignore[return-value]

    return render_template("admin/domain_form.html", domain=domain)


@admin_bp.route("/domains/<int:domain_id>/delete", methods=["POST"])
@login_required
def domain_delete(domain_id: int) -> str:
    """Delete a domain."""
    db = get_db()
    db.execute("DELETE FROM domains WHERE id = ?", (domain_id,))
    db.commit()
    flash("Домен удалён", "success")
    return redirect(url_for("admin.domains_list"))  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Pages management (charts, ads, subscriptions, custom)
# ---------------------------------------------------------------------------


@admin_bp.route("/pages")
@login_required
def pages_list() -> str:
    """List all content pages."""
    db = get_db()
    pages = db.execute("SELECT * FROM pages ORDER BY sort_order, id").fetchall()
    type_map = dict(PAGE_TYPES)
    return render_template("admin/pages.html", pages=pages, type_map=type_map)


@admin_bp.route("/pages/add", methods=["GET", "POST"])
@login_required
def page_add() -> str:
    """Create a new content page."""
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        slug = request.form.get("slug", "").strip()
        page_type = request.form.get("page_type", "custom").strip()
        content = request.form.get("content", "").strip()
        sort_order = int(request.form.get("sort_order", "0"))
        is_active = 1 if request.form.get("is_active") else 0

        if not title or not slug:
            flash("Название и slug обязательны", "error")
            return render_template(
                "admin/page_form.html", page=None, page_types=PAGE_TYPES
            )

        db = get_db()
        existing = db.execute("SELECT id FROM pages WHERE slug = ?", (slug,)).fetchone()
        if existing:
            flash("Страница с таким slug уже существует", "error")
            return render_template(
                "admin/page_form.html", page=None, page_types=PAGE_TYPES
            )

        db.execute(
            "INSERT INTO pages (title, slug, page_type, content, is_active, sort_order, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (title, slug, page_type, content, is_active, sort_order, time.time()),
        )
        db.commit()
        flash("Страница создана", "success")
        return redirect(url_for("admin.pages_list"))  # type: ignore[return-value]

    return render_template("admin/page_form.html", page=None, page_types=PAGE_TYPES)


@admin_bp.route("/pages/<int:page_id>/edit", methods=["GET", "POST"])
@login_required
def page_edit(page_id: int) -> str:
    """Edit an existing content page."""
    db = get_db()
    page = db.execute("SELECT * FROM pages WHERE id = ?", (page_id,)).fetchone()
    if page is None:
        flash("Страница не найдена", "error")
        return redirect(url_for("admin.pages_list"))  # type: ignore[return-value]

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        slug = request.form.get("slug", "").strip()
        page_type = request.form.get("page_type", "custom").strip()
        content = request.form.get("content", "").strip()
        sort_order = int(request.form.get("sort_order", "0"))
        is_active = 1 if request.form.get("is_active") else 0

        if not title or not slug:
            flash("Название и slug обязательны", "error")
            return render_template(
                "admin/page_form.html", page=page, page_types=PAGE_TYPES
            )

        dup = db.execute(
            "SELECT id FROM pages WHERE slug = ? AND id != ?", (slug, page_id)
        ).fetchone()
        if dup:
            flash("Страница с таким slug уже существует", "error")
            return render_template(
                "admin/page_form.html", page=page, page_types=PAGE_TYPES
            )

        db.execute(
            "UPDATE pages SET title=?, slug=?, page_type=?, content=?, "
            "is_active=?, sort_order=? WHERE id=?",
            (title, slug, page_type, content, is_active, sort_order, page_id),
        )
        db.commit()
        flash("Страница обновлена", "success")
        return redirect(url_for("admin.pages_list"))  # type: ignore[return-value]

    return render_template("admin/page_form.html", page=page, page_types=PAGE_TYPES)


@admin_bp.route("/pages/<int:page_id>/delete", methods=["POST"])
@login_required
def page_delete(page_id: int) -> str:
    """Delete a content page."""
    db = get_db()
    db.execute("DELETE FROM pages WHERE id = ?", (page_id,))
    db.commit()
    flash("Страница удалена", "success")
    return redirect(url_for("admin.pages_list"))  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Design / Appearance settings
# ---------------------------------------------------------------------------

# 10 built-in modern themes.  Each theme is a dict of CSS custom-property
# overrides that the public layout will inject into :root.
THEMES: dict[str, dict[str, str]] = {
    "default": {
        "label": "По умолчанию",
        "bg": "#0a0b10",
        "bg-card": "#13151e",
        "primary": "#6c5ce7",
        "accent": "#00cec9",
        "text": "#e8eaf0",
    },
    "midnight-blue": {
        "label": "Полночный синий",
        "bg": "#0b0e1a",
        "bg-card": "#111633",
        "primary": "#3b82f6",
        "accent": "#38bdf8",
        "text": "#e2e8f0",
    },
    "sunset-orange": {
        "label": "Закат",
        "bg": "#1a0e0a",
        "bg-card": "#261510",
        "primary": "#f97316",
        "accent": "#fbbf24",
        "text": "#fef3c7",
    },
    "forest-green": {
        "label": "Лесной",
        "bg": "#0a1210",
        "bg-card": "#0f1f1a",
        "primary": "#22c55e",
        "accent": "#4ade80",
        "text": "#dcfce7",
    },
    "rose-pink": {
        "label": "Розовый",
        "bg": "#1a0a14",
        "bg-card": "#26101c",
        "primary": "#ec4899",
        "accent": "#f472b6",
        "text": "#fce7f3",
    },
    "cyber-purple": {
        "label": "Кибер-фиолет",
        "bg": "#0f0a1a",
        "bg-card": "#1a1028",
        "primary": "#a855f7",
        "accent": "#c084fc",
        "text": "#f3e8ff",
    },
    "arctic-light": {
        "label": "Арктика",
        "bg": "#f0f4f8",
        "bg-card": "#ffffff",
        "primary": "#0ea5e9",
        "accent": "#06b6d4",
        "text": "#1e293b",
    },
    "warm-sand": {
        "label": "Тёплый песок",
        "bg": "#1c1710",
        "bg-card": "#2a2218",
        "primary": "#d97706",
        "accent": "#f59e0b",
        "text": "#fef9c3",
    },
    "neon-city": {
        "label": "Неон",
        "bg": "#0a0a0f",
        "bg-card": "#12121c",
        "primary": "#06ffa5",
        "accent": "#00e5ff",
        "text": "#e0ffe0",
    },
    "monochrome": {
        "label": "Монохром",
        "bg": "#111111",
        "bg-card": "#1a1a1a",
        "primary": "#ffffff",
        "accent": "#a0a0a0",
        "text": "#e0e0e0",
    },
}


@admin_bp.route("/design", methods=["GET", "POST"])
@login_required
def design_settings() -> str:
    """Manage site appearance: theme, background image, site title."""
    db = get_db()

    if request.method == "POST":
        # Theme selection.
        theme = request.form.get("theme", "default")
        if theme in THEMES:
            set_site_setting(db, "theme", theme)

        # Site title.
        site_title = request.form.get("site_title", "").strip()
        if site_title:
            set_site_setting(db, "site_title", site_title)

        # Background image upload.
        bg_img = request.files.get("background_image")
        if bg_img and bg_img.filename and _allowed_image(bg_img.filename):
            filename = _save_image(bg_img)
            set_site_setting(db, "background_image", filename)

        # Allow clearing the background.
        if request.form.get("clear_background"):
            set_site_setting(db, "background_image", "")

        db.commit()
        flash("Оформление сохранено", "success")
        return redirect(url_for("admin.design_settings"))  # type: ignore[return-value]

    settings = get_site_settings(db)
    return render_template("admin/design.html", settings=settings, themes=THEMES)
