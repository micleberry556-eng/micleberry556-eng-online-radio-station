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

from app.models import get_db

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
    return render_template(
        "admin/dashboard.html",
        station_count=station_count,
        track_count=track_count,
        user_count=user_count,
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
        image_url = request.form.get("image_url", "").strip()
        sort_order = int(request.form.get("sort_order", "0"))
        is_active = 1 if request.form.get("is_active") else 0

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
            "INSERT INTO stations (name, slug, description, genre, image_url, is_active, sort_order, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                name,
                slug,
                description,
                genre,
                image_url,
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
        image_url = request.form.get("image_url", "").strip()
        sort_order = int(request.form.get("sort_order", "0"))
        is_active = 1 if request.form.get("is_active") else 0

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
            "UPDATE stations SET name=?, slug=?, description=?, genre=?, image_url=?, "
            "is_active=?, sort_order=? WHERE id=?",
            (
                name,
                slug,
                description,
                genre,
                image_url,
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
