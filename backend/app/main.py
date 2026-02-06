from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import router
from .repository import raw_repo, clean_repo, scored_repo, utc_now
from .models import Health

from pathlib import Path

from .config import settings

def create_app() -> FastAPI:
    app = FastAPI(
        title="Workways FAQ Scorer",
        version="1.0.0",
        description="Scrape Workways documentation, clean text, analyze with LLM, expose sorted results.",
    )

    # CORS: allow frontends easily (tighten in prod if needed)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", response_model=Health)
    def health():
        counts = {
            "raw": len(raw_repo.get_items()),
            "clean": len(clean_repo.get_items()),
            "scored": len(scored_repo.get_items()),
        }
        return Health(status="ok", base_url=settings.BASE_URL, counts=counts, time_utc=utc_now())

    app.include_router(router)

    return app


app = create_app()