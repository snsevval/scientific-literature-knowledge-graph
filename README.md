# Minerva

**A Verified Multi-Agent Knowledge Graph System for Materials Science**

Minerva is a multi-agent pipeline that extracts, verifies, and stores structured materials science knowledge from scientific literature in a Neo4j graph database. It applies three sequential verification layers before writing any claim to the graph: a deterministic Critic Layer, a semantic Verification Agent, and TTD-DR — a novel module that cross-references every extracted claim against a FAISS-indexed corpus of 29,545 chunks from nine materials science textbooks. At query time, a GraphRAG pipeline combines Cypher retrieval over Neo4j with textbook semantic search.

Documentation: [snsevval.github.io/scientific-literature-knowledge-graph](https://snsevval.github.io/scientific-literature-knowledge-graph)

Paper: [Minerva: A Verified Multi-Agent Knowledge Graph System for Materials Science](rapor.pdf)

---

## Quick Start

### 1. Clone

```bash
git clone https://github.com/snsevval/scientific-literature-knowledge-graph
cd scientific-literature-knowledge-graph
```

### 2. Install dependencies

```bash
pip install openai neo4j faiss-cpu sentence-transformers \
            fastapi uvicorn python-dotenv httpx pymupdf pypdf
```

### 3. Configure environment

```bash
# .env
OPENAI_API_KEY=sk-...
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password
```

### 4. Set up Neo4j

```bash
docker run --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/your_password \
  neo4j:5
```

### 5. Place textbook PDFs

Place PDF textbooks in `data/year1_temel/` through `data/year4_uzman/` according to difficulty level. The FAISS index builds automatically on first startup.

### 6. Start the API

```bash
uvicorn main:app --reload
```

On first launch the TextbookKB index is built (~2-5 min). Subsequent starts load the cached index instantly.

---

## Configuration

| Variable | Description | Default |
|---|---|---|
| `OPENAI_API_KEY` | Required. OpenAI API key for extraction, TTD-DR, and GraphRAG. | — |
| `NEO4J_URI` | Neo4j connection URI. | `bolt://localhost:7687` |
| `NEO4J_USER` | Neo4j username. | `neo4j` |
| `NEO4J_PASSWORD` | Neo4j password. | — |
| `UNPAYWALL_EMAIL` | Email for Unpaywall API (PDF enrichment). | — |
| `GROQ_API_KEY` | Optional. Groq API key for benchmark comparison. | — |
| `CEREBRAS_API_KEY` | Optional. Cerebras API key for benchmark comparison. | — |

---

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/search/start` | POST | Start ingestion pipeline. Body: `{"query": "...", "max_per_source": 10}`. Returns `job_id`. |
| `/search/progress/{job_id}` | GET | Poll pipeline progress, per-paper status, entity and relation counts. |
| `/graph/ask` | POST | GraphRAG question answering. Body: `{"question": "..."}`. |
| `/graph/stats` | GET | Neo4j node and relation counts by type. |
| `/graph/nodes` | GET | List up to 200 nodes. |

---

## How It Works

**Ingestion pipeline:**

Papers are fetched from arXiv, OpenAlex, and CrossRef in parallel. Each paper passes through six stages: retrieval, entity/relation extraction (GPT-4o-mini), semantic verification, Critic Layer (7 deterministic rules, zero API calls), TTD-DR claim verification against TextbookKB, and Neo4j write. Only claims that are textbook-supported enter the graph.

**Query pipeline:**

A natural language question is converted to Cypher by GPT-4o, executed against Neo4j, and augmented in parallel with FAISS semantic search over TextbookKB. GPT-4o-mini synthesizes the final answer from graph results and textbook context.

---

## Benchmark

We evaluate Minerva on a 200-question fill-in-the-blank evaluation set constructed from four materials science textbooks (Callister, Shackelford, Kittel, Cengel), spanning 10 domains and four difficulty levels.

| Model | Accuracy | Avg / 3 |
|---|---|---|
| **Minerva** | **83.3%** | **2.500** |
| Llama-3.3-70B (Groq) | 80.7% | 2.420 |
| GPT-4o-mini (baseline) | 75.2% | 2.255 |
| GPT-3.5-turbo | 73.7% | 2.210 |
| ActiveScience | 73.5% | 2.205 |
| Qwen-3-235B (Cerebras) | 72.2% | 2.165 |
| Llama-3.1-8B (Groq) | 67.5% | 2.025 |
| Llama-3.1-8B (Cerebras) | 66.8% | 2.005 |

Minerva's advantage grows with question difficulty. On hard questions it leads GPT-4o-mini by +0.67; on expert questions by +0.56 on the 0-3 scale. The benchmark dataset is available in `benchmark_fillblank_200.json`.

To run the benchmark:

```bash
# All 8 models, 200 questions
python eval_fillblank.py --models all --limit 0 --out results.json

# Minerva only, quick test
python eval_fillblank.py --models v2 --limit 20 --out test.json
```

---

## Project Structure

```
scientific-literature-knowledge-graph/
├── main.py                          # FastAPI entry point
├── eval_fillblank.py                # Benchmark evaluator
├── benchmark_fillblank_200.json     # 200-question benchmark dataset
├── agents/
│   ├── extraction_agent.py          # GPT-4o-mini entity/relation extraction
│   ├── verification_agent.py        # Semantic relation verifier
│   ├── ttd_dr.py                    # TTD-DR claim verification
│   ├── graph_reasoning_agent.py     # GraphRAG query pipeline
│   ├── textbook_kb.py               # FAISS TextbookKB
│   └── schema_validator.py          # 7-rule Critic Layer
├── critical_layer/
│   ├── textbook_kb.py
│   └── schema_validator.py
├── graph/
│   └── graph_builder.py             # Neo4j write layer
├── retrieval/
│   ├── retrieval_manager.py         # Multi-source search + Unpaywall
│   ├── arxiv_source.py
│   ├── openalex_source.py
│   └── crossref_source.py
└── data/
    ├── year1_temel/                  # Introductory textbook PDFs
    ├── year2_orta/
    ├── year3_ileri/
    ├── year4_uzman/
    └── textbook_index/
        ├── textbook.index            # FAISS binary index
        └── chunks.json              # Chunk metadata
```

---

## Citation

If you use Minerva or the benchmark dataset in your research, please cite:

```
@article{san2026minerva,
  title   = {Minerva: A Verified Multi-Agent Knowledge Graph System for Materials Science},
  author  = {San, Sevval},
  year    = {2026},
  url     = {https://github.com/snsevval/scientific-literature-knowledge-graph}
}
```

---

## Contact

Sevval San — github.com/snsevval
