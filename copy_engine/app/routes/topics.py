from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..models import OperationLog, Topic
from ..utils import wants_json

topics_bp = Blueprint("topics", __name__)

CATEGORIES = [
    "情侣冲突",
    "婚姻现实",
    "职场情绪",
    "站队争议",
    "口播观点",
    "聊天记录剧情",
]


def _log(action: str, target_id: int, detail: str):
    db.session.add(
        OperationLog(
            user_id=current_user.id,
            action=action,
            target_type="topics",
            target_id=target_id,
            detail=detail,
        )
    )


@topics_bp.route("")
@login_required
def list_topics():
    q = (request.args.get("q") or "").strip()
    category = (request.args.get("category") or "").strip()
    status = (request.args.get("status") or "").strip()

    query = Topic.query
    if q:
        query = query.filter(Topic.title.contains(q))
    if category:
        query = query.filter_by(category=category)
    if status:
        query = query.filter_by(status=status)
    topics = query.order_by(Topic.created_at.desc()).all()
    return render_template(
        "topics/list.html",
        topics=topics,
        categories=CATEGORIES,
        filters={"q": q, "category": category, "status": status},
    )


@topics_bp.route("/create", methods=["GET", "POST"])
@login_required
def create():
    if request.method == "POST":
        data = request.get_json(silent=True) if wants_json() else None
        if data:
            title = (data.get("title") or "").strip()
            category = (data.get("category") or "").strip()
            tags = (data.get("tags") or "").strip()
            emotion_level = int(data.get("emotion_level") or 3)
            source = (data.get("source") or "").strip()
        else:
            title = (request.form.get("title") or "").strip()
            category = (request.form.get("category") or "").strip()
            tags = (request.form.get("tags") or "").strip()
            emotion_level = int(request.form.get("emotion_level") or 3)
            source = (request.form.get("source") or "").strip()

        if not title:
            if wants_json():
                return {"ok": False, "error": "标题必填"}, 400
            flash("标题必填", "danger")
            return render_template("topics/create.html", categories=CATEGORIES)

        topic = Topic(
            title=title,
            category=category or None,
            tags=tags or None,
            emotion_level=emotion_level,
            source=source or None,
            status="draft",
        )
        db.session.add(topic)
        db.session.commit()
        _log("topic_create", topic.id, title[:200])

        if wants_json():
            return {"ok": True, "id": topic.id}

        flash("选题已创建", "success")
        return redirect(url_for("topics.detail", topic_id=topic.id))

    return render_template("topics/create.html", categories=CATEGORIES)


@topics_bp.route("/<int:topic_id>")
@login_required
def detail(topic_id):
    topic = Topic.query.get_or_404(topic_id)
    return render_template("topics/detail.html", topic=topic, categories=CATEGORIES)


@topics_bp.route("/<int:topic_id>/archive", methods=["POST"])
@login_required
def archive(topic_id):
    topic = Topic.query.get_or_404(topic_id)
    topic.status = "archived"
    db.session.commit()
    _log("topic_archive", topic_id, topic.title[:200])
    flash("已归档", "info")
    return redirect(url_for("topics.list_topics"))
