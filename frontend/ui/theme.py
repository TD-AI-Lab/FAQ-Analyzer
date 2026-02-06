from __future__ import annotations
import streamlit as st


def apply_theme() -> None:
    # Lightweight CSS: cards, spacing, badges, subtle typography.
    st.markdown(
        """
        <style>
          .block-container { padding-top: 1.2rem; padding-bottom: 2rem; }
          h1, h2, h3 { letter-spacing: -0.02em; }
          .muted { opacity: 0.75; }
          .card {
            border: 1px solid rgba(120,120,120,0.25);
            border-radius: 16px;
            padding: 14px 14px;
            margin-bottom: 12px;
            background: rgba(255,255,255,0.02);
          }
          .row { display:flex; align-items:center; justify-content:space-between; gap: 12px; }
          .title {
            font-size: 1.05rem;
            font-weight: 650;
            line-height: 1.25rem;
            margin: 0;
          }
          .badge {
            display:inline-block;
            padding: 4px 10px;
            border-radius: 999px;
            font-size: 0.85rem;
            border: 1px solid rgba(120,120,120,0.35);
            white-space: nowrap;
          }
          .badge-green { background: rgba(0, 200, 140, 0.12); }
          .badge-orange { background: rgba(255, 165, 0, 0.12); }
          .badge-red { background: rgba(255, 80, 80, 0.12); }
          .badge-gray { background: rgba(150, 150, 150, 0.12); }
          .summary { margin-top: 8px; font-size: 0.96rem; line-height: 1.35rem; }
          .pill {
            display:inline-block;
            padding: 2px 8px;
            border-radius: 999px;
            border: 1px solid rgba(120,120,120,0.35);
            font-size: 0.82rem;
            opacity: 0.9;
          }
          .actions a { text-decoration: none; }
          .actions { display:flex; gap: 8px; flex-wrap: wrap; }
          .hr { height: 1px; background: rgba(120,120,120,0.20); margin: 8px 0 10px 0; }
        </style>
        """,
        unsafe_allow_html=True,
    )