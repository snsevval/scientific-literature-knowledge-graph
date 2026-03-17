# scientific-literature-knowledge-graph

Bilimsel literatürden otomatik olarak bilgi çıkaran ve bu bilgileri doğruladıktan sonra knowledge graph'a yazan çok katmanlı bir sistemdir.

---
---

## Mimari

### Teknoloji Stack

- Backend: Python (FastAPI)
- LLM (Extraction): Cerebras API — Qwen-3-235B
- LLM (Verification, TTD-DR, Reasoning): Ollama — llama3.1:8b
- Knowledge Graph: Neo4j
- Embedding: sentence-transformers/all-MiniLM-L6-v2
- Vector DB: FAISS
- Frontend: Next.js + TypeScript

---

## Pipeline

```text
Kullanıcı sorgusu
      |
[1] RETRIEVAL       — arXiv, OpenAlex, CrossRef
      |
[2] ENRICHMENT      — Unpaywall ile PDF/abstract zenginleştirme
      |
[3] EXTRACTION      — Cerebras/Qwen ile entity + relation çıkarımı
      |
[4] VERIFICATION    — Ollama ile relation gerçekten var mı kontrolü
      |
[5] CRITICAL LAYER  — Deterministik schema + domain kontrolü
      |
[6] TEXTBOOK KB     — Kitaplardan evidence çekme
      |
[7] TTD-DR          — Claim textbook ile çelişiyor mu?
      |
[8] NEO4J           — Sadece doğrulanmış bilgileri yaz
