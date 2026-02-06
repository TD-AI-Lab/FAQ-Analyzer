from __future__ import annotations

from fastapi import APIRouter, HTTPException
from typing import Optional

from .models import RunResult
from .repository import raw_repo, clean_repo, scored_repo, utc_now
from .scraper import WorkwaysScraper
from .cleaner import WorkwaysCleaner
from .analyzer import LLMAnalyzer

router = APIRouter()


@router.get("/faq")
def get_faq(sort: Optional[str] = None):
    items = scored_repo.get_items()
    # If not scored yet, fall back to clean, then raw
    if not items:
        items = clean_repo.get_items()
    if not items:
        items = raw_repo.get_items()

    if sort == "score":
        # only if scored
        def score_of(it: dict) -> int:
            try:
                return int(it.get("analysis", {}).get("score", 0))
            except Exception:
                return 0
        items.sort(key=score_of, reverse=True)

    return {"items": items, "count": len(items), "time_utc": utc_now().isoformat()}


@router.get("/faq/{faq_id}")
def get_faq_by_id(faq_id: str):
    for repo in (scored_repo, clean_repo, raw_repo):
        items = repo.get_items()
        for it in items:
            if it.get("id") == faq_id:
                return it
    raise HTTPException(status_code=404, detail="FAQ not found")


@router.post("/scrape", response_model=RunResult)
def run_scrape():
    scraper = WorkwaysScraper()
    raws, stats = scraper.scrape()
    created, updated = raw_repo.upsert_items(
        [r.model_dump(mode="json") for r in raws],
        key_fn=lambda it: str(it["id"]),
        metadata_patch={"last_scrape_at": utc_now().isoformat(), "base_url": scraper.base_url},
    )
    return RunResult(
        message="Scrape completed",
        created=created,
        updated=updated,
        skipped=stats.skipped,
        errors=stats.errors,
    )


@router.post("/clean", response_model=RunResult)
def run_clean():
    raw_items = raw_repo.get_items()
    if not raw_items:
        raise HTTPException(status_code=400, detail="No raw data found. Run /scrape first.")

    # Build map to keep idempotence: if already clean exists, skip unless raw changed.
    existing_clean = {it["id"]: it for it in clean_repo.get_items()}

    cleaner = WorkwaysCleaner()
    created = updated = skipped = errors = 0

    to_upsert = []
    for it in raw_items:
        faq_id = it.get("id")
        try:
            # If already cleaned and raw html unchanged? We don't store raw hash in clean to keep it simple.
            # We'll re-clean only if missing.
            if faq_id in existing_clean:
                skipped += 1
                continue

            from .models import RawFAQ
            raw = RawFAQ(**it)
            c = cleaner.clean_one(raw)
            if not c:
                skipped += 1
                continue
            to_upsert.append(c.model_dump(mode="json"))
        except Exception:
            errors += 1

    if to_upsert:
        c_created, c_updated = clean_repo.upsert_items(
            to_upsert,
            key_fn=lambda x: str(x["id"]),
            metadata_patch={"last_clean_at": utc_now().isoformat()},
        )
        created += c_created
        updated += c_updated

    return RunResult(
        message="Clean completed",
        created=created,
        updated=updated,
        skipped=skipped,
        errors=errors,
    )


@router.post("/analyze", response_model=RunResult)
def run_analyze(force: bool = False):
    clean_items = clean_repo.get_items()
    if not clean_items:
        raise HTTPException(status_code=400, detail="No clean data found. Run /clean first.")

    existing_scored = {it["id"]: it for it in scored_repo.get_items()}

    analyzer = LLMAnalyzer()

    created = updated = skipped = errors = 0

    from .models import CleanFAQ

    # ==========================================
    # Build list to analyze
    # ==========================================
    to_analyze: list[CleanFAQ] = []

    for it in clean_items:
        faq_id = it.get("id")

        if (faq_id in existing_scored) and not force:
            skipped += 1
            continue

        to_analyze.append(CleanFAQ(**it))


    if not to_analyze:
        return RunResult(
            message="Nothing to analyze",
            created=0,
            updated=0,
            skipped=skipped,
            errors=0,
        )


    # ==========================================
    # ⭐ Parallel LLM analysis
    # ==========================================
    scored_items, stats = analyzer.analyze_many(to_analyze)

    to_upsert = [item.model_dump(mode="json") for item in scored_items]

    errors += stats.errors


    # ==========================================
    # Upsert
    # ==========================================
    if to_upsert:
        s_created, s_updated = scored_repo.upsert_items(
            to_upsert,
            key_fn=lambda x: str(x["id"]),
            metadata_patch={"last_analyze_at": utc_now().isoformat()},
        )
        created += s_created
        updated += s_updated


    return RunResult(
        message="Analyze completed",
        created=created,
        updated=updated,
        skipped=skipped,
        errors=errors,
    )