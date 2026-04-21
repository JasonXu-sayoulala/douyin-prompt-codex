"""媒体生成路由：文案 → 图片 → 视频"""
import logging
from flask import Blueprint, jsonify, request, render_template, send_file
from flask_login import login_required, current_user

from flask import current_app

from ..models import Content, Topic, CopyTemplate, db

logger = logging.getLogger(__name__)

bp = Blueprint("media", __name__, url_prefix="/media")


def _media():
    """始终用 create_app 里已 init_app 的实例，避免 None / str 路径错误。"""
    return current_app.extensions["media_service"]


@bp.route("/generate", methods=["GET", "POST"])
@login_required
def generate_media():
    """生成文案并转换为视频/走马灯"""
    if request.method == "GET":
        # 获取所有可用的模板和主题
        templates = CopyTemplate.query.filter_by(is_active=True).all()
        topics = Topic.query.order_by(Topic.created_at.desc()).limit(20).all()
        return render_template(
            "media/generate.html",
            templates=templates,
            topics=topics
        )
    
    # POST 请求：生成媒体
    data = request.get_json() or request.form
    
    topic_id = data.get("topic_id")
    template_id = data.get("template_id")
    media_type = data.get("media_type", "slideshow")  # slideshow 或 video
    num_images = int(data.get("num_images", 3))
    
    if not topic_id or not template_id:
        return jsonify({"error": "缺少必要参数"}), 400
    
    try:
        # 1. 生成文案
        logger.info(f"开始生成文案: topic_id={topic_id}, template_id={template_id}")
        
        # 获取主题和模板
        topic = Topic.query.get_or_404(topic_id)
        template = CopyTemplate.query.get_or_404(template_id)
        
        # 使用 content_service 生成文案
        from ..services.content_service import ContentService
        content_service = ContentService(current_app.extensions.get('llm_service'))
        
        contents = content_service.generate_contents(
            topic=topic,
            template=template,
            user_id=current_user.id
        )
        
        if not contents:
            return jsonify({"error": "文案生成失败"}), 500
        
        content = contents[0]  # 取第一个版本
        db.session.commit()
        
        if not content or not content.body:
            return jsonify({"error": "文案生成失败"}), 500
        
        # 2. 根据文案生成图片
        logger.info(f"开始生成图片: content_id={content.id}, num_images={num_images}")
        image_paths = _media().generate_images_from_copy(
            copy_text=content.body,
            num_images=num_images
        )
        
        if not image_paths:
            return jsonify({"error": "图片生成失败"}), 500
        
        # 3. 生成视频或走马灯
        if media_type == "slideshow":
            logger.info(f"开始生成走马灯视频: content_id={content.id}")
            overlay_parts = [
                (content.title or "").strip(),
                (content.body or "").strip(),
            ]
            if (content.comment_hook or "").strip():
                overlay_parts.append("【互动】" + (content.comment_hook or "").strip()[:500])
            overlay_text = "\n\n".join(p for p in overlay_parts if p)

            video_path = _media().create_slideshow_video(
                image_paths=image_paths,
                output_name=f"slideshow_{content.id}.mp4",
                duration_per_image=3.0,
                transition_duration=0.5,
                add_text_overlay=True,
                text_content=overlay_text[:4000],
            )
            
            return jsonify({
                "success": True,
                "content_id": content.id,
                "video_path": video_path,
                "image_paths": image_paths,
                "message": "走马灯视频生成成功"
            })
        else:
            # 其他媒体类型的处理
            return jsonify({
                "success": True,
                "content_id": content.id,
                "image_paths": image_paths,
                "message": "图片生成成功"
            })
    
    except Exception as e:
        logger.exception(f"媒体生成失败: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route("/download/<int:content_id>")
@login_required
def download_media(content_id):
    """下载生成的媒体文件"""
    try:
        # 查找对应的视频文件
        video_path = _media()._output_dir / f"slideshow_{content_id}.mp4"
        
        if not video_path.exists():
            return jsonify({"error": "文件不存在"}), 404
        
        return send_file(
            video_path,
            as_attachment=True,
            download_name=f"douyin_video_{content_id}.mp4"
        )
    
    except Exception as e:
        logger.exception(f"文件下载失败: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route("/preview/<int:content_id>")
@login_required
def preview_media(content_id):
    """预览生成的媒体"""
    content = Content.query.get_or_404(content_id)
    
    # 查找对应的视频和图片文件
    video_path = _media()._output_dir / f"slideshow_{content_id}.mp4"
    
    return render_template(
        "media/preview.html",
        content=content,
        video_exists=video_path.exists(),
        video_url=f"/media/download/{content_id}" if video_path.exists() else None
    )
