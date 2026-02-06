from __future__ import annotations

import streamlit as st
from typing import Any

from .api_client import ApiClient


@st.cache_data(ttl=60, show_spinner=False)
def fetch_health_cached(client: ApiClient) -> dict[str, Any]:
    return client.health()


@st.cache_data(ttl=60, show_spinner=False)
def fetch_faq_cached(client: ApiClient, sort: str | None = None) -> dict[str, Any]:
    return client.faq(sort=sort)


def clear_all_caches() -> None:
    try:
        fetch_health_cached.clear()
    except Exception:
        pass
    try:
        fetch_faq_cached.clear()
    except Exception:
        pass