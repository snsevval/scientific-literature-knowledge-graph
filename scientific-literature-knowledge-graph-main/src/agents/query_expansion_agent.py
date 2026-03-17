"""
Verification Agent — Gemini
Extraction Agent'ın çıktısını doğrular.
"""

import os
import json
import asyncio
from dotenv import load_dotenv
from dataclasses import dataclass, field
import google.generativeai as genai

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-1.5-flash")

VERIFICATION_PROMPT = """Return ONLY valid JSON. No explanation, no markdown.

You are a strict scientific fact-checker. Verify if the extracted relations are supported by the abstract.

ABSTRACT:
{abstract}

EXTRACTED RELATIONS:
{relations}

For each relation check:
1. Is it explicitly or implicitly mentioned in the abstract?
2. Are entity names reasonable (not hallucinated)?
3. Is the relation type correct?

RULES:
- Be strict: if not clearly supported, mark as REJECTED
- Return ONLY valid JSON

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
    if not extraction_result.relations:
        return VerificationResult(acceptance_rate=1.0)

    relations_text = "\n".join([
        f"- {r.source} --[{r.relation_type}]--> {r.target} (evidence: '{r.evidence[:100]}')"
        for r in extraction_result.relations
    ])

    def _call_gemini():
        response = model.generate_content(
            VERIFICATION_PROMPT.format(
                abstract=abstract[:2000],
                relations=relations_text
            ),
            generation_config=genai.types.GenerationConfig(
                temperature=0,
                response_mime_type="application/json"
            )
        )
        return response.text

    try:
        loop = asyncio.get_event_loop()
        raw = await loop.run_in_executor(None, _call_gemini)

        raw = raw.strip()
        if raw.startswith("```json"): raw = raw[7:]
        if raw.startswith("```"): raw = raw[3:]
        if raw.endswith("```"): raw = raw[:-3]
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
        key = (r.get("source", "").lower(), r.get("target", "").lower(), r.get("relation_type", ""))
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