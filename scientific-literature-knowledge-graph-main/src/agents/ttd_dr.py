"""
TTD-DR — Test-Time Diffusion Deep Researcher
ActiveScience v2 için claim doğrulama modülü.

Çalışma mantığı:
1. LLM'den gelen claim alınır
2. Textbook KB'den ilgili evidence çekilir
3. Ollama ile claim vs evidence karşılaştırılır
4. Karar: Supported / Contradicted / Insufficient
"""

import asyncio
import ollama
from dataclasses import dataclass, field
from typing import List, Optional
import sys, os

sys.path.append(os.path.dirname(__file__))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'critical_layer'))

try:
    from textbook_kb import TextbookKB
    _kb = TextbookKB()
    _KB_AVAILABLE = True
except Exception as e:
    print(f"⚠️  TextbookKB yüklenemedi: {e}")
    _KB_AVAILABLE = False

# ─── Sabitler ────────────────────────────────────────────────────────────────

VERDICT_SUPPORTED    = "supported"
VERDICT_CONTRADICTED = "contradicted"
VERDICT_INSUFFICIENT = "insufficient"

TTD_DR_PROMPT = """You are a scientific fact-checker. Given a scientific claim and textbook evidence, decide if the claim is correct.

CLAIM: {claim}

TEXTBOOK EVIDENCE:
{evidence}

Answer with ONLY one of these verdicts and a brief reason:
- SUPPORTED: claim is consistent with evidence
- CONTRADICTED: claim contradicts evidence
- INSUFFICIENT: evidence is not relevant enough to judge

Format:
VERDICT: <SUPPORTED|CONTRADICTED|INSUFFICIENT>
REASON: <one sentence>"""

# ─── Veri sınıfları ──────────────────────────────────────────────────────────

@dataclass
class TTDResult:
    claim: str
    verdict: str              # supported / contradicted / insufficient
    reason: str
    evidence: List[str] = field(default_factory=list)
    source: str = ""          # hangi kitaptan geldi
    error: Optional[str] = None

# ─── Ana fonksiyon ───────────────────────────────────────────────────────────

async def verify_claim(claim: str) -> TTDResult:
    """
    Bir claim'i textbook KB + Ollama ile doğrula.
    
    Args:
        claim: Doğrulanacak bilimsel iddia
               Örn: "MgB2 has superconductivity at 300K"
    
    Returns:
        TTDResult: verdict + reason + evidence
    """
    if not _KB_AVAILABLE:
        return TTDResult(
            claim=claim,
            verdict=VERDICT_INSUFFICIENT,
            reason="Textbook KB yüklenemedi",
            error="KB not available"
        )

    # 1. Textbook KB'den evidence çek
    try:
        kb_results = _kb.search(claim, top_k=3)
    except Exception as e:
        return TTDResult(
            claim=claim,
            verdict=VERDICT_INSUFFICIENT,
            reason="KB arama hatası",
            error=str(e)
        )

    if not kb_results:
        return TTDResult(
            claim=claim,
            verdict=VERDICT_INSUFFICIENT,
            reason="Textbook'ta ilgili bilgi bulunamadı"
        )

    # En iyi evidence'ları al
    evidence_texts = [r.chunk.text[:300] for r in kb_results[:3]]
    sources = [f"{r.chunk.source} (L{r.chunk.year_level})" for r in kb_results[:3]]
    evidence_str = "\n\n".join([f"[{sources[i]}]\n{t}" for i, t in enumerate(evidence_texts)])

    # 2. Ollama ile karşılaştır
    prompt = TTD_DR_PROMPT.format(
        claim=claim,
        evidence=evidence_str
    )

    def _call_ollama():
        response = ollama.chat(
            model="llama3.1:8b",
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0, "num_predict": 256}
        )
        return response['message']['content']

    try:
        loop = asyncio.get_event_loop()
        raw = await loop.run_in_executor(None, _call_ollama)

        # Parse verdict
        verdict = VERDICT_INSUFFICIENT
        reason = ""

        for line in raw.strip().split("\n"):
            line = line.strip()
            if line.startswith("VERDICT:"):
                v = line.replace("VERDICT:", "").strip().lower()
                if "supported" in v:
                    verdict = VERDICT_SUPPORTED
                elif "contradicted" in v:
                    verdict = VERDICT_CONTRADICTED
                else:
                    verdict = VERDICT_INSUFFICIENT
            elif line.startswith("REASON:"):
                reason = line.replace("REASON:", "").strip()

        return TTDResult(
            claim=claim,
            verdict=verdict,
            reason=reason,
            evidence=evidence_texts,
            source=sources[0] if sources else ""
        )

    except Exception as e:
        return TTDResult(
            claim=claim,
            verdict=VERDICT_INSUFFICIENT,
            reason="Ollama hatası",
            error=str(e)
        )


async def verify_relations(relations) -> List[TTDResult]:
    """
    Bir makalenin relation listesini toplu doğrula.
    HAS_PROPERTY, SYNTHESIZED_BY, USED_IN relation'larını kontrol eder.
    """
    results = []
    for r in relations:
        claim = None

        if r.relation_type == "HAS_PROPERTY":
            claim = f"{r.source} has property {r.target}"

        elif r.relation_type == "SYNTHESIZED_BY":
            claim = f"{r.target} is a synthesis or fabrication method for {r.source}"

        elif r.relation_type == "USED_IN":
            claim = f"{r.source} is used in {r.target}"

        if claim:
            result = await verify_claim(claim)
            results.append(result)
            await asyncio.sleep(0.2)  # Ollama'ya nefes aldır

    return results


# ─── TEST ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    test_claims = [
        "MgB2 has superconductivity at 300K",           # yanlış — 39K'de
        "Silicon is a semiconductor",                    # doğru
        "Aluminum melts at 660 degrees Celsius",         # doğru
        "NbN has superconductivity",                     # doğru
        "Steel melts at 200 degrees Celsius",            # yanlış — ~1400°C
    ]

    async def test():
        print("=" * 60)
        print("TTD-DR Claim Verification Test")
        print("=" * 60)

        for claim in test_claims:
            print(f"\n🔍 Claim: {claim}")
            result = await verify_claim(claim)

            icon = "✅" if result.verdict == VERDICT_SUPPORTED else \
                   "❌" if result.verdict == VERDICT_CONTRADICTED else "⚠️"

            print(f"   {icon} Verdict: {result.verdict.upper()}")
            print(f"   Reason: {result.reason}")
            if result.source:
                print(f"   Source: {result.source}")
            if result.error:
                print(f"   Error: {result.error}")

    asyncio.run(test())