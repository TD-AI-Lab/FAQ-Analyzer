from __future__ import annotations

import time
from typing import Any, Optional

import streamlit as st

from services.api_client import ApiClient, ApiError
from services.cache import clear_all_caches
from utils.formatting import score_badge_html, safe_get, short_text
from .text import APP_TITLE, APP_SUBTITLE, EMPTY_STATE


def render_connection_banner(backend_url: str, health: Optional[dict[str, Any]], err: Optional[Exception]) -> None:
    top = st.container()
    with top:
        cols = st.columns([2, 3, 3], vertical_alignment="center")
        with cols[0]:
            st.markdown(f"### 📚 {APP_TITLE}")
            st.caption(APP_SUBTITLE)
        with cols[1]:
            st.caption("Backend")
            st.code(backend_url, language=None)
        with cols[2]:
            if err or not health:
                st.error("Backend indisponible")
            else:
                st.success("Backend OK")


def render_header(health: Optional[dict[str, Any]], last_refresh_ts: float) -> None:
    counts = (health or {}).get("counts", {}) if isinstance(health, dict) else {}
    raw = int(counts.get("raw", 0) or 0)
    clean = int(counts.get("clean", 0) or 0)
    scored = int(counts.get("scored", 0) or 0)

    c1, c2, c3, c4 = st.columns([1, 1, 1, 2], vertical_alignment="center")
    with c1:
        st.metric("Raw", raw)
    with c2:
        st.metric("Clean", clean)
    with c3:
        st.metric("Scored", scored)
    with c4:
        if last_refresh_ts:
            st.caption(f"Dernier refresh (client) : {time.strftime('%H:%M:%S', time.localtime(last_refresh_ts))}")
        else:
            st.caption("Dernier refresh (client) : —")


