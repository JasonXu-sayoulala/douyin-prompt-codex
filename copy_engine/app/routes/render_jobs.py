from __future__ import annotations

from flask import Blueprint, flash, redirect, request, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..models import Content

try:
    from ..models_rendering import MediaAsset, RenderJob, StoryboardScene
except ImportError:
    from ..models import MediaAsset, RenderJob, StoryboardScene  # type: ignore

from ..security import api_error
from ..services.dsp_client import DSPClientError
from ..services.render_dispatcher import RenderDispatcher

try:
    from ..utils import wants_json  # type: ignore
except Exception:  # pragma: no cover
    def wants_json() -> bool:
        return request.is_json or request.path.startswith("/api/")


render_jobs_bp = Blueprint("render_jobs", __name__, url_prefix="/render-jobs")


@render_jobs_bp.route("")
@login_required
def list_jobs():
    q = RenderJob.query.order_by(RenderJob.created_at.desc())
    status = (request.args.get("status") or "").strip()
    content_id = (request.args.get("content_id") or "").strip()

    if status:
        q = q.filter_by(status=status)
    if content_id.isdigit():
        q = q.filter_by(content_id=int(content_id))

    items = q.limit(100).all()
    return {
        "ok": True,
        "items": [_serialize_job(item) for item in items],
        "filters": {"status": status, "content_id": content_id},
    }


@render_jobs_bp.route("/<int:id>")
@login_required
def detail(id):
    job = RenderJob.query.get_or_404(id)
    assets = MediaAsset.query.filter_by(render_job_id=id).order_by(MediaAsset.id.asc()).all()
    scenes = StoryboardScene.query.filter_by(render_job_id=id).order_by(StoryboardScene.seq_no.asc()).all()
    return {
        "ok": True,
        "item": _serialize_job(job),
        "assets": [_serialize_asset(asset) for asset in assets],
        "storyboard": [_serialize_scene(scene) for scene in scenes],
    }


@render_jobs_bp.route("/content/<int:content_id>/submit", methods=["POST"])
@login_required
def submit_for_content(content_id):
    content = Content.query.get_or_404(content_id)
    if content.status != "approved":
        return api_error("仅审核通过的文案可提交视频生成。", 400, code="content_not_approved")

    data = request.get_json(silent=True) if wants_json() or request.is_json else None
    overrides = data.get("overrides") if isinstance(data, dict) else None
    dispatcher = RenderDispatcher()

    try:
        job = dispatcher.create_job_for_content(
            content,
            submitted_by=getattr(current_user, "id", None),
            overrides=overrides if isinstance(overrides, dict) else None,
        )
        dispatcher.submit_job(job)
        dispatcher.log_operation(
            user_id=getattr(current_user, "id", None),
            action="render_submit",
            target_id=job.id,
            detail=f"content={content_id}",
        )
        db.session.commit()
    except DSPClientError as exc:
        db.session.rollback()
        return api_error(str(exc), 502, code="dsp_unavailable")
    except Exception as exc:  # noqa: BLE001
        db.session.rollback()
        return api_error(str(exc), 500, code="render_submit_failed")

    if wants_json():
        return {"ok": True, "render_job_id": job.id, "status": job.status, "external_job_id": job.external_job_id}

    flash("已提交视频生成任务", "success")
    return redirect(url_for("render_jobs.detail", id=job.id))


@render_jobs_bp.route("/<int:id>/sync", methods=["POST"])
@login_required
def sync_job(id):
    job = RenderJob.query.get_or_404(id)
    dispatcher = RenderDispatcher()
    try:
        dispatcher.sync_job_status(job)
        dispatcher.log_operation(
            user_id=getattr(current_user, "id", None),
            action="render_sync",
            target_id=job.id,
            detail=f"status={job.status}",
        )
        db.session.commit()
    except DSPClientError as exc:
        db.session.rollback()
        return api_error(str(exc), 502, code="dsp_unavailable")
    except Exception as exc:  # noqa: BLE001
        db.session.rollback()
        return api_error(str(exc), 500, code="render_sync_failed")

    return {"ok": True, "item": _serialize_job(job)}


@render_jobs_bp.route("/<int:id>/retry", methods=["POST"])
@login_required
def retry_job(id):
    job = RenderJob.query.get_or_404(id)
    data = request.get_json(silent=True) if wants_json() or request.is_json else None
    reason = ((data or {}).get("reason") if isinstance(data, dict) else None) or request.form.get("reason") or "manual retry"
    dispatcher = RenderDispatcher()

    try:
        dispatcher.retry_job(job, reason=reason.strip())
        dispatcher.log_operation(
            user_id=getattr(current_user, "id", None),
            action="render_retry",
            target_id=job.id,
            detail=reason.strip()[:500],
        )
        db.session.commit()
    except DSPClientError as exc:
        db.session.rollback()
        return api_error(str(exc), 502, code="dsp_unavailable")
    except Exception as exc:  # noqa: BLE001
        db.session.rollback()
        return api_error(str(exc), 500, code="render_retry_failed")

    return {"ok": True, "item": _serialize_job(job)}


@render_jobs_bp.route("/<int:id>/preview")
@login_required
def preview_job(id):
    job = RenderJob.query.get_or_404(id)
    assets = MediaAsset.query.filter_by(render_job_id=id).all()
    video = next((a for a in assets if a.asset_type == "final_video"), None)
    poster = next((a for a in assets if a.asset_type == "poster"), None)
    execution_json = next((a for a in assets if a.asset_type == "execution_json"), None)
    return {
        "ok": True,
        "item": _serialize_job(job),
        "preview": {
            "video_url": video.file_url if video else None,
            "poster_url": poster.file_url if poster else None,
            "execution_url": execution_json.file_url if execution_json else None,
        },
    }


def _serialize_job(job: RenderJob) -> dict:
    return {
        "id": job.id,
        "content_id": job.content_id,
        "provider": job.provider,
        "job_type": job.job_type,
        "status": job.status,
        "priority": job.priority,
        "external_job_id": job.external_job_id,
        "retry_count": job.retry_count,
        "error_code": job.error_code,
        "error_message": job.error_message,
        "submitted_by": job.submitted_by,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
    }


def _serialize_asset(asset: MediaAsset) -> dict:
    return {
        "id": asset.id,
        "asset_type": asset.asset_type,
        "source_type": asset.source_type,
        "provider": asset.provider,
        "label": asset.label,
        "file_url": asset.file_url,
        "local_path": asset.local_path,
        "mime_type": asset.mime_type,
        "duration_seconds": float(asset.duration_seconds) if asset.duration_seconds is not None else None,
        "file_size_bytes": asset.file_size_bytes,
        "metadata_json": asset.metadata_json,
    }


def _serialize_scene(scene: StoryboardScene) -> dict:
    return {
        "id": scene.id,
        "seq_no": scene.seq_no,
        "scene_id": scene.scene_id,
        "duration_seconds": scene.duration_seconds,
        "narration": scene.narration,
        "onscreen_text": scene.onscreen_text,
        "shot_type": scene.shot_type,
        "transition_name": scene.transition_name,
        "objective": scene.objective,
        "visual_prompt": scene.visual_prompt,
        "negative_prompt": scene.negative_prompt,
        "camera_motion": scene.camera_motion,
        "metadata_json": scene.metadata_json,
    }
