from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import os
from dotenv import load_dotenv

# ✅ Always load backend/.env from the config module itself
BASE_DIR = Path(__file__).resolve().parent.parent  # backend/
load_dotenv(BASE_DIR / ".env")

def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default)

@dataclass(frozen=True)
class Settings:
    BASE_URL: str = field(default_factory=lambda: _env("WORKWAYS_BASE_URL", "https://support.workways.com/docs/presentation/"))

    DATA_DIR: Path = field(default_factory=lambda: Path(_env("DATA_DIR", "data")))
    RAW_PATH: Path = field(init=False)
    CLEAN_PATH: Path = field(init=False)
    SCORED_PATH: Path = field(init=False)

    USER_AGENT: str = field(default_factory=lambda: _env("USER_AGENT", "WorkwaysFAQScorer/1.0 python-requests"))

    REQUEST_TIMEOUT_S: float = field(default_factory=lambda: float(_env("REQUEST_TIMEOUT_S", "15")))
    REQUEST_RETRIES: int = field(default_factory=lambda: int(_env("REQUEST_RETRIES", "3")))
    REQUEST_SLEEP_S: float = field(default_factory=lambda: float(_env("REQUEST_SLEEP_S", "0.35")))

    MIN_WORDS: int = field(default_factory=lambda: int(_env("MIN_WORDS", "30")))
    MAX_CHARS_FOR_LLM: int = field(default_factory=lambda: int(_env("MAX_CHARS_FOR_LLM", "16000")))

    # ✅ This one was the issue: must not be evaluated at import-time
    OPENAI_API_KEY: str = field(default_factory=lambda: _env("OPENAI_API_KEY", ""))
    OPENAI_MODEL: str = field(default_factory=lambda: _env("OPENAI_MODEL", "gpt-4o-mini"))
    OPENAI_TEMPERATURE: float = field(default_factory=lambda: float(_env("OPENAI_TEMPERATURE", "0")))

    OPENAI_MAX_RETRIES: int = field(default_factory=lambda: int(_env("OPENAI_MAX_RETRIES", "3")))
    OPENAI_BACKOFF_BASE_S: float = field(default_factory=lambda: float(_env("OPENAI_BACKOFF_BASE_S", "1.5")))

    FILE_LOCK_TIMEOUT_S: float = field(default_factory=lambda: float(_env("FILE_LOCK_TIMEOUT_S", "10")))

    def __post_init__(self) -> None:
        object.__setattr__(self, "RAW_PATH", self.DATA_DIR / "faq_raw.json")
        object.__setattr__(self, "CLEAN_PATH", self.DATA_DIR / "faq_clean.json")
        object.__setattr__(self, "SCORED_PATH", self.DATA_DIR / "faq_scored.json")


settings = Settings()
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)