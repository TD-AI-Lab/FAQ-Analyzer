from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Any, Optional

from openai import OpenAI

from .config import settings
from .models import CleanFAQ, Analysis, ScoredFAQ
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np

SYSTEM_PROMPT = (
    "Tu es un agent d'analyse de documentation/FAQ. "
    "Tu dois évaluer la qualité d'une page d'aide de manière neutre et reproductible. "
    "Tu ne dois JAMAIS inventer des informations absentes du texte."
)

USER_PROMPT_TEMPLATE = """
Tu es Product Manager.

Ta mission :
Évaluer l'IMPORTANCE UTILISATEUR de cette question FAQ.

⚠️ Ce n'est PAS une note de qualité rédactionnelle.

On mesure :
- Combien d’utilisateurs rencontreront ce problème
- À quel point il bloque l’usage du service
- Impact business / support
- Urgence

Score attendu :
0 = quasi inutile / rarement consulté
20 = mineur
50 = utile mais secondaire
80 = très fréquent ou critique
100 = essentiel / bloque la majorité des utilisateurs

IMPORTANT :
- Utilise toute l’échelle 0–100
- Sois très discriminant
- Évite absolument les scores moyens répétitifs
- Les scores doivent varier fortement

Réponds STRICTEMENT en JSON :
{{
  "summary": "...",
  "strengths": "...",
  "weaknesses": "...",
  "score": entier
}}

Titre: {title}

Contenu:
{content}
""".strip()

@dataclass
class AnalyzeStats:
    analyzed: int = 0
    skipped: int = 0
    errors: int = 0


class LLMAnalyzer:
    def __init__(self) -> None:
        if not settings.OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY is missing in environment.")
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)

    def analyze_one(self, faq: CleanFAQ) -> ScoredFAQ:
        prompt = f"""
        {USER_PROMPT_TEMPLATE}

        Titre: {faq.title}

        Contenu:
        {faq.content}
        """

        last_err: Optional[Exception] = None

        for attempt in range(1, settings.OPENAI_MAX_RETRIES + 1):
            try:
                resp = self.client.chat.completions.create(
                    model=settings.OPENAI_MODEL,
                    temperature=settings.OPENAI_TEMPERATURE,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                )

                text = resp.choices[0].message.content or "{}"

                obj = json.loads(text)

                for field in ("strengths", "weaknesses"):
                    if isinstance(obj.get(field), list):
                        obj[field] = "\n".join(f"- {x}" for x in obj[field])

                if "score" not in obj:
                    obj["score"] = 50

                analysis = Analysis(**obj)

                return ScoredFAQ(
                    id=faq.id,
                    url=faq.url,
                    title=faq.title,
                    content=faq.content,
                    word_count=faq.word_count,
                    analysis=analysis,
                )

            except Exception as e:
                last_err = e

                print(f"[RETRY {attempt}] id={faq.id} → {repr(e)}")

                time.sleep(min(20.0, settings.OPENAI_BACKOFF_BASE_S ** attempt))

        raise RuntimeError(f"LLM analyze failed for id={faq.id}: {last_err}")


    def analyze_many(self, faqs: list[CleanFAQ]) -> tuple[list[ScoredFAQ], AnalyzeStats]:
        stats = AnalyzeStats()
        results: list[ScoredFAQ] = []

        max_workers = min(10, len(faqs))

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {
                pool.submit(self.analyze_one, faq): faq
                for faq in faqs
            }

            for fut in as_completed(futures):
                faq = futures[fut]
                try:
                    results.append(fut.result())
                    stats.analyzed += 1
                except Exception as e:
                    print(f"[LLM ERROR] id={faq.id} → {repr(e)}")
                    stats.errors += 1

        # =====================================================
        # NORMALISATION RELATIVE
        # =====================================================

        if results:
            raw_scores = [r.analysis.score for r in results]

            order = np.argsort(np.argsort(raw_scores))

            percentiles = 100 * order / max(1, len(results) - 1)

            for r, p in zip(results, percentiles):
                r.analysis.score = int(round(p))

        return results, stats