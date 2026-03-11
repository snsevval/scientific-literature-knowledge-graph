"""
Graph Reasoning Agent
Kullanıcının doğal dil sorusunu Cypher'a çevirir, Neo4j'i sorgular, cevaplar.
"""

import os
import asyncio
import ollama
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

CYPHER_PROMPT = """You are a Neo4j expert. Convert the natural language question to a Cypher query.

GRAPH SCHEMA:
Nodes: Material, Property, Application, Method, Element, Formula, Paper
Relationships:
  (Material)-[:HAS_PROPERTY]->(Property)
  (Material)-[:USED_IN]->(Application)
  (Material)-[:HAS_ELEMENT]->(Element)
  (Material)-[:HAS_FORMULA]->(Formula)
  (Material)-[:SYNTHESIZED_BY]->(Method)
  (Paper)-[:PAPER_MENTIONS]->(any node)

RULES:
1. Return ONLY the Cypher query, nothing else, no explanation
2. Always use LIMIT 20
3. Use case-insensitive matching with toLower() when filtering by name
4. Return meaningful node properties (n.name, n.canonical_name)

QUESTION: {question}

CYPHER:"""

ANSWER_PROMPT = """You are a material science expert analyzing knowledge graph results.

Question: {question}
Cypher Query: {cypher}
Results: {results}

Provide a clear, concise answer in 2-3 sentences based on the graph data.
If results are empty, say so clearly.
Always answer in Turkish
"""


class GraphReasoningAgent:
    def __init__(self):
        uri      = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687")
        user     = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "")
        self._driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self._driver.close()

    def _run_cypher(self, cypher: str) -> list:
        try:
            with self._driver.session() as session:
                result = session.run(cypher)
                return [dict(record) for record in result]
        except Exception as e:
            return [{"error": str(e)}]

    async def _generate_cypher(self, question: str) -> str:
        def _call():
            response = ollama.chat(
                model="llama3.1:8b",
                messages=[{"role": "user", "content": CYPHER_PROMPT.format(question=question)}],
                options={"temperature": 0}
            )
            cypher = response['message']['content'].strip()
            cypher = cypher.replace("```cypher", "").replace("```", "").strip()
            return cypher

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _call)

    async def _generate_answer(self, question: str, cypher: str, results: list) -> str:
        def _call():
            response = ollama.chat(
                model="llama3.1:8b",
                messages=[{"role": "user", "content": ANSWER_PROMPT.format(
                    question=question,
                    cypher=cypher,
                    results=str(results[:10])
                )}],
                options={"temperature": 0.3}
            )
            return response['message']['content'].strip()

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _call)

    async def ask(self, question: str) -> dict:
        print(f"\n❓ Soru: {question}")

        cypher = await self._generate_cypher(question)
        print(f"🔧 Cypher: {cypher}")

        results = self._run_cypher(cypher)
        print(f"📊 {len(results)} sonuç bulundu")

        answer = await self._generate_answer(question, cypher, results)
        print(f"💡 Cevap: {answer}")

        return {
            "question": question,
            "cypher": cypher,
            "results": results,
            "answer": answer
        }

    def query_graph(self, cypher: str) -> list:
        return self._run_cypher(cypher)


# TEST
if __name__ == "__main__":
    async def test():
        agent = GraphReasoningAgent()
        questions = [
            "Which materials have superconductivity property?",
            "What applications are materials used in?",
            "Which methods are used to synthesize materials?",
            "Hangi materyaller kuantum hesaplamada kullanılıyor?",
        ]
        print("=" * 60)
        print("🧠 Graph Reasoning Agent Test (Ollama)")
        print("=" * 60)
        for q in questions:
            result = await agent.ask(q)
            print()
        agent.close()

    asyncio.run(test())