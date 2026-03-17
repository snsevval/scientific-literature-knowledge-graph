"""
ActiveScience v2 — Ana Pipeline
Retrieval → Extraction → Critical Layer → Neo4j
"""

import asyncio
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from retrieval.retrieval_manager import search_all
from agents.extraction_agent import extract_entities
from agents.verification_agent import verify_extraction, filter_by_verification
from critical_layer.schema_validator import run_critical_layer
from graph.graph_builder import GraphBuilder


async def process_paper(paper, builder: GraphBuilder) -> dict:
    """Tek bir makaleyi işle: extraction → critical layer → graph."""

    print(f"\n{'─'*60}")
    print(f"📄 {paper.title[:70]}...")
    print(f"   Kaynak: {paper.source} | Yıl: {paper.year}")

    if not paper.abstract or len(paper.abstract.strip()) < 50:
        print(f"   ⚠️  Abstract yok, atlanıyor.")
        return {"status": "skipped", "reason": "no_abstract"}

    print(f"   🤖 Extraction Agent çalışıyor...")
    extraction = await extract_entities(paper.title, paper.abstract)

    if extraction.error:
        print(f"   ❌ Extraction hatası: {extraction.error}")
        return {"status": "error", "reason": extraction.error}

    print(f"   ✅ {len(extraction.entities)} entity, {len(extraction.relations)} relation bulundu")

    print(f"   🔍 Verification Agent çalışıyor...")
    verification = await verify_extraction(paper.abstract, extraction)
    if verification.error:
        print(f"   ⚠️  Verification hatası, devam ediliyor...")
    else:
        extraction = filter_by_verification(extraction, verification)
        print(f"   ✅ Verification: %{verification.acceptance_rate:.0%} kabul")

    critical = run_critical_layer(extraction)

    if not critical.passed:
        print(f"   ❌ Critical Layer geçilemedi: {critical.errors}")
        return {"status": "failed", "reason": "critical_layer"}

    print(f"   ✅ Critical Layer: {len(critical.entities)} entity, {len(critical.relations)} relation kabul edildi")
    if critical.rejected_entities:
        print(f"   ⚠️  Reddedilen entity: {len(critical.rejected_entities)}")
    if critical.rejected_relations:
        print(f"   ⚠️  Reddedilen relation: {len(critical.rejected_relations)}")

    builder.write_paper(
        title=paper.title,
        doi=paper.doi,
        url=paper.url,
        year=paper.year
    )

    entities_n, relations_n = builder.write_validated_result(critical, paper.title)
    print(f"   📊 Neo4j'e yazıldı: {entities_n} entity, {relations_n} relation")

    return {
        "status": "success",
        "entities": entities_n,
        "relations": relations_n
    }


async def run_pipeline(query: str, max_per_source: int = 10):
    """Ana pipeline."""

    print(f"\n{'='*60}")
    print(f"🚀 ActiveScience v2 Pipeline Başlıyor")
    print(f"   Query: '{query}'")
    print(f"{'='*60}")

    builder = GraphBuilder()
    builder.create_constraints()

    # Direkt arama — expansion yok
    papers = await search_all(query, max_per_source=max_per_source)
    print(f"\n✅ Toplam {len(papers)} benzersiz makale bulundu")

    results = {"success": 0, "skipped": 0, "error": 0, "failed": 0}
    total_entities = 0
    total_relations = 0

    for i, paper in enumerate(papers, 1):
        print(f"\n[{i}/{len(papers)}]", end="")
        result = await process_paper(paper, builder)

        status = result.get("status", "error")
        results[status] = results.get(status, 0) + 1

        if status == "success":
            total_entities += result.get("entities", 0)
            total_relations += result.get("relations", 0)

        await asyncio.sleep(1)

    print(f"\n{'='*60}")
    print(f"🏁 Pipeline Tamamlandı!")
    print(f"{'='*60}")
    print(f"   Makale sayısı  : {len(papers)}")
    print(f"   Başarılı       : {results['success']}")
    print(f"   Atlanan        : {results['skipped']}")
    print(f"   Hatalı         : {results['error'] + results['failed']}")
    print(f"   Toplam entity  : {total_entities}")
    print(f"   Toplam relation: {total_relations}")

    stats = builder.get_stats()
    print(f"\n📈 Knowledge Graph:")
    for k, v in stats.items():
        if v > 0:
            print(f"   {k:12}: {v}")

    builder.close()
    print(f"\n✅ Tamamlandı! Neo4j Browser'da görüntülemek için:")
    print(f"   http://localhost:7474")
    print(f"   Cypher: MATCH (n)-[r]->(m) RETURN n,r,m LIMIT 100")


if __name__ == "__main__":
    QUERY = "superconducting nanowires quantum computing"
    MAX_PER_SOURCE = 10

    asyncio.run(run_pipeline(QUERY, MAX_PER_SOURCE))