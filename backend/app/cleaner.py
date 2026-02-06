from __future__ import annotations

import re
from bs4 import BeautifulSoup

from .config import settings
from .models import RawFAQ, CleanFAQ


def normalize_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # collapse spaces
    text = re.sub(r"[ \t]+", " ", text)
    # collapse too many blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def truncate_smart(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    # Keep head + tail (more robust than only head)
    head_len = int(max_chars * 0.7)
    tail_len = max_chars - head_len - len("\n...\n")
    head = text[:head_len].rstrip()
    tail = text[-tail_len:].lstrip()
    return f"{head}\n...\n{tail}"


class WorkwaysCleaner:
    def clean_one(self, raw: RawFAQ) -> CleanFAQ | None:
        soup = BeautifulSoup(raw.html, "html.parser")

        # Remove non-content elements
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()

        # Remove nav-ish / table of contents blocks by heuristics
        # (We avoid relying on exact classes; we remove elements containing typical ToC labels)
        toc_candidates = soup.find_all(string=re.compile(r"Table Of Contents|Sommaire|Table des matières", re.I))
        for s in toc_candidates:
            parent = getattr(s, "parent", None)
            if parent and parent.name:
                # remove nearest container
                container = parent
                for _ in range(3):
                    if container.parent is None:
                        break
                    container = container.parent
                try:
                    container.decompose()
                except Exception:
                    pass

        # Extract main-ish content: fallback to full body text
        main = soup.find("main") or soup.find("article") or soup.body or soup

        text = main.get_text("\n", strip=True)
        text = normalize_whitespace(text)

        # Remove obvious sidebar remnants if present
        # (sometimes menu text leaks; we kill lines that are too short and repeated)
        lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
        # De-dup consecutive duplicates
        deduped: list[str] = []
        prev = None
        for ln in lines:
            if ln == prev:
                continue
            deduped.append(ln)
            prev = ln
        text = "\n".join(deduped).strip()

        # Truncate for LLM safety
        text = truncate_smart(text, settings.MAX_CHARS_FOR_LLM)

        # Word count
        words = re.findall(r"\w+", text, flags=re.UNICODE)
        wc = len(words)

        if wc < settings.MIN_WORDS:
            return None

        return CleanFAQ(
            id=raw.id,
            url=raw.url,
            title=raw.title,
            content=text,
            word_count=wc,
        )

    def clean_many(self, raws: list[RawFAQ]) -> list[CleanFAQ]:
        out: list[CleanFAQ] = []
        for r in raws:
            c = self.clean_one(r)
            if c:
                out.append(c)
        return out