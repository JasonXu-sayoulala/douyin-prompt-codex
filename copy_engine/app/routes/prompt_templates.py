from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..models import CopyTemplate, OperationLog
from ..utils import wants_json

templates_bp = Blueprint("prompt_templates", __name__)


def _log(action: str, target_id: int, detail: str):
    db.session.add(
        OperationLog(
            user_id=current_user.id,
            action=action,
            target_type="templates",
            target_id=target_id,
            detail=detail,
        )
    )


@templates_bp.route("")
@login_required
def list_templates():
    items = CopyTemplate.query.order_by(CopyTemplate.created_at.desc()).all()
    return render_template("templates/list.html", items=items)


@templates_bp.route("/create", methods=["GET", "POST"])
@login_required
def create():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        template_type = (request.form.get("template_type") or "").strip()
        prompt = (request.form.get("prompt") or "").strip()
        description = (request.form.get("description") or "").strip()
        is_active = request.form.get("is_active") == "on"
        if not name or not prompt:
            flash("模板名称与提示词正文必填", "danger")
            return render_template("templates/edit.html", tpl=None)
        tpl = CopyTemplate(
            name=name,
            template_type=template_type or None,
            prompt=prompt,
            description=description or None,
            is_active=is_active,
        )
        db.session.add(tpl)
        db.session.flush()
        _log("template_create", tpl.id, name)
        db.session.commit()
        if wants_json():
            return {"ok": True, "id": tpl.id}
        flash("模板已创建", "success")
        return redirect(url_for("prompt_templates.list_templates"))
    return render_template("templates/edit.html", tpl=None)


@templates_bp.route("/<int:id>/edit", methods=["GET", "POST"])
@login_required
def edit(id):
    tpl = CopyTemplate.query.get_or_404(id)
    if request.method == "POST":
        tpl.name = (request.form.get("name") or tpl.name).strip()
        tpl.template_type = (request.form.get("template_type") or "").strip() or None
        tpl.prompt = (request.form.get("prompt") or "").strip()
        tpl.description = (request.form.get("description") or "").strip() or None
        tpl.is_active = request.form.get("is_active") == "on"
        if not tpl.name or not tpl.prompt:
            flash("模板名称与提示词正文必填", "danger")
            return render_template("templates/edit.html", tpl=tpl)
        _log("template_update", id, tpl.name)
        db.session.commit()
        if wants_json():
            return {"ok": True}
        flash("已保存", "success")
        return redirect(url_for("prompt_templates.list_templates"))
    return render_template("templates/edit.html", tpl=tpl)


@templates_bp.route("/<int:id>/apply")
@login_required
def apply_redirect(id):
    """套用：跳转选题列表（用户选题后进入生成页）。"""
    flash("请选择一个选题后点击「生成文案」", "info")
    return redirect(url_for("topics.list_topics"))
