"""爆款素材拆解服务：素材评分、爆点提炼、转选题。"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

from ..extensions import db
from ..models import MaterialInsight, SourceMaterial, Topic


@dataclass(frozen=True)
class KeywordProfile:
    category: str
    keywords: tuple[str, ...]
    audience: str


PROFILES: tuple[KeywordProfile, ...] = (
    KeywordProfile("情侣冲突", ("分手", "前任", "男朋友", "女朋友", "恋爱", "冷处理", "复合", "异地"), "恋爱关系里正在拉扯的人"),
    KeywordProfile("婚姻现实", ("婆婆", "儿媳", "婆媳", "老公", "老婆", "婚姻", "彩礼", "房贷", "孩子", "娘家", "婆家"), "被家庭关系和现实责任夹住的人"),
    KeywordProfile("职场情绪", ("老板", "同事", "领导", "加班", "工资", "辞职", "背锅", "绩效", "裁员"), "在职场里憋着情绪的普通人"),
    KeywordProfile("站队争议", ("该不该", "凭什么", "到底", "谁错", "站哪边", "公平", "双标", "底线"), "喜欢在评论区表达立场的人"),
    KeywordProfile("口播观点", ("成年人", "现实", "人性", "清醒", "格局", "沉默", "关系", "价值"), "爱看现实观点和情绪共鸣的人"),
    KeywordProfile("聊天记录剧情", ("A：", "B：", "A:", "B:", "微信", "聊天", "已读", "消息"), "爱看聊天截图剧情反转的人"),
)

CONFLICT_WORDS = (
    "争吵", "冷战", "分手", "婚姻", "翻脸", "崩溃", "委屈", "质问", "拉黑",
    "道歉", "偏心", "不回", "背叛", "算计", "隐瞒", "反转", "真相", "凭什么", "该不该",
)

DISCUSSION_WORDS = (
    "你怎么看", "评论区", "换作你", "到底谁", "站哪边", "该不该", "凭什么", "有没有同款",
    "支持", "反对", "怎么选", "忍不忍", "谁错了",
)

PAIN_WORDS = (
    "委屈", "心寒", "崩溃", "难受", "累", "失望", "没钱", "房贷", "彩礼", "孩子", "加班",
    "不被理解", "没人帮", "忍", "亏欠", "后悔", "现实",
)


def _clean_lines(text: str | None, limit: int = 12) -> list[str]:
    raw = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    lines: list[str] = []
    for part in re.split(r"[\n。！？!?]", raw):
        s = part.strip(" \t，,；;：:")
        if s:
            lines.append(s)
        if len(lines) >= limit:
            break
    return lines


def _hit_count(text: str, words: tuple[str, ...]) -> int:
    return sum(text.count(w) for w in words if w)


class MaterialInsightService:
    """本地规则版爆点引擎，保证无外部 API 时也可用。"""

    def infer_category(self, material: SourceMaterial) -> str:
        if material.category:
            return material.category
        text = self._joined_text(material)
        best_name = "站队争议"
        best_score = 0
        for profile in PROFILES:
            score = _hit_count(text, profile.keywords)
            if score > best_score:
                best_name = profile.category
                best_score = score
        return best_name

    def score_material(self, material: SourceMaterial) -> tuple[int, int]:
        text = self._joined_text(material)
        engagement = max(0, int(material.like_count or 0))
        engagement += max(0, int(material.comment_count or 0)) * 2
        engagement += max(0, int(material.share_count or 0)) * 3
        engagement += max(0, int(material.collect_count or 0)) * 2

        conflict_bonus = min(28, _hit_count(text, CONFLICT_WORDS) * 4)
        emotion_bonus = min(18, _hit_count(text, PAIN_WORDS) * 3)
        discussion_bonus = min(16, _hit_count(text, DISCUSSION_WORDS) * 4)
        length_bonus = 8 if 60 <= len(text) <= 900 else 2
        engagement_score = int(min(32, math.log10(engagement + 1) * 10)) if engagement else 0

        viral_score = min(100, 18 + engagement_score + conflict_bonus + emotion_bonus + length_bonus)
        comment_signal = min(30, int(math.log10(max(1, int(material.comment_count or 0)) + 1) * 12))
        discussion_score = min(100, 16 + comment_signal + conflict_bonus + discussion_bonus)
        return int(viral_score), int(discussion_score)

    def analyze(self, material: SourceMaterial) -> MaterialInsight:
        viral_score, discussion_score = self.score_material(material)
        material.viral_score = viral_score
        material.discussion_score = discussion_score
        material.category = self.infer_category(material)
        material.status = "analyzed"

        insight = MaterialInsight(
            material_id=material.id,
            conflict_point=self._extract_conflict(material),
            pain_point=self._extract_pain(material),
            audience=self._infer_audience(material),
            hook=self._build_hook(material),
            story_angle=self._build_story_angle(material),
            rewrite_suggestion=self._build_rewrite_suggestion(material),
            risk_note=self._build_risk_note(material),
            viral_score=viral_score,
            discussion_score=discussion_score,
        )
        db.session.add(material)
        db.session.add(insight)
        db.session.flush()
        return insight

    def create_topic_from_material(self, material: SourceMaterial, user_id: int | None = None) -> Topic:
        insight = (
            MaterialInsight.query.filter_by(material_id=material.id)
            .order_by(MaterialInsight.created_at.desc())
            .first()
        )
        if insight is None:
            insight = self.analyze(material)

        title = (insight.hook or material.title or "爆款素材转选题").strip()
        title = re.sub(r"^如果把这个素材改成抖音文案：", "", title).strip()
        tags = ",".join(
            x for x in [material.tags or "", "爆款素材", f"素材{material.id}"] if x
        )[:255]
        emotion_level = 5 if max(material.viral_score or 0, material.discussion_score or 0) >= 75 else 4
        topic = Topic(
            title=title[:255],
            category=material.category or self.infer_category(material),
            tags=tags or None,
            emotion_level=emotion_level,
            source=f"material:{material.id}:{material.platform or 'manual'}",
            status="draft",
        )
        db.session.add(topic)
        material.status = "selected"
        db.session.add(material)
        db.session.flush()
        return topic

    def _joined_text(self, material: SourceMaterial) -> str:
        return "\n".join(
            p for p in [material.title, material.raw_text, material.hot_comments, material.tags] if p
        )[:6000]

    def _extract_conflict(self, material: SourceMaterial) -> str:
        lines = _clean_lines(self._joined_text(material), limit=20)
        for line in lines:
            if any(w in line for w in CONFLICT_WORDS):
                return line[:220]
        if material.title:
            return material.title[:220]
        return "素材里已经具备情绪对立，但需要在开头进一步明确双方立场。"

    def _extract_pain(self, material: SourceMaterial) -> str:
        lines = _clean_lines(self._joined_text(material), limit=20)
        for line in lines:
            if any(w in line for w in PAIN_WORDS):
                return line[:220]
        return "痛点集中在关系里的不被理解、现实压力和情绪补偿。"

    def _infer_audience(self, material: SourceMaterial) -> str:
        text = self._joined_text(material)
        category = material.category or self.infer_category(material)
        for profile in PROFILES:
            if profile.category == category:
                return profile.audience
        if "婆" in text or "孩子" in text:
            return "正在处理家庭关系的人"
        if "老板" in text or "同事" in text:
            return "对职场关系有共鸣的人"
        return "容易被现实关系和情绪冲突触发共鸣的人"

    def _build_hook(self, material: SourceMaterial) -> str:
        base = (material.title or "").strip()
        if not base:
            lines = _clean_lines(material.raw_text or material.hot_comments, limit=2)
            base = lines[0] if lines else "这件事评论区一定会吵起来"
        if any(k in base for k in ("？", "?", "该不该", "凭什么")):
            return base[:255]
        return f"{base}，到底是谁先过分了？"[:255]

    def _build_story_angle(self, material: SourceMaterial) -> str:
        conflict = self._extract_conflict(material)
        category = material.category or self.infer_category(material)
        return f"按「{category}」处理：开头先抛出冲突，再补一处现实细节，结尾留站队问题。冲突核：{conflict[:160]}"

    def _build_rewrite_suggestion(self, material: SourceMaterial) -> str:
        return (
            "建议生成 3 个版本：1）聊天记录型，放大双方短句对峙；"
            "2）口播观点型，用一句现实判断切入；3）剧情摘要型，保留反转和评论争议点。"
        )

    def _build_risk_note(self, material: SourceMaterial) -> str:
        text = self._joined_text(material)
        if any(w in text for w in ("高敏", "禁词", "违规", "极端")):
            return "素材疑似包含平台敏感表达，生成文案前必须人工复核语境。"
        return "未发现明显高风险表达，仍建议审核后发布。"


material_insight_service = MaterialInsightService()
