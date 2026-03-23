"""Public-facing routes — radio player pages."""

from flask import Blueprint, render_template

from app.models import get_db

public_bp = Blueprint("public", __name__)


@public_bp.route("/")
def index() -> str:
    """Main radio player page with station list."""
    db = get_db()
    stations = db.execute(
        "SELECT * FROM stations WHERE is_active = 1 ORDER BY sort_order"
    ).fetchall()
    return render_template("public/index.html", stations=stations)


@public_bp.route("/station/<slug>")
def station(slug: str) -> str:
    """Station detail page."""
    db = get_db()
    st = db.execute(
        "SELECT * FROM stations WHERE slug = ? AND is_active = 1", (slug,)
    ).fetchone()
    if st is None:
        return render_template("public/404.html"), 404  # type: ignore[return-value]
    tracks = db.execute(
        "SELECT * FROM tracks WHERE station_id = ? ORDER BY sort_order", (st["id"],)
    ).fetchall()
    return render_template("public/station.html", station=st, tracks=tracks)
