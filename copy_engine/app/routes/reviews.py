from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..models import Content, CopyTemplate, OperationLog, ReviewRecord
from ..utils import wants_json

reviews_bp = Blueprint("reviews", __name__)


def _log(action: str, target_id: int, detail: str):
    db.session.add(
        OperationLog(
            user_id=current_user.id,
            action=action,
            target_type="reviews",
            target_id=target_id,
            detail=detail,
        )
    )


@reviews_bp.route("")
@login_required
def list_reviews():
    status = (request.args.get("status") or "").strip()
    q = Content.query.filter(Content.status.in_(["pending_review", "approved", "rejected"]))
    if status:
        q = q.filter_by(status=status)
    items = q.order_by(Content.updated_at.desc()).all()
    return render_template("reviews/list.html", items=items, filters={"status": status})


@reviews_bp.route("/<int:content_id>")
@login_required
def detail(content_id):
    content = Content.query.get_or_404(content_id)
    return render_template("reviews/detail.html", content=content)


@reviews_bp.route("/<int:content_id>/approve", methods=["POST"])
@login_required
def approve(content_id):
    content = Content.query.get_or_404(content_id)
    content.status = "approved"
    rec = (
        ReviewRecord.query.filter_by(content_id=content_id, review_status="pending")
        .order_by(ReviewRecord.created_at.desc())
        .first()
    )
    if rec:
        rec.review_status = "approved"
        rec.reviewer_id = current_user.id
    else:
        db.session.add(
            ReviewRecord(
                content_id=content_id,
                reviewer_id=current_user.id,
                review_status="approved",
            )
        )
    db.session.commit()
    _log("review_approve", content_id, "通过")
    if wants_json():
        return {"ok": True}
    flash("已通过审核", "success")
    return redirect(url_for("reviews.list_reviews"))


@reviews_bp.route("/<int:content_id>/reject", methods=["POST"])
@login_required
def reject(content_id):
    content = Content.query.get_or_404(content_id)
    data = request.get_json(silent=True) if wants_json() or request.is_json else None
    note = (data.get("review_note") if data else None) or request.form.get("review_note") or ""
    note = note.strip()
    if not note:
        if wants_json():
            return {"ok": False, "error": "请填写驳回备注"}, 400
        flash("请填写驳回备注", "danger")
        return redirect(url_for("reviews.detail", content_id=content_id))

    content.status = "rejected"
    rec = (
        ReviewRecord.query.filter_by(content_id=content_id, review_status="pending")
        .order_by(ReviewRecord.created_at.desc())
        .first()
    )
    if rec:
        rec.review_status = "rejected"
        rec.reviewer_id = current_user.id
        rec.review_note = note
    else:
        db.session.add(
            ReviewRecord(
                content_id=content_id,
                reviewer_id=current_user.id,
                review_status="rejected",
                review_note=note,
            )
        )
    db.session.commit()
    _log("review_reject", content_id, note[:200])
    if wants_json():
        return {"ok": True}
    flash("已驳回", "warning")
    return redirect(url_for("reviews.list_reviews"))


@reviews_bp.route("/<int:content_id>/void", methods=["POST"])
@login_required
def void_content(content_id):
    """作废：标记为 rejected 并备注。"""
    content = Content.query.get_or_404(content_id)
    content.status = "rejected"
    db.session.add(
        ReviewRecord(
            content_id=content_id,
            reviewer_id=current_user.id,
            review_status="rejected",
            review_note="作废",
        )
    )
    db.session.commit()
    _log("content_void", content_id, "作废")
    flash("已作废", "info")
    return redirect(url_for("reviews.list_reviews"))


@reviews_bp.route("/<int:content_id>/favorite-template", methods=["POST"])
@login_required
def favorite_template(content_id):
    content = Content.query.get_or_404(content_id)
    name = (request.form.get("name") or f"收藏-{content.title or content_id}")[:100]
    tpl = CopyTemplate(
        name=name,
        template_type="收藏",
        prompt=(content.body or "")[:8000],
        description=f"由文案 #{content_id} 收藏生成",
        is_active=True,
    )
    db.session.add(tpl)
    db.session.flush()
    _log("template_favorite", tpl.id, name)
    db.session.commit()
    flash("已保存为模板", "success")
    return redirect(url_for("prompt_templates.edit", id=tpl.id))
