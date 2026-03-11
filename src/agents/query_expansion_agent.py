"""
Query Expansion Agent — Materials Science Edition
Literature-app yaklaşımı: base phrase sabit, pivotları kod ekler.
LLM sadece typo düzeltir.
"""

import re
import requests
from typing import List
from dotenv import load_dotenv
import os
import asyncio

load_dotenv()

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")

# Malzeme bilimi pivotları — "synthesis" çıkarıldı (text-to-speech, image synthesis ile karışıyordu)
MATERIAL_SCIENCE_PIVOTS = [
    "superconductor",
    "nanowire",
    "material properties",
    "fabrication",
    "characterization",
    "nanostructure",
    "conductivity",
    "alloy",
    "review",
    "survey",
]

_BAD_CONTEXT_WORDS = [
    "job", "jobs", "career", "careers", "recruitment",
    "curriculum", "course", "syllabus", "program",
    "iş", "kariyer", "ilan", "müfredat", "ders",
]


def _drop_bad_context(q: str) -> bool:
    low = q.lower()
    return any(w in low for w in _BAD_CONTEXT_WORDS)


def _normalize_topic_with_llm(topic: str) -> str:
    """Ollama ile sadece typo düzelt. Erişilemezse orijinali döndür."""
    t = (topic or "").strip()
    if not t:
        return ""

    prompt = (
        "Fix typos in the topic and return ONLY the corrected short phrase, "
        "no quotes and no extra text.\n"
        f"Topic: {t}"
    )

    try:
        r = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": "llama3.1:8b", "prompt": prompt, "stream": False},
            timeout=30,
        )
        j = r.json()
        fixed = (j.get("response") or "").strip()
        fixed = re.sub(r"[\r\n]+", " ", fixed).strip().strip('"').strip("'")
        if fixed and len(fixed) < len(t) * 3:
            return fixed
        return t
    except Exception:
        return t


def expand_queries(topic: str, n: int = 8) -> List[str]:
    """Base phrase sabit kalarak n adet sorgu üretir."""
    base = _normalize_topic_with_llm(topic)
    if not base:
        return [topic]

    phrase = f'"{base}"' if " " in base else base
    fallback = [f"{phrase} {pivot}" for pivot in MATERIAL_SCIENCE_PIVOTS]

    seen, out = set(), []
    seen.add(phrase.lower())
    out.append(phrase)

    for q in fallback:
        qn = q.strip()
        if not qn or qn.lower() in seen:
            continue
        if _drop_bad_context(qn):
            continue
        seen.add(qn.lower())
        out.append(qn)
        if len(out) >= n:
            break

    return out[:n]


async def expand_query(query: str, n: int = 8) -> List[str]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, expand_queries, query, n)


if __name__ == "__main__":
    async def test():
        for q in ["superconducting nanowires", "Al-Si alloy", "grphene thin film"]:
            print(f"\nOrijinal: '{q}'")
            expanded = await expand_query(q, n=6)
            for i, eq in enumerate(expanded, 1):
                print(f"   {i}. {eq}")
    asyncio.run(test())