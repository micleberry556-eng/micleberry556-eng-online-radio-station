"""Authentication blueprint — login/logout for admin panel."""

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required

from app import login_manager
from app.models import User

auth_bp = Blueprint("auth", __name__)


@login_manager.user_loader  # type: ignore[misc]
def load_user(user_id: str) -> User | None:
    return User.get_by_id(int(user_id))


@auth_bp.route("/login", methods=["GET", "POST"])
def login() -> str:
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        user = User.get_by_username(username)
        if user and user.check_password(password):
            login_user(user)
            next_page = request.args.get("next", url_for("admin.dashboard"))
            return redirect(next_page)  # type: ignore[return-value]
        flash("Неверное имя пользователя или пароль", "error")
    return render_template("admin/login.html")


@auth_bp.route("/logout")
@login_required
def logout() -> str:
    logout_user()
    return redirect(url_for("auth.login"))  # type: ignore[return-value]
