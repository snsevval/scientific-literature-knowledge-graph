"""
Verification Agent
Extraction Agent'ın çıktısını doğrular:
- Relation abstract'ta gerçekten var mı?
- Hallucination var mı?
- Entity isimleri mantıklı mı?
"""

import json
import asyncio
import ollama
from dataclasses import dataclass, field

VERIFICATION_PROMPT = """IMPORTANT: Return ONLY valid JSON. No explanation, no text, no markdown. Start with {{ and end with }}.

You are a strict scientific fact-checker. Verify if the extracted relations are supported by the abstract.

ABSTRACT:
{abstract}

EXTRACTED RELATIONS:
{relations}

For each relation, check:
1. Is the relation explicitly or implicitly mentioned in the abstract?
2. Are the entity names reasonable (not hallucinated)?
3. Is the relation type correct?

RULES:
- Be strict: if not clearly supported, mark as REJECTED
- Return ONLY valid JSON, no explanation, no markdown

OUTPUT FORMAT:
{{
  "verified": [
    {{
      "source": "entity name",
      "target": "entity name",
      "relation_type": "RELATION_TYPE",
      "verdict": "ACCEPTED",
      "reason": "brief reason"
    }}
  ],
  "rejected": [
    {{
      "source": "entity name",
      "target": "entity name",
      "relation_type": "RELATION_TYPE",
      "verdict": "REJECTED",
      "reason": "brief reason"
    }}
  ]
}}
"""

@dataclass
class VerificationResult:
    accepted_relations: list = field(default_factory=list)
    rejected_relations: list = field(default_factory=list)
    acceptance_rate: float = 0.0
    error: str = ""


async def verify_extraction(abstract: str, extraction_result) -> VerificationResult:
    """Extraction sonucunu doğrula."""

    if not extraction_result.relations:
        return VerificationResult(acceptance_rate=1.0)

    relations_text = "\n".join([
        f"- {r.source} --[{r.relation_type}]--> {r.target} (evidence: '{r.evidence[:100]}')"
        for r in extraction_result.relations
    ])

    def _call_ollama():
        response = ollama.chat(
            model="llama3.1:8b",
            messages=[{
                "role": "user",
                "content": VERIFICATION_PROMPT.format(
                    abstract=abstract[:2000],
                    relations=relations_text
                )
            }],
            options={"temperature": 0}
        )
        return response['message']['content']

    try:
        loop = asyncio.get_event_loop()
        raw = await loop.run_in_executor(None, _call_ollama)

        raw = raw.strip()
        if raw.startswith("```json"):
            raw = raw[7:]
        if raw.startswith("```"):
            raw = raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()

        data = json.loads(raw)
        accepted = data.get("verified", [])
        rejected = data.get("rejected", [])

        total = len(accepted) + len(rejected)
        rate = len(accepted) / total if total > 0 else 1.0

        return VerificationResult(
            accepted_relations=accepted,
            rejected_relations=rejected,
            acceptance_rate=rate
        )

    except Exception as e:
        return VerificationResult(
            accepted_relations=[],
            rejected_relations=[],
            acceptance_rate=1.0,
            error=str(e)
        )


def filter_by_verification(extraction_result, verification_result):
    if verification_result.error:
        return extraction_result

    accepted_set = set()
    for r in verification_result.accepted_relations:
        key = (r.get("source","").lower(), r.get("target","").lower(), r.get("relation_type",""))
        accepted_set.add(key)

    if not accepted_set:
        return extraction_result

    filtered_relations = []
    for r in extraction_result.relations:
        key = (r.source.lower(), r.target.lower(), r.relation_type)
        if key in accepted_set:
            filtered_relations.append(r)

    extraction_result.relations = filtered_relations
    return extraction_result


# TEST
if __name__ == "__main__":
    import sys, os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    from src.agents.extraction_agent import Entity, Relation, ExtractionResult

    test_abstract = """
    We report the synthesis of Al-Si nanowires using chemical vapor deposition (CVD).
    The nanowires exhibit superconductivity at temperatures below 4.2K and high electron
    mobility, making them promising candidates for quantum computing applications.
    """

    mock_extraction = ExtractionResult(
        paper_title="Test",
        entities=[
            Entity("Nanowire", "Material", 0.9),
            Entity("Superconductivity", "Property", 0.9),
            Entity("CVD", "Method", 0.9),
            Entity("Quantum Computing", "Application", 0.9),
        ],
        relations=[
            Relation("Nanowire", "Superconductivity", "HAS_PROPERTY",
                    "nanowires exhibit superconductivity", 0.9),
            Relation("Nanowire", "CVD", "SYNTHESIZED_BY",
                    "synthesis using chemical vapor deposition", 0.9),
            Relation("Nanowire", "Quantum Computing", "USED_IN",
                    "candidates for quantum computing", 0.9),
            Relation("Nanowire", "Quantum Computing", "HAS_PROPERTY",
                    "hallucinated relation", 0.5),
        ]
    )

    async def test():
        print("🔍 Verification Agent (Ollama) çalışıyor...\n")
        result = await verify_extraction(test_abstract, mock_extraction)

        print(f"✅ Kabul edilen relation'lar ({len(result.accepted_relations)}):")
        for r in result.accepted_relations:
            print(f"   {r['source']} --[{r['relation_type']}]--> {r['target']}")
            print(f"   Neden: {r['reason']}")

        print(f"\n❌ Reddedilen relation'lar ({len(result.rejected_relations)}):")
        for r in result.rejected_relations:
            print(f"   {r['source']} --[{r['relation_type']}]--> {r['target']}")
            print(f"   Neden: {r['reason']}")

        print(f"\n📊 Kabul oranı: {result.acceptance_rate:.0%}")

    asyncio.run(test())