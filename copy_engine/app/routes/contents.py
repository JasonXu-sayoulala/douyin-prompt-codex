import json
from io import BytesIO

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import current_user, login_required

from ..extensions import db
from ..models import Content, CopyTemplate, MaterialInsight, OperationLog, ReviewRecord, SourceMaterial, Topic
from ..services.content_service import ContentService
from ..utils import wants_json
from ..services.rewrite_service import RewriteService

contents_bp = Blueprint("contents", __name__)


def _risk():
    return current_app.extensions["risk_service"]


def _log(action: str, target_id: int, detail: str):
    db.session.add(
        OperationLog(
            user_id=current_user.id,
            action=action,
            target_type="contents",
            target_id=target_id,
            detail=detail,
        )
    )


def _apply_risk(content: Content) -> None:
    r = _risk().scan_aggregate(content.title, content.body, content.comment_hook, content.cover_text)
    content.risk_level = r["level"]


def _material_id_from_topic(topic: Topic) -> int | None:
    source = (topic.source or "").strip()
    if not source.startswith("material:"):
        return None
    try:
        return int(source.split(":", 2)[1])
    except (IndexError, TypeError, ValueError):
        return None


def _material_context_for_topic(topic: Topic):
    material_id = _material_id_from_topic(topic)
    if not material_id:
        return None, None
    material = db.session.get(SourceMaterial, material_id)
    if not material:
        return None, None
    insight = (
        MaterialInsight.query.filter_by(material_id=material.id)
        .order_by(MaterialInsight.created_at.desc())
        .first()
    )
    return material, insight


@contents_bp.route("/generate/<int:topic_id>", methods=["GET", "POST"])
@login_required
def generate(topic_id):
    topic = Topic.query.get_or_404(topic_id)
    templates = CopyTemplate.query.filter_by(is_active=True).order_by(CopyTemplate.name).all()
    source_material, material_insight = _material_context_for_topic(topic)

    if request.method == "POST":
        data = request.get_json(silent=True) if wants_json() else None
        if data:
            template_id = int(data.get("template_id") or 0)
            content_type = (data.get("content_type") or "chat").strip()
            variants = int(data.get("variants") or data.get("生成数量") or 3)
            emotion_level = int(data.get("emotion_level") or topic.emotion_level or 3)
            max_length = int(data.get("max_length") or 280)
        else:
            template_id = int(request.form.get("template_id") or 0)
            content_type = (request.form.get("content_type") or "chat").strip()
            variants = int(request.form.get("variants") or 3)
            emotion_level = int(request.form.get("emotion_level") or topic.emotion_level or 3)
            max_length = int(request.form.get("max_length") or 280)

        tpl = CopyTemplate.query.get_or_404(template_id)
        llm = current_app.extensions["llm_service"]
        service = ContentService(llm)

        try:
            created = service.generate_contents(
                topic=topic,
                template=tpl,
                content_type=content_type,
                emotion_level=emotion_level,
                max_length=max_length,
                variants=max(1, min(variants, 5)),
                user_id=current_user.id,
            )
        except Exception as e:  # noqa: BLE001
            db.session.rollback()
            if wants_json():
                return {"ok": False, "error": str(e)}, 500
            flash(f"生成失败：{e}", "danger")
            return render_template(
                "contents/generate.html",
                topic=topic,
                templates=templates,
                source_material=source_material,
                material_insight=material_insight,
            )

        for c in created:
            _apply_risk(c)
            db.session.add(c)
            _log("content_generate", c.id, f"topic={topic_id}")
        db.session.commit()

        if wants_json():
            return {
                "ok": True,
                "source_material_id": source_material.id if source_material else None,
                "items": [
                    {
                        "id": c.id,
                        "title": c.title,
                        "body": c.body,
                        "comment_hook": c.comment_hook,
                        "cover_text": c.cover_text,
                        "risk_level": c.risk_level,
                    }
                    for c in created
                ],
            }

        flash("生成完成", "success")
        return redirect(url_for("contents.generate", topic_id=topic_id))

    recent = (
        Content.query.filter_by(topic_id=topic_id)
        .order_by(Content.created_at.desc())
        .limit(20)
        .all()
    )
    return render_template(
        "contents/generate.html",
        topic=topic,
        templates=templates,
        recent=recent,
        source_material=source_material,
        material_insight=material_insight,
    )


@contents_bp.route("/<int:id>")
@login_required
def detail(id):
    content = Content.query.get_or_404(id)
    return render_template("contents/detail.html", content=content)


@contents_bp.route("/<int:id>/edit", methods=["GET", "POST"])
@login_required
def edit(id):
    content = Content.query.get_or_404(id)
    if request.method == "POST":
        content.title = request.form.get("title") or content.title
        content.body = request.form.get("body") or content.body
        content.comment_hook = request.form.get("comment_hook") or content.comment_hook
        content.cover_text = request.form.get("cover_text") or content.cover_text
        _apply_risk(content)
        db.session.commit()
        _log("content_update", id, "编辑保存")
        flash("已保存", "success")
        return redirect(url_for("contents.detail", id=id))
    return render_template("contents/edit.html", content=content)


