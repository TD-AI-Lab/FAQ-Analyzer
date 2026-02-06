from __future__ import annotations

import re
from typing import Any, Optional


def safe_get(d: dict[str, Any], *keys: str) -> Any:
    cur: Any = d
    for k in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


def normalize_text(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"\s+", " ", s).strip()
    return s


def short_text(text: str, max_chars: int) -> str:
    text = text or ""
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def score_badge_html(score: Any) -> str:
    if score is None:
        return "<span class='badge badge-gray'>Not scored</span>"
    try:
        sc = int(score)
    except Exception:
        return "<span class='badge badge-gray'>Not scored</span>"

    if sc >= 70:
        cls = "badge badge-green"
    elif sc >= 40:
        cls = "badge badge-orange"
    else:
        cls = "badge badge-red"
    return f"<span class='{cls}'>Score {sc}</span>"