from __future__ import annotations

import os
import time
from typing import Any

import streamlit as st
from dotenv import load_dotenv

from services.api_client import ApiClient, ApiError
from services.cache import fetch_health_cached, fetch_faq_cached, clear_all_caches
from ui.theme import apply_theme
from ui.components import (
    render_header,
    render_sidebar,
    render_empty_state,
    render_faq_list,
    render_connection_banner,
)
from utils.export import make_csv_bytes, make_json_bytes
from utils.formatting import safe_get, normalize_text


def resolve_backend_url() -> str:
    # Priority:
    # 1) Streamlit secrets (prod on Streamlit Cloud)
    # 2) Environment variable
    # 3) .env (local)
    # 4) localhost fallback
    try:
        secret_url = st.secrets.get("BACKEND_BASE_URL", None)  # type: ignore[attr-defined]
        if secret_url:
            return str(secret_url).rstrip("/")
    except Exception:
        pass

    env_url = os.getenv("BACKEND_BASE_URL")
    if env_url:
        return env_url.rstrip("/")

    return "http://localhost:8000"


def init_session_state() -> None:
    if "backend_url" not in st.session_state:
        st.session_state.backend_url = resolve_backend_url()
    if "compact_mode" not in st.session_state:
        st.session_state.compact_mode = False
    if "show_weaknesses" not in st.session_state:
        st.session_state.show_weaknesses = True
    if "show_full_content" not in st.session_state:
        st.session_state.show_full_content = False
    if "only_scored" not in st.session_state:
        st.session_state.only_scored = True
    if "score_range" not in st.session_state:
        st.session_state.score_range = (0, 100)
    if "sort_mode" not in st.session_state:
        st.session_state.sort_mode = "Score ↓"
    if "search_query" not in st.session_state:
        st.session_state.search_query = ""
    if "last_refresh_ts" not in st.session_state:
        st.session_state.last_refresh_ts = 0.0
    if "debug_log" not in st.session_state:
        st.session_state.debug_log = []


def log_debug(msg: str) -> None:
    st.session_state.debug_log.append(f"{time.strftime('%H:%M:%S')} {msg}")


def main() -> None:
    load_dotenv()  # allows local .env (optional)
    st.set_page_config(
        page_title="Workways FAQ Scorer",
        page_icon="📚",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    apply_theme()
    init_session_state()

    backend_url: str = st.session_state.backend_url
    client = ApiClient(base_url=backend_url)

    # Top: connection + health
    health = None
    health_error = None
    try:
        health = fetch_health_cached(client)
    except Exception as e:
        health_error = e
        log_debug(f"Health fetch failed: {repr(e)}")

    render_connection_banner(backend_url, health, health_error)

    # Sidebar: controls + filters + actions
    sidebar_result = render_sidebar(client, health)

    # If sidebar changed backend URL, reload client and clear caches
    if sidebar_result.get("backend_url_changed"):
        st.session_state.backend_url = sidebar_result["backend_url"]
        clear_all_caches()
        st.rerun()

    # Fetch FAQ list (prefer scored sorted)
    faq_payload = None
    faq_error = None
    try:
        faq_payload = fetch_faq_cached(client, sort="score")
    except Exception as e:
        faq_error = e
        log_debug(f"FAQ fetch failed: {repr(e)}")

    render_header(health, st.session_state.last_refresh_ts)

    if faq_error:
        st.error("Impossible de récupérer les données FAQ depuis le backend.")
        with st.expander("Détails techniques", expanded=False):
            st.code(str(faq_error))
            if st.session_state.debug_log:
                st.code("\n".join(st.session_state.debug_log))
        return

    items: list[dict[str, Any]] = (faq_payload or {}).get("items", [])
    if not items:
        render_empty_state(client)
        return

    # Build search blob & apply filters locally
    search_q = normalize_text(st.session_state.search_query)
    score_min, score_max = st.session_state.score_range
    only_scored = bool(st.session_state.only_scored)

    def get_score(it: dict[str, Any]) -> int | None:
        try:
            sc = safe_get(it, "analysis", "score")
            if sc is None:
                return None
            return int(sc)
        except Exception:
            return None

    filtered: list[dict[str, Any]] = []
    for it in items:
        sc = get_score(it)
        if only_scored and sc is None:
            continue
        if sc is not None and (sc < score_min or sc > score_max):
            continue

        blob = " ".join(
            [
                str(it.get("title", "")),
                str(safe_get(it, "analysis", "summary") or ""),
                str(safe_get(it, "analysis", "strengths") or ""),
                str(safe_get(it, "analysis", "weaknesses") or ""),
                str(it.get("content", "")),
                str(it.get("url", "")),
            ]
        )
        if search_q and search_q not in normalize_text(blob):
            continue

        filtered.append(it)

    # Local sorting options
    sort_mode = st.session_state.sort_mode
    if sort_mode == "Score ↓":
        filtered.sort(key=lambda x: (get_score(x) is not None, get_score(x) or -1), reverse=True)
    elif sort_mode == "Score ↑":
        filtered.sort(key=lambda x: (get_score(x) is None, get_score(x) or 10**9))
    elif sort_mode == "Titre A→Z":
        filtered.sort(key=lambda x: str(x.get("title", "")).lower())
    elif sort_mode == "Titre Z→A":
        filtered.sort(key=lambda x: str(x.get("title", "")).lower(), reverse=True)

    # Export bar
    col_a, col_b, col_c, col_d = st.columns([1, 1, 3, 3], vertical_alignment="center")
    with col_a:
        st.download_button(
            label="⬇️ Export JSON",
            data=make_json_bytes(filtered),
            file_name="faq_filtered.json",
            mime="application/json",
            use_container_width=True,
        )
    with col_b:
        st.download_button(
            label="⬇️ Export CSV",
            data=make_csv_bytes(filtered),
            file_name="faq_filtered.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with col_c:
        st.caption(f"Affichées : **{len(filtered)}** / {len(items)}")
    with col_d:
        st.caption("Astuce : utilise la recherche + slider score pour isoler les pages les plus faibles.")

    # Render list
    render_faq_list(
        filtered,
        compact_mode=bool(st.session_state.compact_mode),
        show_weaknesses=bool(st.session_state.show_weaknesses),
        show_full_content=bool(st.session_state.show_full_content),
    )


if __name__ == "__main__":
    main()