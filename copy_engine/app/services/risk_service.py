class RiskService:
    """敏感词扫描与风险等级。"""

    def __init__(self, app=None):
        self._words: list[str] = []
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        raw = app.config.get("SENSITIVE_WORDS", "") or ""
        self._words = [w.strip() for w in raw.replace("，", ",").split(",") if w.strip()]

    def scan(self, text: str) -> dict:
        if not text:
            return {"level": "low", "hits": [], "message": "无文本"}

        hits = [w for w in self._words if w and w in text]
        if not hits:
            return {"level": "low", "hits": [], "message": "未命中敏感词"}

        if len(hits) >= 3:
            level, message = "high", "高风险：命中多项敏感词，导出受限，请人工处理"
        elif len(hits) >= 2:
            level, message = "medium", "中风险：建议复核后再导出"
        else:
            level, message = "medium", "中风险：检测到敏感词，请结合语境复核"

        return {"level": level, "hits": hits, "message": message}

    def scan_aggregate(self, *parts: str | None) -> dict:
        merged = "\n".join(p or "" for p in parts)
        return self.scan(merged)
