from __future__ import annotations

from datetime import datetime
from typing import Any, Optional, Literal
from pydantic import BaseModel, Field, HttpUrl, ConfigDict


class RawFAQ(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    url: HttpUrl
    title: str
    html: str
    scraped_at: datetime


class CleanFAQ(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    url: HttpUrl
    title: str
    content: str
    word_count: int


class Analysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(..., min_length=1)
    strengths: str = Field(..., min_length=1)
    weaknesses: str = Field(..., min_length=1)
    score: int = Field(..., ge=0, le=100)


class ScoredFAQ(CleanFAQ):
    model_config = ConfigDict(extra="forbid")

    analysis: Analysis


class Envelope(BaseModel):
    """
    Generic container on disk:
    {
      "metadata": {...},
      "items": [...]
    }
    """
    model_config = ConfigDict(extra="forbid")

    metadata: dict[str, Any] = Field(default_factory=dict)
    items: list[Any] = Field(default_factory=list)


class Health(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"]
    base_url: str
    counts: dict[str, int]
    time_utc: datetime


class RunResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: int = 0


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: str
    details: Optional[Any] = None