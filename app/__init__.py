"""Flask application factory for the online radio station."""

import os

from flask import Flask
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect

from config import Config

login_manager = LoginManager()
csrf = CSRFProtect()


def create_app(config_class: type = Config) -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Ensure required directories exist
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(os.path.dirname(app.config["DATABASE_PATH"]), exist_ok=True)

    # Initialize extensions
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"  # type: ignore[assignment]
    csrf.init_app(app)

    # Initialize database
    from app.models import init_db

    init_db(app)

    # Register blueprints
    from app.routes import public_bp
    from app.admin import admin_bp
    from app.auth import auth_bp
    from app.stream import stream_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(stream_bp, url_prefix="/stream")

    # Inject site settings, active theme, and nav pages into every template.
    @app.context_processor
    def inject_site_settings() -> dict[str, object]:
        from app.models import get_db, get_site_settings
        from app.admin import THEMES

        try:
            db = get_db()
            settings = get_site_settings(db)
            nav_pages = db.execute(
                "SELECT title, slug FROM pages WHERE is_active = 1 ORDER BY sort_order"
            ).fetchall()
        except Exception:
            settings = {
                "theme": "default",
                "background_image": "",
                "site_title": "Онлайн Радио",
            }
            nav_pages = []
        theme_key = settings.get("theme", "default")
        theme_vars = THEMES.get(theme_key, THEMES["default"])
        return {
            "site_settings": settings,
            "active_theme": theme_vars,
            "nav_pages": nav_pages,
        }

    return app
