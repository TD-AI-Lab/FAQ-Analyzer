from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .config import settings
from .models import RawFAQ


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class ScrapeStats:
    discovered: int = 0
    fetched: int = 0
    skipped: int = 0
    errors: int = 0


class WorkwaysScraper:
    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = base_url or settings.BASE_URL
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": settings.USER_AGENT})

    def _get(self, url: str) -> Optional[str]:
        last_exc: Optional[Exception] = None
        for attempt in range(1, settings.REQUEST_RETRIES + 1):
            try:
                resp = self.session.get(url, timeout=settings.REQUEST_TIMEOUT_S)
                if resp.status_code != 200:
                    last_exc = RuntimeError(f"HTTP {resp.status_code} for {url}")
                else:
                    resp.encoding = resp.encoding or "utf-8"
                    return resp.text
            except Exception as e:
                last_exc = e

            # simple backoff
            time.sleep(min(2.0, 0.4 * attempt))

        return None

    def _is_same_site(self, url: str) -> bool:
        try:
            a = urlparse(self.base_url)
            b = urlparse(url)
            return (a.scheme, a.netloc) == (b.scheme, b.netloc)
        except Exception:
            return False

    def discover_doc_links(self) -> list[str]:
        """
        Discover links from sidebar/menu of the base page.
        We keep only links that look like docs pages on the same domain.
        """
        html = self._get(self.base_url)
        if not html:
            raise RuntimeError(f"Failed to load base URL: {self.base_url}")

        soup = BeautifulSoup(html, "html.parser")

        # Heuristic: keep doc links, dedupe.
        links: set[str] = set()
        for a in soup.find_all("a", href=True):
            href = a.get("href", "").strip()
            if not href:
                continue

            abs_url = urljoin(self.base_url, href)
            if not self._is_same_site(abs_url):
                continue

            # Typical doc pattern
            path = urlparse(abs_url).path or ""
            if "/docs/" not in path:
                continue

            # Avoid anchors-only duplicates
            abs_url = abs_url.split("#", 1)[0].rstrip("/")
            links.add(abs_url)

        # Ensure base page itself is included
        links.add(self.base_url.rstrip("/"))

        return sorted(links)

    def scrape(self) -> tuple[list[RawFAQ], ScrapeStats]:
        stats = ScrapeStats()
        urls = self.discover_doc_links()
        print("Discovered URLs:", urls)
        stats.discovered = len(urls)

        items: list[RawFAQ] = []
        seen_hashes: set[str] = set()  # sécurité anti-duplication

        for url in urls:
            time.sleep(settings.REQUEST_SLEEP_S)

            html = self._get(url)
            if not html:
                stats.errors += 1
                continue

            soup = BeautifulSoup(html, "html.parser")

            # ---------------------------------------------------
            # Supprimer le layout global (menus répétés)
            # ---------------------------------------------------
            for tag in soup(["nav", "header", "footer", "aside", "script", "style"]):
                tag.decompose()

            # ---------------------------------------------------
            # Trouver le vrai contenu WordPress
            # (plusieurs fallbacks robustes)
            # ---------------------------------------------------
            main = (
                soup.select_one("main")
                or soup.select_one("article")
                or soup.select_one(".entry-content")
                or soup.select_one(".post-content")
                or soup.select_one("#content")
            )

            container = main if main else soup

            # ---------------------------------------------------
            # Extraire texte propre (PAS le HTML complet)
            # ---------------------------------------------------
            text = container.get_text(separator="\n")

            # Nettoyage léger
            lines = [line.strip() for line in text.splitlines()]
            lines = [line for line in lines if line]
            clean_text = "\n".join(lines)

            # ---------------------------------------------------
            #  4. Sécurité anti contenu identique
            # (évite 67 pages identiques sans le savoir)
            # ---------------------------------------------------
            content_hash = hashlib.sha256(clean_text.encode()).hexdigest()
            if content_hash in seen_hashes:
                print(f"[SKIP duplicate content] {url}")
                stats.skipped += 1
                continue
            seen_hashes.add(content_hash)

            # ---------------------------------------------------
            # Titre fiable
            # ---------------------------------------------------
            title = ""
            h1 = container.find("h1")
            if h1 and h1.get_text(strip=True):
                title = h1.get_text(strip=True)
            else:
                t = soup.find("title")
                if t and t.get_text(strip=True):
                    title = t.get_text(strip=True)
                else:
                    title = urlparse(url).path.strip("/").split("/")[-1] or "untitled"

            # ---------------------------------------------------
            # ID stable
            # ---------------------------------------------------
            faq_id = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]

            # ---------------------------------------------------
            # Stocker TEXTE PROPRE (pas html brut)
            # ---------------------------------------------------
            items.append(
                RawFAQ(
                    id=faq_id,
                    url=url,
                    title=title,
                    html=clean_text,  # <- IMPORTANT : texte propre seulement
                    scraped_at=utc_now(),
                )
            )

            print(f"[SCRAPED] {url} ({len(clean_text)} chars)")
            stats.fetched += 1

        print(f"Unique pages kept: {len(items)} / {len(urls)}")

        return items, stats