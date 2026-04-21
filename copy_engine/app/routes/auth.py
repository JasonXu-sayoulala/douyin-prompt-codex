from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user

from ..extensions import db
from ..models import OperationLog, User

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user, remember=True)
            db.session.add(
                OperationLog(
                    user_id=user.id,
                    action="login",
                    target_type="users",
                    target_id=user.id,
                    detail="登录成功",
                )
            )
            db.session.commit()
            next_url = request.args.get("next") or url_for("dashboard.index")
            return redirect(next_url)
        flash("用户名或密码错误", "danger")

    return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    if current_user.is_authenticated:
        db.session.add(
            OperationLog(
                user_id=current_user.id,
                action="logout",
                target_type="users",
                target_id=current_user.id,
                detail="退出",
            )
        )
        db.session.commit()
    logout_user()
    flash("已退出登录", "info")
    return redirect(url_for("auth.login"))
