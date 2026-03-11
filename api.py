"""
ActiveScience v2 — FastAPI Backend
"""

import asyncio
import sys
import os
import uuid
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from retrieval.retrieval_manager import search_all
from agents.extraction_agent import extract_entities
from agents.verification_agent import verify_extraction, filter_by_verification
from agents.graph_reasoning_agent import GraphReasoningAgent
from critical_layer.schema_validator import run_critical_layer
from graph.graph_builder import GraphBuilder

app = FastAPI(title="ActiveScience v2", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

jobs = {}

class SearchRequest(BaseModel):
    query: str
    max_per_source: int = 10  # default 10'a çıkarıldı

class QuestionRequest(BaseModel):
    question: str


async def run_pipeline_job(job_id: str, query: str, max_per_source: int):
    jobs[job_id]["status"] = "running"
    jobs[job_id]["log"] = []
    jobs[job_id]["papers"] = []

    def log(msg):
        jobs[job_id]["log"].append(msg)
        print(msg)

    try:
        builder = GraphBuilder()
        builder.create_constraints()

        # Direkt arama — expansion yok
        log(f"🔍 '{query}' için arama başlatılıyor...")
        papers = await search_all(query, max_per_source=max_per_source)
        jobs[job_id]["total_papers"] = len(papers)
        log(f"✅ {len(papers)} benzersiz makale bulundu")

        success = skipped = errors = 0
        total_entities = total_relations = 0

        for i, paper in enumerate(papers):
            jobs[job_id]["progress"] = int((i / max(len(papers), 1)) * 100)
            jobs[job_id]["current_paper"] = paper.title[:60]

            paper_record = {
                "title": paper.title,
                "source": getattr(paper, 'source', 'unknown'),
                "year": getattr(paper, 'year', None),
                "doi": getattr(paper, 'doi', None),
                "status": "pending",
                "entities": 0,
                "relations": 0,
            }

            if not paper.abstract or len(paper.abstract.strip()) < 50:
                skipped += 1
                paper_record["status"] = "skipped"
                jobs[job_id]["papers"].append(paper_record)
                continue

            try:
                extraction = await extract_entities(paper.title, paper.abstract)
                if extraction.error:
                    errors += 1
                    paper_record["status"] = "error"
                    jobs[job_id]["papers"].append(paper_record)
                    continue

                verification = await verify_extraction(paper.abstract, extraction)
                extraction = filter_by_verification(extraction, verification)

                critical = run_critical_layer(extraction)
                if not critical.passed:
                    errors += 1
                    paper_record["status"] = "error"
                    jobs[job_id]["papers"].append(paper_record)
                    continue

                builder.write_paper(paper.title, paper.doi, paper.url, paper.year)
                e_n, r_n = builder.write_validated_result(critical, paper.title)
                total_entities += e_n
                total_relations += r_n
                success += 1

                paper_record["status"] = "success"
                paper_record["entities"] = e_n
                paper_record["relations"] = r_n

            except Exception as ex:
                errors += 1
                paper_record["status"] = "error"
                log(f"   ❌ Hata: {ex}")

            jobs[job_id]["papers"].append(paper_record)
            await asyncio.sleep(0.5)

        stats = builder.get_stats()
        builder.close()

        jobs[job_id].update({
            "status": "completed",
            "progress": 100,
            "stats": stats,
            "summary": {
                "success": success,
                "skipped": skipped,
                "errors": errors,
                "total_entities": total_entities,
                "total_relations": total_relations,
            }
        })
        log(f"🏁 Tamamlandı!")

    except Exception as e:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = str(e)


@app.post("/search/start")
async def start_search(req: SearchRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {
        "status": "starting",
        "progress": 0,
        "query": req.query,
        "log": [],
        "current_paper": "",
        "papers": [],
    }
    background_tasks.add_task(run_pipeline_job, job_id, req.query, req.max_per_source)
    return {"job_id": job_id, "message": "Pipeline başlatıldı"}

@app.get("/search/progress/{job_id}")
async def get_progress(job_id: str):
    if job_id not in jobs:
        return {"error": "Job bulunamadı"}
    return jobs[job_id]

@app.get("/graph/stats")
async def get_stats():
    try:
        builder = GraphBuilder()
        stats = builder.get_stats()
        builder.close()
        return stats
    except Exception as e:
        return {"error": str(e)}

@app.post("/graph/ask")
async def ask_graph(req: QuestionRequest):
    try:
        agent = GraphReasoningAgent()
        result = await agent.ask(req.question)
        agent.close()
        return result
    except Exception as e:
        return {"error": str(e)}

@app.get("/graph/nodes")
async def get_nodes():
    try:
        builder = GraphBuilder()
        nodes = builder.query_graph(
            "MATCH (n) RETURN labels(n)[0] as type, n.name as name, n.canonical_name as canonical LIMIT 200"
        )
        builder.close()
        return nodes
    except Exception as e:
        return {"error": str(e)}

@app.get("/")
async def root():
    return {"message": "ActiveScience v2 API", "docs": "/docs"}