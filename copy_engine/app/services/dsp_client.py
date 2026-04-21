from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests


class DSPClientError(RuntimeError):
    """Raised when the DSP video engine returns an error or is unreachable."""

    def __init__(self, message: str, *, status_code: int | None = None, payload: Any | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


@dataclass(slots=True)
class DSPClient:
    """Thin HTTP client for the FastAPI-based DSP video engine."""

    base_url: str
    api_key: str = ""
    timeout_seconds: int = 60

    @classmethod
    def from_app(cls, app) -> "DSPClient":
        return cls(
            base_url=(app.config.get("DSP_BASE_URL") or "http://127.0.0.1:8000").rstrip("/"),
            api_key=(app.config.get("DSP_API_KEY") or "").strip(),
            timeout_seconds=int(app.config.get("DSP_TIMEOUT_SECONDS") or 60),
        )

    def submit_render_job(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/api/render-jobs", json=payload)

    def get_render_job(self, job_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/render-jobs/{job_id}")

    def get_render_result(self, job_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/render-jobs/{job_id}/result")

    def retry_render_job(self, job_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._request("POST", f"/api/render-jobs/{job_id}/retry", json=payload or {})

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/api/health")

    def _request(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        headers = kwargs.pop("headers", {}) or {}
        headers.setdefault("Accept", "application/json")
        if self.api_key:
            headers.setdefault("Authorization", f"Bearer {self.api_key}")

        try:
            resp = requests.request(
                method=method,
                url=url,
                headers=headers,
                timeout=self.timeout_seconds,
                **kwargs,
            )
        except requests.RequestException as exc:
            raise DSPClientError(f"DSP 服务不可用：{exc}") from exc

        data: Any
        try:
            data = resp.json()
        except ValueError:
            data = {"ok": False, "error": {"message": resp.text[:1000]}}

        if resp.status_code >= 400:
            message = self._extract_error_message(data) or f"DSP 请求失败（HTTP {resp.status_code}）"
            raise DSPClientError(message, status_code=resp.status_code, payload=data)

        if isinstance(data, dict) and data.get("ok") is False:
            message = self._extract_error_message(data) or "DSP 返回失败响应"
            raise DSPClientError(message, status_code=resp.status_code, payload=data)

        if not isinstance(data, dict):
            raise DSPClientError("DSP 返回格式非法：预期 JSON object", status_code=resp.status_code, payload=data)
        return data

    @staticmethod
    def _extract_error_message(payload: Any) -> str:
        if isinstance(payload, dict):
            err = payload.get("error")
            if isinstance(err, dict):
                return str(err.get("message") or err.get("details") or "").strip()
            if err:
                return str(err).strip()
            if payload.get("message"):
                return str(payload["message"]).strip()
        return ""