def render_sidebar(client: ApiClient, health: Optional[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {"backend_url_changed": False, "backend_url": client.base_url}

    with st.sidebar:
        st.markdown("## ⚙️ Paramètres")
        new_url = st.text_input("Backend URL", value=st.session_state.backend_url, help="URL du backend FastAPI.")
        if new_url.rstrip("/") != st.session_state.backend_url.rstrip("/"):
            out["backend_url_changed"] = True
            out["backend_url"] = new_url.rstrip("/")
            return out

        st.markdown("## 🔄 Actions")
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("Scrape", use_container_width=True):
                _run_action(client, "scrape")
        with col_b:
            if st.button("Clean", use_container_width=True):
                _run_action(client, "clean")

        force = st.toggle("Force re-analyze", value=False, help="Recalcule le scoring même si déjà présent.")
        if st.button("Analyze", use_container_width=True):
            _run_action(client, "analyze", force=force)

        st.markdown("---")
        st.markdown("## 🔎 Filtres")

        st.session_state.search_query = st.text_input(
            "Recherche",
            value=st.session_state.search_query,
            placeholder="mots-clés (titre, résumé, contenu...)",
        )

        st.session_state.score_range = st.slider(
            "Score",
            0,
            100,
            value=st.session_state.score_range,
            help="Filtrer les éléments scorés par plage.",
        )

        st.session_state.only_scored = st.checkbox("Afficher uniquement scorées", value=st.session_state.only_scored)

        st.session_state.sort_mode = st.selectbox(
            "Tri",
            options=["Score ↓", "Score ↑", "Titre A→Z", "Titre Z→A"],
            index=["Score ↓", "Score ↑", "Titre A→Z", "Titre Z→A"].index(st.session_state.sort_mode),
        )

        st.markdown("---")
        st.markdown("## 🧩 Affichage")
        st.session_state.compact_mode = st.toggle("Compact mode", value=st.session_state.compact_mode)
        st.session_state.show_weaknesses = st.toggle("Afficher faiblesses", value=st.session_state.show_weaknesses)
        st.session_state.show_full_content = st.toggle("Afficher contenu complet", value=st.session_state.show_full_content)

        st.markdown("---")
        with st.expander("🧪 Debug", expanded=False):
            st.write("Health (raw):")
            st.json(health or {})

    return out


def _run_action(client: ApiClient, action: str, force: bool = False) -> None:
    with st.status("Exécution en cours…", expanded=False) as status:
        try:
            if action == "scrape":
                res = client.scrape()
            elif action == "clean":
                res = client.clean()
            elif action == "analyze":
                res = client.analyze(force=force)
            else:
                raise ValueError(f"Unknown action: {action}")

            status.update(label="Terminé ✅", state="complete")
            st.toast("Action terminée", icon="✅")

            st.session_state.last_refresh_ts = time.time()
            clear_all_caches()
            st.rerun()
            
            # Pretty result
            created = res.get("created", 0)
            updated = res.get("updated", 0)
            skipped = res.get("skipped", 0)
            errors = res.get("errors", 0)
            st.success(f"{action.upper()} OK — created={created} updated={updated} skipped={skipped} errors={errors}")
        except ApiError as e:
            status.update(label="Erreur ❌", state="error")
            st.error(f"Erreur backend: {e}")
            if e.details:
                with st.expander("Détails", expanded=False):
                    st.code(str(e.details))
        except Exception as e:
            status.update(label="Erreur ❌", state="error")
            st.error(f"Erreur: {e}")


def render_empty_state(client: ApiClient) -> None:
    st.info(EMPTY_STATE)
    cols = st.columns([1, 1, 1, 3], vertical_alignment="center")
    with cols[0]:
        if st.button("Scrape", use_container_width=True):
            _run_action(client, "scrape")
    with cols[1]:
        if st.button("Clean", use_container_width=True):
            _run_action(client, "clean")
    with cols[2]:
        if st.button("Analyze", use_container_width=True):
            _run_action(client, "analyze")
    with cols[3]:
        st.caption("Tu peux lancer les actions dans l’ordre. L’UI se mettra à jour après chaque étape.")


def render_faq_list(
    items: list[dict[str, Any]],
    compact_mode: bool,
    show_weaknesses: bool,
    show_full_content: bool,
) -> None:
    st.markdown("## 📄 Résultats")

    for it in items:
        title = str(it.get("title", "") or "Sans titre")
        url = str(it.get("url", "") or "")
        word_count = it.get("word_count", None)

        score = safe_get(it, "analysis", "score")
        summary = safe_get(it, "analysis", "summary") or ""
        strengths = safe_get(it, "analysis", "strengths") or ""
        weaknesses = safe_get(it, "analysis", "weaknesses") or ""
        content = str(it.get("content", "") or "")

        badge = score_badge_html(score)

        # Card header
        st.markdown(
            f"""
            <div class="card">
              <div class="row">
                <div>
                  <div class="title">{title}</div>
                  <div class="muted">{url}</div>
                </div>
                <div>{badge}</div>
              </div>
              <div class="hr"></div>
            """,
            unsafe_allow_html=True,
        )

        if summary:
            st.markdown(f"<div class='summary'>{summary}</div>", unsafe_allow_html=True)
        else:
            st.caption("Résumé indisponible (pas encore scoré ou analyse manquante).")

        # Actions row
        action_cols = st.columns([1.2, 1.2, 6], vertical_alignment="center")
        with action_cols[0]:
            if url:
                st.link_button("🔗 Ouvrir la source", url, use_container_width=True)
            else:
                st.button("🔗 Ouvrir la source", disabled=True, use_container_width=True)
        with action_cols[1]:
            with st.popover("ℹ️ Métadonnées", use_container_width=True):
                st.write("**ID**:", it.get("id"))
                if word_count is not None:
                    st.write("**Mots**:", word_count)
                st.write("**URL**:", url)

        # Details
        if compact_mode:
            # compact mode: keep it minimal
            st.markdown("</div>", unsafe_allow_html=True)
            continue

        with st.expander("Détails", expanded=False):
            tabs = st.tabs(["Contenu", "Forces", "Faiblesses", "Brut"])
            with tabs[0]:
                faq_id = it.get("id")

                if show_full_content:
                    st.text_area(
                        "Contenu",
                        value=content,
                        height=260,
                        key=f"content_full_{faq_id}",
                    )
                else:
                    st.text_area(
                        "Contenu (aperçu)",
                        value=short_text(content, 1400),
                        height=220,
                        key=f"content_preview_{faq_id}",
                    )
            with tabs[1]:
                st.write(strengths or "—")
            with tabs[2]:
                if show_weaknesses:
                    st.write(weaknesses or "—")
                else:
                    st.info("Affichage des faiblesses désactivé dans la sidebar.")
            with tabs[3]:
                st.json(it)

        st.markdown("</div>", unsafe_allow_html=True)