import os
import json
import asyncio
from dotenv import load_dotenv
from dataclasses import dataclass, field
from typing import List, Optional
import ollama

load_dotenv()

@dataclass
class Entity:
    name: str
    type: str
    confidence: float

@dataclass
class Relation:
    source: str
    target: str
    relation_type: str
    evidence: str
    confidence: float

@dataclass
class ExtractionResult:
    paper_title: str
    entities: List[Entity] = field(default_factory=list)
    relations: List[Relation] = field(default_factory=list)
    error: Optional[str] = None

EXTRACTION_PROMPT = """Return ONLY valid JSON, no explanation. Start with {{ end with }}.

Extract material science entities from this abstract.

ENTITY TYPES:
- Material: named substance/compound (e.g. "NbN", "MgB2", "Niobium"). NOT shapes/devices (not "Nanowire","Detector","Film")
- Property: measurable characteristic (e.g. "Superconductivity", "Critical temperature"). NOT vague ("good performance")
- Application: concrete use case (e.g. "Single-photon detection", "Quantum computing"). NOT general ("research")
- Method: named technique (e.g. "CVD", "Electrodeposition", "Sputtering"). NOT generic ("fabrication")
- Element: periodic table symbol only (e.g. "Nb", "Mg", "Si"). NOT full names
- Formula: exact chemical formula (e.g. "MgB2", "NbN"). NOT words ("alloy")

RELATIONS: HAS_PROPERTY, USED_IN, HAS_ELEMENT, HAS_FORMULA, SYNTHESIZED_BY

OUTPUT:
{{"entities":[{{"name":"...","type":"...","confidence":0.9}}],"relations":[{{"source":"...","target":"...","relation_type":"...","evidence":"...","confidence":0.8}}]}}

TITLE: {title}
ABSTRACT: {abstract}"""

async def extract_entities(paper_title: str, abstract: str) -> ExtractionResult:
    if not abstract or len(abstract.strip()) < 50:
        return ExtractionResult(paper_title=paper_title, error="Abstract çok kısa veya boş")

    prompt = EXTRACTION_PROMPT.format(
        title=paper_title,
        abstract=abstract[:1500]  # token taşmasını önle
    )

    def _call_ollama():
        response = ollama.chat(
            model="llama3.1:8b",
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0}
        )
        return response['message']['content']

    try:
        loop = asyncio.get_event_loop()
        raw = await loop.run_in_executor(None, _call_ollama)

        raw = raw.strip()
        if raw.startswith("```json"): raw = raw[7:]
        if raw.startswith("```"): raw = raw[3:]
        if raw.endswith("```"): raw = raw[:-3]
        raw = raw.strip()

        data = json.loads(raw)

        entities = [
            Entity(name=e["name"], type=e["type"], confidence=float(e.get("confidence", 0.7)))
            for e in data.get("entities", [])
        ]
        relations = [
            Relation(source=r["source"], target=r["target"], relation_type=r["relation_type"],
                     evidence=r.get("evidence", ""), confidence=float(r.get("confidence", 0.7)))
            for r in data.get("relations", [])
        ]

        return ExtractionResult(paper_title=paper_title, entities=entities, relations=relations)

    except json.JSONDecodeError as e:
        print(f"JSON HATA: {e}\nRAW: {raw[:200]}")
        return ExtractionResult(paper_title=paper_title, error=f"JSON parse hatası: {e}")
    except Exception as e:
        print(f"OLLAMA HATA: {e}")
        return ExtractionResult(paper_title=paper_title, error=f"Ollama hatası: {e}")

if __name__ == "__main__":
    test_abstract = """
    We report the synthesis of MgB2 superconducting nanowires using electrodeposition.
    The nanowires exhibit superconductivity at temperatures below 4.2K and high electron
    mobility, making them promising candidates for single-photon detection applications.
    """

    async def test():
        result = await extract_entities("MgB2 Superconducting Nanowires", test_abstract)
        if result.error:
            print(f"Hata: {result.error}")
            return
        print(f"ENTITIES ({len(result.entities)}):")
        for e in result.entities:
            print(f"  [{e.type:12}] {e.name}")
        print(f"RELATIONS ({len(result.relations)}):")
        for r in result.relations:
            print(f"  {r.source} --[{r.relation_type}]--> {r.target}")

    asyncio.run(test())