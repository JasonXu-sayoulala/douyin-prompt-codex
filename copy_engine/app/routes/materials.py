from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..models import MaterialInsight, OperationLog, SourceMaterial
from ..services.material_insight_service import material_insight_service
from ..utils import wants_json

materials_bp = Blueprint("materials", __name__)

PLATFORMS = ["manual", "douyin", "xiaohongshu", "kuaishou", "bilibili", "wechat"]
STATUSES = ["raw", "analyzed", "selected", "archived"]
CATEGORIES = [
    "情侣冲突",
    "婚姻现实",
    "职场情绪",
    "站队争议",
    "口播观点",
    "聊天记录剧情",
]


def _to_int(value, default: int = 0) -> int:
    try:
        return max(0, int(value or default))
    except (TypeError, ValueError):
        return default


def _log(action: str, target_id: int, detail: str):
    db.session.add(
        OperationLog(
            user_id=current_user.id,
            action=action,
            target_type="materials",
            target_id=target_id,
            detail=detail,
        )
    )


@materials_bp.route("")
@login_required
def list_materials():
    q = (request.args.get("q") or "").strip()
    platform = (request.args.get("platform") or "").strip()
    status = (request.args.get("status") or "").strip()
    category = (request.args.get("category") or "").strip()

    query = SourceMaterial.query
    if q:
        like = f"%{q}%"
        query = query.filter(
            SourceMaterial.title.like(like)
            | SourceMaterial.raw_text.like(like)
            | SourceMaterial.hot_comments.like(like)
        )
    if platform:
        query = query.filter_by(platform=platform)
    if status:
        query = query.filter_by(status=status)
    if category:
        query = query.filter_by(category=category)

    items = query.order_by(SourceMaterial.viral_score.desc(), SourceMaterial.created_at.desc()).all()
    return render_template(
        "materials/list.html",
        items=items,
        platforms=PLATFORMS,
        statuses=STATUSES,
        categories=CATEGORIES,
        filters={"q": q, "platform": platform, "status": status, "category": category},
    )


@materials_bp.route("/create", methods=["GET", "POST"])
@login_required
def create():
    if request.method == "POST":
        data = request.get_json(silent=True) if wants_json() or request.is_json else None
        src = data or request.form
        title = (src.get("title") or "").strip()
        raw_text = (src.get("raw_text") or "").strip()
        if not title and raw_text:
            title = raw_text[:80]
        if not title:
            if wants_json():
                return {"ok": False, "error": "标题或正文至少填写一项"}, 400
            flash("标题或正文至少填写一项", "danger")
            return render_template("materials/create.html", platforms=PLATFORMS, categories=CATEGORIES)

        material = SourceMaterial(
            platform=(src.get("platform") or "manual").strip() or "manual",
            source_url=(src.get("source_url") or "").strip() or None,
            source_account=(src.get("source_account") or "").strip() or None,
            title=title[:255],
            raw_text=raw_text or None,
            hot_comments=(src.get("hot_comments") or "").strip() or None,
            category=(src.get("category") or "").strip() or None,
            tags=(src.get("tags") or "").strip() or None,
            like_count=_to_int(src.get("like_count")),
            comment_count=_to_int(src.get("comment_count")),
            share_count=_to_int(src.get("share_count")),
            collect_count=_to_int(src.get("collect_count")),
            status="raw",
            created_by=current_user.id,
        )
        db.session.add(material)
        db.session.flush()
        _log("material_create", material.id, title[:200])
        db.session.commit()

        if wants_json():
            return {"ok": True, "id": material.id}
        flash("素材已录入，可继续拆解爆点", "success")
        return redirect(url_for("materials.detail", material_id=material.id))

    return render_template("materials/create.html", platforms=PLATFORMS, categories=CATEGORIES)


@materials_bp.route("/<int:material_id>")
@login_required
def detail(material_id):
    material = SourceMaterial.query.get_or_404(material_id)
    insights = (
        MaterialInsight.query.filter_by(material_id=material_id)
        .order_by(MaterialInsight.created_at.desc())
        .all()
    )
    latest_insight = insights[0] if insights else None
    return render_template(
        "materials/detail.html",
        material=material,
        insights=insights,
        latest_insight=latest_insight,
    )


@materials_bp.route("/<int:material_id>/analyze", methods=["POST"])
@login_required
def analyze(material_id):
    material = SourceMaterial.query.get_or_404(material_id)
    insight = material_insight_service.analyze(material)
    _log("material_analyze", material_id, f"viral={insight.viral_score},discussion={insight.discussion_score}")
    db.session.commit()

    if wants_json():
        return {
            "ok": True,
            "insight_id": insight.id,
            "viral_score": insight.viral_score,
            "discussion_score": insight.discussion_score,
        }
    flash("爆点拆解完成", "success")
    return redirect(url_for("materials.detail", material_id=material_id))


@materials_bp.route("/<int:material_id>/to-topic", methods=["POST"])
@login_required
def to_topic(material_id):
    material = SourceMaterial.query.get_or_404(material_id)
    topic = material_insight_service.create_topic_from_material(material, user_id=current_user.id)
    _log("material_to_topic", material_id, f"topic={topic.id}")
    db.session.commit()

    if wants_json():
        return {"ok": True, "topic_id": topic.id}
    flash("已转为选题，可进入文案生成", "success")
    return redirect(url_for("contents.generate", topic_id=topic.id))


@materials_bp.route("/<int:material_id>/archive", methods=["POST"])
@login_required
def archive(material_id):
    material = SourceMaterial.query.get_or_404(material_id)
    material.status = "archived"
    db.session.add(material)
    _log("material_archive", material_id, material.title[:200] if material.title else "")
    db.session.commit()
    flash("素材已归档", "info")
    return redirect(url_for("materials.list_materials"))