@contents_bp.route("/<int:id>/update", methods=["POST"])
@login_required
def update(id):
    """与文档一致：POST 更新（支持 JSON）。"""
    content = Content.query.get_or_404(id)
    data = request.get_json(silent=True) if wants_json() or request.is_json else None
    if data:
        if data.get("title") is not None:
            content.title = data["title"]
        if data.get("body") is not None:
            content.body = data["body"]
        if data.get("comment_hook") is not None:
            content.comment_hook = data["comment_hook"]
        if data.get("cover_text") is not None:
            content.cover_text = data["cover_text"]
    else:
        content.title = request.form.get("title", content.title)
        content.body = request.form.get("body", content.body)
        content.comment_hook = request.form.get("comment_hook", content.comment_hook)
        content.cover_text = request.form.get("cover_text", content.cover_text)

    _apply_risk(content)
    db.session.commit()
    _log("content_update", id, "update 接口")

    if wants_json():
        return {"ok": True, "risk_level": content.risk_level}
    flash("已更新", "success")
    return redirect(url_for("contents.detail", id=id))


@contents_bp.route("/<int:id>/rewrite", methods=["POST"])
@login_required
def rewrite(id):
    content = Content.query.get_or_404(id)
    data = request.get_json(silent=True) if wants_json() or request.is_json else None
    action = (data.get("action") if data else None) or request.form.get("action") or ""
    action = action.strip()
    llm = current_app.extensions["llm_service"]
    service = RewriteService(llm)
    try:
        result = service.rewrite(content, action)
        _apply_risk(content)
        _log("content_rewrite", id, action)
        db.session.commit()
    except ValueError as e:
        db.session.rollback()
        if wants_json():
            return {"ok": False, "error": str(e)}, 400
        flash(str(e), "danger")
        return redirect(url_for("contents.detail", id=id))
    except Exception as e:  # noqa: BLE001
        db.session.rollback()
        if wants_json():
            return {"ok": False, "error": str(e)}, 500
        flash(f"改写失败：{e}", "danger")
        return redirect(url_for("contents.detail", id=id))

    if wants_json():
        return {"ok": True, **result}
    flash("改写完成", "success")
    return redirect(url_for("contents.detail", id=id))


@contents_bp.route("/<int:id>/save-review", methods=["POST"])
@login_required
def save_review(id):
    content = Content.query.get_or_404(id)
    content.status = "pending_review"
    pending = (
        ReviewRecord.query.filter_by(content_id=id, review_status="pending")
        .order_by(ReviewRecord.created_at.desc())
        .first()
    )
    if not pending:
        db.session.add(
            ReviewRecord(
                content_id=id,
                reviewer_id=None,
                review_status="pending",
            )
        )
    db.session.commit()
    _log("content_save_review", id, "进入审核池")
    if wants_json():
        return {"ok": True}
    flash("已送入审核池", "success")
    return redirect(url_for("reviews.detail", content_id=id))


@contents_bp.route("/<int:id>/export")
@login_required
def export_content(id):
    content = Content.query.get_or_404(id)
    if content.status != "approved":
        flash("仅审核通过的文案可导出", "danger")
        return redirect(url_for("contents.detail", id=id))

    fmt = (request.args.get("format") or "txt").lower()
    risk = _risk().scan_aggregate(content.title, content.body, content.comment_hook, content.cover_text)
    force = request.args.get("confirm") == "1" and getattr(current_user, "role", "") == "admin"

    if risk["level"] == "high" and not force and fmt != "copy":
        flash("高风险文案已阻止文件导出：管理员可在 URL 加 confirm=1，或改用「页面复制」模式", "warning")
        return redirect(url_for("contents.detail", id=id))

    if content.content_type == "chat":
        payload = {
            "export_template": "A_chat",
            "title": content.title,
            "role_a_lines": [],
            "role_b_lines": [],
            "comment_hook": content.comment_hook,
            "raw_body": content.body,
        }
        body = content.body or ""
        for line in body.splitlines():
            line = line.strip()
            if line.upper().startswith("A：") or line.upper().startswith("A:"):
                payload["role_a_lines"].append(line.split("：", 1)[-1].split(":", 1)[-1].strip())
            elif line.upper().startswith("B：") or line.upper().startswith("B:"):
                payload["role_b_lines"].append(line.split("：", 1)[-1].split(":", 1)[-1].strip())
    else:
        payload = {
            "export_template": "B_spoken",
            "title": content.title,
            "hook": (content.body or "")[:80],
            "body": content.body,
            "closing": content.comment_hook,
        }

    if fmt == "json":
        raw = json.dumps(payload, ensure_ascii=False, indent=2)
        return send_file(
            BytesIO(raw.encode("utf-8")),
            mimetype="application/json",
            as_attachment=True,
            download_name=f"content_{id}.json",
        )

    if fmt == "txt":
        if payload.get("export_template") == "A_chat":
            text = f"标题\n{content.title}\n\n"
            text += "角色A / 角色B\n" + (content.body or "") + "\n\n评论引导\n" + (content.comment_hook or "")
        else:
            text = (
                f"标题\n{content.title}\n\n开头钩子\n{payload.get('hook','')}\n\n"
                f"正文\n{content.body or ''}\n\n结尾互动\n{content.comment_hook or ''}"
            )
        return send_file(
            BytesIO(text.encode("utf-8")),
            mimetype="text/plain; charset=utf-8",
            as_attachment=True,
            download_name=f"content_{id}.txt",
        )

    return render_template("contents/export_copy.html", content=content, payload=payload, risk=risk)
