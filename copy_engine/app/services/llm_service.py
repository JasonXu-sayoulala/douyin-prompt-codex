import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


class LLMService:
    """统一封装大模型调用；无 API Key 时返回可解析的占位 JSON。"""

    def __init__(self, app=None):
        self._client = None
        self._model = "gpt-4o-mini"
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        self._model = app.config.get("OPENAI_MODEL", "gpt-4o-mini")
        key = app.config.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY", "")
        base = app.config.get("OPENAI_BASE_URL") or os.environ.get("OPENAI_BASE_URL", "")
        if key:
            try:
                from openai import OpenAI

                kwargs: dict[str, Any] = {"api_key": key}
                if base:
                    kwargs["base_url"] = base
                self._client = OpenAI(**kwargs)
            except Exception as e:  # noqa: BLE001
                logger.warning("OpenAI 客户端初始化失败，将使用占位输出: %s", e)
                self._client = None
        else:
            self._client = None

    def generate(self, prompt: str, system: str | None = None) -> str:
        if not self._client:
            return self._mock_json_response(prompt)

        try:
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            resp = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=0.85,
            )
            return (resp.choices[0].message.content or "").strip()
        except Exception as e:  # noqa: BLE001
            logger.exception("LLM 调用失败: %s", e)
            raise

    def _mock_json_response(self, prompt: str) -> str:
        """本地演示：未配置 Key 时返回固定结构 JSON 字符串。"""
        snippet = (prompt[:80] + "…") if len(prompt) > 80 else prompt
        payload = {
            "titles": [
                f"【演示】未配置 API，占位标题1：{snippet[:20]}",
                "【演示】占位标题2：情绪拉满的一瞬",
                "【演示】占位标题3：你站哪一边？",
            ],
            "bodies": [
                "【演示正文1】请在环境变量中配置 OPENAI_API_KEY 后重新生成。口语短句，留钩子。\n第二句制造信息差。",
                "【演示正文2】冲突前置，不评判对错，把情绪交给评论区。\n结尾一句反问。",
                "【演示正文3】更像聊天截图的节奏：短、碎、真实。",
            ],
            "comment_hooks": ["你遇到过吗？评论区说说。", "换作你会怎么做？"],
            "cover_texts": ["别划走", "看到最后"],
        }
        return json.dumps(payload, ensure_ascii=False)
