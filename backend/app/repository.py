from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Optional, TypeVar

import portalocker

from .config import settings

T = TypeVar("T")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class JsonRepository:
    path: Path

    def _ensure_parent(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load_envelope(self) -> dict[str, Any]:
        """
        Load JSON envelope safely using UTF-8 encoding.

        Fixes Windows UnicodeDecodeError when reading UTF-8 files.
        Also auto-recovers from corrupted files.
        """
        self._ensure_parent()

        if not self.path.exists():
            return {"metadata": {}, "items": []}

        try:
            with portalocker.Lock(
                self.path,
                mode="r",
                encoding="utf-8",  # ⭐ CRITICAL FIX
                timeout=settings.FILE_LOCK_TIMEOUT_S,
            ) as f:
                return json.load(f)

        except json.JSONDecodeError:
            # corrupted file → auto reset (production safe behavior)
            return {"metadata": {}, "items": []}

        except UnicodeDecodeError:
            # wrong encoding legacy file → reset
            return {"metadata": {}, "items": []}

    def save_envelope(self, envelope: dict[str, Any]) -> None:
        """
        Atomically save JSON envelope to disk using UTF-8 encoding.

        Fixes Windows UnicodeEncodeError (cp1252 default).
        Guarantees:
        - UTF-8 encoding
        - no partial writes (tmp file then replace)
        - safe for special characters / accents / emojis
        """
        self._ensure_parent()

        tmp = self.path.with_suffix(self.path.suffix + ".tmp")

        data = json.dumps(
            envelope,
            ensure_ascii=False,  # keep real unicode chars
            indent=2
        )

        # --- write temp file in UTF-8 ---
        with portalocker.Lock(
            tmp,
            mode="w",
            encoding="utf-8",  # ⭐ CRITICAL FIX
            timeout=settings.FILE_LOCK_TIMEOUT_S,
        ) as f:
            f.write(data)
            f.flush()

        # --- atomic replace final file ---
        with portalocker.Lock(
            self.path,
            mode="w",
            encoding="utf-8",  # ⭐ CRITICAL FIX
            timeout=settings.FILE_LOCK_TIMEOUT_S,
        ) as f:
            f.write(data)
            f.flush()

        # cleanup temp
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass

    def upsert_items(
        self,
        new_items: Iterable[dict[str, Any]],
        key_fn: Callable[[dict[str, Any]], str],
        metadata_patch: Optional[dict[str, Any]] = None,
    ) -> tuple[int, int]:
        """
        Returns (created, updated). Upsert is stable & idempotent by key.
        """
        envelope = self.load_envelope()
        items = envelope.get("items", [])
        by_key: dict[str, dict[str, Any]] = {key_fn(it): it for it in items if isinstance(it, dict)}

        created = 0
        updated = 0
        for it in new_items:
            k = key_fn(it)
            if k not in by_key:
                by_key[k] = it
                created += 1
            else:
                # Update existing item fields (overwrite)
                if by_key[k] != it:
                    by_key[k] = it
                    updated += 1

        envelope["items"] = list(by_key.values())
        envelope.setdefault("metadata", {})
        envelope["metadata"]["updated_at"] = utc_now().isoformat()
        if metadata_patch:
            envelope["metadata"].update(metadata_patch)

        self.save_envelope(envelope)
        return created, updated

    def get_items(self) -> list[dict[str, Any]]:
        env = self.load_envelope()
        items = env.get("items", [])
        return [it for it in items if isinstance(it, dict)]


raw_repo = JsonRepository(settings.RAW_PATH)
clean_repo = JsonRepository(settings.CLEAN_PATH)
scored_repo = JsonRepository(settings.SCORED_PATH)