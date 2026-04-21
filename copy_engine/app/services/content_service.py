import json
import re
import logging
from typing import Any

from ..extensions import db
from ..models import Content, Topic, CopyTemplate
from .llm_service import LLMService

logger = logging.getLogger(__name__)

SYSTEM_ROLE = "你是抖音情绪类爆款文案专家，只输出合法 JSON，不要 Markdown 围栏。"


def _strip_json_fence(raw: str) -> str:
    s = raw.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    return s.strip()


def _parse_llm_json(raw: str) -> dict[str, Any]:
    try:
        return json.loads(_strip_json_fence(raw))
    except json.JSONDecodeError:
        logger.warning("JSON 解析失败，尝试截取花括号")
        m = re.search(r"\{[\s\S]*\}", raw)
        if m:
            return json.loads(m.group())
        raise


class ContentService:
    def __init__(self, llm: LLMService | None = None):
        self.llm = llm or LLMService()

    def build_prompt(
        self,
        topic: Topic,
        template: CopyTemplate,
        content_type: str,
        emotion_level: int,
        max_length: int,
        variants: int,
    ) -> str:
        return f"""你是抖音情绪类爆款文案专家。

目标：围绕给定选题写适合抖音发布的情绪类文案。

要求：
1. 开头直接冲突
2. 句子短，口语化
3. 留争议，不给标准答案
4. 适合聊天记录/口播视频
5. 每版正文控制在约 {max_length} 字以内

请严格输出一个 JSON 对象（不要其它文字），字段如下：
- titles: 字符串数组，3~5 个标题
- bodies: 字符串数组，恰好 {variants} 条正文版本
- comment_hooks: 字符串数组，2~3 条评论引导
- cover_texts: 字符串数组，2~3 条封面短句

选题：{topic.title}
分类：{topic.category or '未分类'}
模板名称：{template.name}
模板补充说明（创作时可融合）：{template.prompt[:2000]}
内容类型：{content_type}（chat=聊天记录型，spoken=口播型，story=剧情摘要型）
情绪强度：{emotion_level}（1-5）
"""

    def generate_contents(
        self,
        topic: Topic,
        template: CopyTemplate,
        content_type: str = "chat",
        emotion_level: int = 3,
        max_length: int = 280,
        variants: int = 3,
        user_id: int | None = None,
    ) -> list[Content]:
        prompt = self.build_prompt(
            topic, template, content_type, emotion_level, max_length, variants
        )
        raw = self.llm.generate(prompt, system=SYSTEM_ROLE)
        data = _parse_llm_json(raw)

        titles = data.get("titles") or []
        bodies = data.get("bodies") or []
        hooks = data.get("comment_hooks") or []
        covers = data.get("cover_texts") or []

        if not bodies:
            bodies = [raw[:4000]]

        created: list[Content] = []
        for i, body in enumerate(bodies):
            title = titles[i % len(titles)] if titles else f"版本{i + 1}"
            ch = "\n".join(hooks) if hooks else ""
            cv = "\n".join(covers) if covers else ""
            c = Content(
                topic_id=topic.id,
                template_id=template.id,
                title=title,
                body=body,
                comment_hook=ch,
                cover_text=cv,
                content_type=content_type,
                version_no=i + 1,
                status="generated",
                created_by=user_id,
            )
            db.session.add(c)
            created.append(c)

        topic.status = "generated"
        db.session.add(topic)
        db.session.flush()
        return created


# 全局实例
content_service = ContentService()
