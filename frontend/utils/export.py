from __future__ import annotations

import csv
import io
import json
from typing import Any

from .formatting import safe_get


def make_json_bytes(items: list[dict[str, Any]]) -> bytes:
    payload = {"items": items, "count": len(items)}
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def make_csv_bytes(items: list[dict[str, Any]]) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)

    writer.writerow(["id", "title", "score", "summary", "strengths", "weaknesses", "url"])
    for it in items:
        writer.writerow(
            [
                it.get("id", ""),
                it.get("title", ""),
                safe_get(it, "analysis", "score") if safe_get(it, "analysis") else "",
                safe_get(it, "analysis", "summary") if safe_get(it, "analysis") else "",
                safe_get(it, "analysis", "strengths") if safe_get(it, "analysis") else "",
                safe_get(it, "analysis", "weaknesses") if safe_get(it, "analysis") else "",
                it.get("url", ""),
            ]
        )

    return buf.getvalue().encode("utf-8")