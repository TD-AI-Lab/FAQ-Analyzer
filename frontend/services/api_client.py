from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
import requests


class ApiError(RuntimeError):
    def __init__(self, message: str, status_code: Optional[int] = None, details: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.details = details


@dataclass
class ApiClient:
    base_url: str
    timeout_s: float = 600.0

    def _url(self, path: str) -> str:
        path = path if path.startswith("/") else f"/{path}"
        return f"{self.base_url}{path}"

    def get_json(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            r = requests.get(self._url(path), params=params, timeout=self.timeout_s)
        except requests.RequestException as e:
            raise ApiError(f"Network error calling GET {path}: {e}") from e

        if r.status_code >= 400:
            details = None
            try:
                details = r.json()
            except Exception:
                details = r.text
            raise ApiError(f"HTTP {r.status_code} calling GET {path}", status_code=r.status_code, details=details)

        try:
            return r.json()
        except Exception as e:
            raise ApiError(f"Invalid JSON from GET {path}", status_code=r.status_code, details=r.text) from e

    def post_json(self, path: str, params: dict[str, Any] | None = None, json_body: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            r = requests.post(self._url(path), params=params, json=json_body, timeout=self.timeout_s)
        except requests.RequestException as e:
            raise ApiError(f"Network error calling POST {path}: {e}") from e

        if r.status_code >= 400:
            details = None
            try:
                details = r.json()
            except Exception:
                details = r.text
            raise ApiError(f"HTTP {r.status_code} calling POST {path}", status_code=r.status_code, details=details)

        try:
            return r.json()
        except Exception as e:
            raise ApiError(f"Invalid JSON from POST {path}", status_code=r.status_code, details=r.text) from e

    # Convenience wrappers
    def health(self) -> dict[str, Any]:
        return self.get_json("/health")

    def faq(self, sort: str | None = None) -> dict[str, Any]:
        params = {}
        if sort:
            params["sort"] = sort
        return self.get_json("/faq", params=params)

    def scrape(self) -> dict[str, Any]:
        return self.post_json("/scrape")

    def clean(self) -> dict[str, Any]:
        return self.post_json("/clean")

    def analyze(self, force: bool = False) -> dict[str, Any]:
        params = {"force": "true" if force else "false"}
        return self.post_json("/analyze", params=params)