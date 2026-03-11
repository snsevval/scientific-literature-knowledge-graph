"""
GRAPH BUILDER — Saf Python kodu, LLM yok!
Critical Layer'dan geçen doğrulanmış veriyi Neo4j'e yazar.
"""

import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

class GraphBuilder:
    def __init__(self):
        uri      = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687")
        user     = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "")
        
        self._driver = GraphDatabase.driver(uri, auth=(user, password))
        
        try:
            self._driver.verify_connectivity()
            print("✅ Neo4j bağlantısı başarılı!")
        except Exception as e:
            raise Exception(f"Neo4j bağlantı hatası: {e}")

    def close(self):
        self._driver.close()

    def create_constraints(self):
        """Unique constraint'leri oluştur — duplicate engelle."""
        constraints = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Material)    REQUIRE n.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Property)    REQUIRE n.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Application) REQUIRE n.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Method)      REQUIRE n.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Element)     REQUIRE n.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Formula)     REQUIRE n.name IS UNIQUE",
        ]
        with self._driver.session() as session:
            for c in constraints:
                try:
                    session.run(c)
                except Exception as e:
                    print(f"  ⚠️  Constraint: {e}")
        print("✅ Constraint'ler hazır!")

    def write_paper(self, title: str, doi: str = "", url: str = "", year: int = 0):
        """Paper node yaz."""
        cypher = """
        MERGE (p:Paper {title: $title})
        SET p.doi  = $doi,
            p.url  = $url,
            p.year = $year
        RETURN p
        """
        with self._driver.session() as session:
            session.run(cypher, title=title, doi=doi, url=url, year=year)

    def write_validated_result(self, critical_result, paper_title: str):
        """
        Critical Layer sonucunu Neo4j'e yaz.
        Tamamen parametreli Cypher — injection riski yok.
        """
        written_entities  = 0
        written_relations = 0

        with self._driver.session() as session:

            # 1) Entity'leri yaz
            for e in critical_result.entities:
                cypher = f"""
                MERGE (n:{e.type} {{name: $name}})
                SET n.canonical_name = $canonical,
                    n.confidence      = $confidence
                """
                session.run(cypher,
                    name=e.name,
                    canonical=e.canonical_name,
                    confidence=e.confidence
                )
                written_entities += 1

            # 2) Paper → entity ilişkisi
            for e in critical_result.entities:
                cypher = f"""
                MATCH (p:Paper {{title: $paper_title}})
                MATCH (n:{e.type} {{name: $entity_name}})
                MERGE (p)-[:PAPER_MENTIONS]->(n)
                """
                session.run(cypher,
                    paper_title=paper_title,
                    entity_name=e.name
                )

            # 3) Relation'ları yaz
            for r in critical_result.relations:
                # Source ve target'ın tipini bul
                source_type = next(
                    (e.type for e in critical_result.entities if e.canonical_name == r.source),
                    None
                )
                target_type = next(
                    (e.type for e in critical_result.entities if e.canonical_name == r.target),
                    None
                )
                if not source_type or not target_type:
                    continue

                cypher = f"""
                MATCH (s:{source_type} {{canonical_name: $source}})
                MATCH (t:{target_type} {{canonical_name: $target}})
                MERGE (s)-[r:{r.relation_type}]->(t)
                SET r.evidence   = $evidence,
                    r.confidence = $confidence
                """
                session.run(cypher,
                    source=r.source,
                    target=r.target,
                    evidence=r.evidence,
                    confidence=r.confidence
                )
                written_relations += 1

        return written_entities, written_relations

    def query_graph(self, cypher: str) -> list:
        """Graph'ı sorgula, sonuçları döndür."""
        with self._driver.session() as session:
            result = session.run(cypher)
            return [dict(record) for record in result]

    def get_stats(self) -> dict:
        """Graph istatistikleri."""
        with self._driver.session() as session:
            counts = {}
            for label in ["Material","Property","Application","Method","Element","Formula","Paper"]:
                r = session.run(f"MATCH (n:{label}) RETURN count(n) as c")
                counts[label] = r.single()["c"]
            
            rel = session.run("MATCH ()-[r]->() RETURN count(r) as c")
            counts["Relations"] = rel.single()["c"]
        return counts


# ─── TEST ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys, os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

    from src.agents.extraction_agent import Entity, Relation, ExtractionResult
    from src.critical_layer.schema_validator import run_critical_layer, ValidatedEntity, ValidatedRelation, CriticalLayerResult

    # Mock critical layer sonucu
    mock_critical = CriticalLayerResult(passed=True)
    mock_critical.entities = [
        ValidatedEntity("Nanowire",          "Material",    0.9, "Nanowire"),
        ValidatedEntity("Superconductivity", "Property",    0.9, "Superconductivity"),
        ValidatedEntity("Quantum Computing", "Application", 0.9, "Quantum Computing"),
        ValidatedEntity("CVD",               "Method",      0.9, "CVD"),
        ValidatedEntity("Al",                "Element",     0.9, "Al"),
        ValidatedEntity("Al-Si",             "Formula",     0.9, "Al-Si"),
    ]
    mock_critical.relations = [
        ValidatedRelation("Nanowire","Superconductivity","HAS_PROPERTY","exhibits superconductivity",0.9),
        ValidatedRelation("Nanowire","Quantum Computing","USED_IN","quantum computing applications",0.9),
        ValidatedRelation("Nanowire","CVD","SYNTHESIZED_BY","synthesized using CVD",0.9),
        ValidatedRelation("Nanowire","Al","HAS_ELEMENT","aluminum composition",0.9),
        ValidatedRelation("Nanowire","Al-Si","HAS_FORMULA","Al-Si nanowires",0.9),
    ]

    # Graph Builder başlat
    builder = GraphBuilder()
    builder.create_constraints()

    # Paper yaz
    builder.write_paper(
        title="Al-Si Nanowire Superconductivity Test",
        doi="test/001",
        url="https://arxiv.org/test",
        year=2024
    )

    # Validated veriyi yaz
    entities_n, relations_n = builder.write_validated_result(
        mock_critical,
        "Al-Si Nanowire Superconductivity Test"
    )

    print(f"\n📊 Neo4j'e yazıldı:")
    print(f"   Entity   : {entities_n}")
    print(f"   Relation : {relations_n}")

    # İstatistik
    stats = builder.get_stats()
    print(f"\n📈 Graph istatistikleri:")
    for k, v in stats.items():
        print(f"   {k:12}: {v}")

    builder.close()  