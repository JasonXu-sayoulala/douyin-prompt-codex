import json
import re
import logging
from typing import Any

from ..extensions import db
from ..models import Content, RewriteLog
from .llm_service import LLMService

logger = logging.getLogger(__name__)

ACTION_INSTRUCTIONS: dict[str, str] = {
    "more_human": "更像真人：语气词、停顿、不完美表达，减少排比套话",
    "more_conflict": "更有争议：强化对立立场，但仍不给出道德审判式结论",
    "more_piercing": "更扎心：现实细节、具体损失感，避免空洞鸡汤",
    "shorten": "更短：总字数压到原来约一半，保留核心冲突",
    "chat_format": "改成聊天记录格式：用「A：」「B：」短对话呈现，8~15 轮以内",
    "spoken_format": "改成口播格式：开头钩子一句，中间三段口语，结尾互动一句",
    "regen_3": "再生成 3 版：同一内核输出 3 段不同切入的正文，每段独立成段",
}


def _strip_json_fence(raw: str) -> str:
    s = raw.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    return s.strip()


class RewriteService:
    def __init__(self, llm: LLMService | None = None):
        self.llm = llm or LLMService()

    def build_rewrite_prompt(self, body: str, action: str) -> str:
        desc = ACTION_INSTRUCTIONS.get(action, action)
        if action == "regen_3":
            return f"""请对下面文案做改写。

改写目标：{desc}

要求：
1. 保留核心冲突
2. 提高真实感
3. 不要写成长文章
4. 适合抖音口语表达

请只输出 JSON：{{"bodies": ["第一版正文","第二版正文","第三版正文"]}}

原文如下：
{body}
"""

        return f"""请对下面文案做改写。

改写目标：{desc}
要求：
1. 保留核心冲突
2. 提高真实感
3. 不要写成长文章
4. 适合抖音口语表达

请只输出 JSON：{{"body": "改写后的完整正文"}}

原文如下：
{body}
"""

    def rewrite(self, content: Content, action: str) -> dict[str, Any]:
        if action not in ACTION_INSTRUCTIONS:
            raise ValueError(f"不支持的改写动作: {action}")

        before = content.body or ""
        prompt = self.build_rewrite_prompt(before, action)
        raw = self.llm.generate(
            prompt,
            system="你是抖音口语文案编辑，只输出合法 JSON。",
        )

        try:
            data = json.loads(_strip_json_fence(raw))
        except json.JSONDecodeError:
            m = re.search(r"\{[\s\S]*\}", raw)
            data = json.loads(m.group()) if m else {"body": raw}

        log = RewriteLog(
            content_id=content.id,
            action=action,
            before_text=before,
            after_text="",
        )

        if action == "regen_3":
            bodies = data.get("bodies") or []
            if not bodies:
                bodies = [raw]
            joined = "\n\n---\n\n".join(bodies[:3])
            log.after_text = joined
            content.body = joined
        else:
            new_body = data.get("body") or raw
            log.after_text = new_body
            content.body = new_body

        content.version_no = (content.version_no or 1) + 1
        db.session.add(log)
        db.session.add(content)
        db.session.flush()

        return {
            "content_id": content.id,
            "action": action,
            "body": content.body,
            "version_no": content.version_no,
        }
