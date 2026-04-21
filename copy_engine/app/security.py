from __future__ import annotations

from flask import jsonify, redirect, request, url_for
from flask_login import current_user
from flask_wtf.csrf import CSRFError


def _wants_json() -> bool:
    if request.is_json:
        return True
    best = request.accept_mimetypes.best
    return best == "application/json" or request.path.startswith("/render-jobs") or request.path.startswith("/api/")


def api_error(message: str, status_code: int = 400, *, code: str = "bad_request"):
    return jsonify({"ok": False, "error": {"code": code, "message": message}}), status_code


def register_error_handlers(app) -> None:
    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        if _wants_json():
            return api_error(str(e), 400, code="csrf_failed")
        return redirect(url_for("auth.login"))

    @app.errorhandler(401)
    def handle_unauthorized(_e):
        if _wants_json():
            return api_error("请先登录", 401, code="unauthorized")
        return redirect(url_for("auth.login"))

    @app.errorhandler(403)
    def handle_forbidden(_e):
        if _wants_json():
            return api_error("无权限访问", 403, code="forbidden")
        return redirect(url_for("dashboard.index" if current_user.is_authenticated else "auth.login"))

    @app.errorhandler(404)
    def handle_not_found(_e):
        if _wants_json():
            return api_error("资源不存在", 404, code="not_found")
        return "Not Found", 404

    @app.errorhandler(500)
    def handle_server_error(_e):
        if _wants_json():
            return api_error("服务器内部错误", 500, code="server_error")
        return "Internal Server Error", 500
