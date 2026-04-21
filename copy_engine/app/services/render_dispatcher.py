from __future__ import annotations

import mimetypes
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from flask import current_app

from ..extensions import db
from ..models import Content
from ..models import OperationLog

try:
    from ..models_rendering import MediaAsset, RenderJob, StoryboardScene
except ImportError:
    from ..models import MediaAsset, RenderJob, StoryboardScene  # type: ignore

from .dsp_client import DSPClient


RUNNING_STATUSES = {"submitted", "planning", "generating_assets", "rendering"}
FINAL_STATUSES = {"succeeded", "failed", "canceled"}

DSP_TO_LOCAL_STATUS = {
    "queued": "submitted",
    "submitted": "submitted",
    "planning": "planning",
    "asset_generation": "generating_assets",
    "generating_assets": "generating_assets",
    "timeline_render": "rendering",
    "rendering": "rendering",
    "done": "succeeded",
    "succeeded": "succeeded",
    "error": "failed",
    "failed": "failed",
    "cancelled": "canceled",
    "canceled": "canceled",
}


class RenderDispatcher:
    """Bridge between Flask content records and the DSP video engine."""

    def __init__(self, client: DSPClient | None = None):
        self.client = client or self._get_client()

    def create_job_for_content(
        self,
        content: Content,
        *,
        provider: str = "dsp",
        submitted_by: int | None = None,
        priority: int = 5,
        overrides: dict[str, Any] | None = None,
    ) -> RenderJob:
        payload = self.build_payload(content, overrides=overrides)
        job = RenderJob(
            content_id=content.id,
            provider=provider,
            job_type="single_video",
            status="queued",
            priority=priority,
            request_payload_json=payload,
            submitted_by=submitted_by,
        )
        db.session.add(job)
        db.session.flush()
        return job

    def submit_job(self, job: RenderJob) -> RenderJob:
        if not job.request_payload_json:
            raise ValueError("渲染任务缺少 request_payload_json")

        response = self.client.submit_render_job(job.request_payload_json)
        job.external_job_id = str(response.get("job_id") or response.get("external_job_id") or "").strip() or None
        job.external_trace_id = str(response.get("trace_id") or "").strip() or None
        job.latest_response_json = response
        job.status = self._normalize_status(response.get("status") or "submitted")
        if job.status in RUNNING_STATUSES and not job.started_at:
            job.started_at = self._now()
        db.session.add(job)
        return job

    def sync_job_status(self, job: RenderJob, *, fetch_result_on_success: bool = True) -> RenderJob:
        if not job.external_job_id:
            raise ValueError("渲染任务缺少 external_job_id，无法同步状态")

        status_payload = self.client.get_render_job(job.external_job_id)
        job.latest_response_json = status_payload
        job.status = self._normalize_status(status_payload.get("status") or job.status)

        if job.status in RUNNING_STATUSES and not job.started_at:
            job.started_at = self._now()

        if job.status in FINAL_STATUSES:
            job.finished_at = self._now()
            error_obj = status_payload.get("error") or {}
            if isinstance(error_obj, dict):
                job.error_code = str(error_obj.get("code") or "").strip() or None
                job.error_message = str(error_obj.get("message") or "").strip() or None
            elif error_obj:
                job.error_message = str(error_obj)

            if job.status == "succeeded" and fetch_result_on_success:
                result_payload = self.client.get_render_result(job.external_job_id)
                self.ingest_result(job, result_payload)
                job.latest_response_json = result_payload

        db.session.add(job)
        return job

    def retry_job(self, job: RenderJob, *, reason: str = "manual retry") -> RenderJob:
        if not job.external_job_id:
            raise ValueError("渲染任务缺少 external_job_id，无法重试")

        response = self.client.retry_render_job(
            job.external_job_id,
            payload={"reason": reason},
        )
        job.retry_count = int(job.retry_count or 0) + 1
        job.latest_response_json = response
        job.external_job_id = str(response.get("job_id") or job.external_job_id)
        job.status = self._normalize_status(response.get("status") or "submitted")
        job.error_code = None
        job.error_message = None
        job.finished_at = None
        if not job.started_at:
            job.started_at = self._now()
        db.session.add(job)
        return job

    def ingest_result(self, job: RenderJob, result_payload: dict[str, Any]) -> None:
        self._replace_storyboard(job, result_payload.get("storyboard") or [])
        self._replace_assets(job, result_payload.get("artifacts") or [])
        job.status = self._normalize_status(result_payload.get("status") or job.status)
        if job.status in FINAL_STATUSES and not job.finished_at:
            job.finished_at = self._now()
        db.session.add(job)

    def build_payload(self, content: Content, *, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
        topic = getattr(content, "topic", None)
        template = getattr(content, "copy_template", None)
        payload: dict[str, Any] = {
            "request_id": f"rj_{content.id}_{uuid4().hex[:8]}",
            "content_id": content.id,
            "job_type": "single_video",
            "priority": 5,
            "script_payload": {
                "title": (content.title or "").strip(),
                "hook": self._build_hook(content),
                "body": (content.body or "").strip(),
                "cta": (content.comment_hook or "").strip(),
                "cover_text": (content.cover_text or "").strip(),
            },
            "style_payload": {
                "duration_seconds": 20,
                "tone": self._infer_tone(content),
                "visual_style": "写实纪实，竖屏，抖音节奏，适合短视频口播/剧情切片",
                "language": "zh-CN",
            },
            "audio_payload": {
                "voice_mode": "tts",
                "music_mode": "hot_music_first",
                "preferred_music_id": None,
            },
            "source_payload": {
                "topic_id": getattr(content, "topic_id", None),
                "topic_title": getattr(topic, "title", "") if topic else "",
                "template_id": getattr(content, "template_id", None),
                "template_name": getattr(template, "name", "") if template else "",
                "content_type": (content.content_type or "spoken").strip(),
                "risk_level": (content.risk_level or "low").strip(),
            },
        }
        if overrides:
            payload = self._deep_merge(payload, overrides)
        return payload

    def log_operation(self, *, user_id: int | None, action: str, target_id: int, detail: str) -> None:
        db.session.add(
            OperationLog(
                user_id=user_id,
                action=action,
                target_type="render_jobs",
                target_id=target_id,
                detail=detail[:2000],
            )
        )

    @staticmethod
    def _build_hook(content: Content) -> str:
        title = (content.title or "").strip()
        body = (content.body or "").strip().splitlines()
        if body:
            first_line = body[0].strip()
            return first_line[:120]
        return title[:120]

    @staticmethod
    def _infer_tone(content: Content) -> str:
        tones: list[str] = ["高代入", "口语化"]
        if (content.content_type or "") == "chat":
            tones.append("聊天记录节奏")
        else:
            tones.append("口播节奏")
        if (content.risk_level or "") in {"medium", "high"}:
            tones.append("高争议")
        return "、".join(tones)

    def _replace_storyboard(self, job: RenderJob, storyboard_items: list[dict[str, Any]]) -> None:
        StoryboardScene.query.filter_by(render_job_id=job.id).delete()
        for idx, item in enumerate(storyboard_items, start=1):
            db.session.add(
                StoryboardScene(
                    render_job_id=job.id,
                    content_id=job.content_id,
                    seq_no=int(item.get("seq_no") or idx),
                    scene_id=str(item.get("scene_id") or f"scene-{idx}"),
                    duration_seconds=int(item.get("duration_seconds") or 3),
                    narration=item.get("narration"),
                    onscreen_text=item.get("onscreen_text"),
                    shot_type=item.get("shot_type"),
                    transition_name=item.get("transition") or item.get("transition_name"),
                    objective=item.get("objective"),
                    visual_prompt=item.get("visual_prompt"),
                    negative_prompt=item.get("negative_prompt"),
                    camera_motion=item.get("camera_motion"),
                    metadata_json=item,
                )
            )

    def _replace_assets(self, job: RenderJob, artifacts: list[dict[str, Any]]) -> None:
        MediaAsset.query.filter_by(render_job_id=job.id).delete()
        for item in artifacts:
            url = item.get("url") or item.get("file_url") or item.get("remote_url")
            local_path = item.get("local_path")
            asset_type = str(item.get("asset_type") or "unknown")
            mime_type = item.get("mime_type") or self._guess_mime_type(url or local_path)
            db.session.add(
                MediaAsset(
                    render_job_id=job.id,
                    content_id=job.content_id,
                    asset_type=asset_type,
                    source_type=str(item.get("source_type") or "generated"),
                    provider=job.provider,
                    label=item.get("label"),
                    file_url=url,
                    local_path=local_path,
                    storage_key=item.get("storage_key"),
                    mime_type=mime_type,
                    duration_seconds=item.get("duration_seconds"),
                    file_size_bytes=item.get("file_size_bytes"),
                    checksum=item.get("checksum"),
                    metadata_json=item,
                )
            )

    @staticmethod
    def _guess_mime_type(path: str | None) -> str | None:
        if not path:
            return None
        guessed, _ = mimetypes.guess_type(path)
        return guessed

    @staticmethod
    def _normalize_status(raw: str) -> str:
        status = str(raw or "").strip().lower()
        return DSP_TO_LOCAL_STATUS.get(status, status or "queued")

    @staticmethod
    def _deep_merge(base: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
        merged = dict(base)
        for key, value in extra.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = RenderDispatcher._deep_merge(merged[key], value)
            else:
                merged[key] = value
        return merged

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _get_client() -> DSPClient:
        client = current_app.extensions.get("dsp_client")
        if client is None:
            client = DSPClient.from_app(current_app)
            current_app.extensions["dsp_client"] = client
        return client
