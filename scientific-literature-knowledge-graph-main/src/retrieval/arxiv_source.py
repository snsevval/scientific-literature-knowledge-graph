import arxiv
import asyncio
from dataclasses import dataclass
from typing import List

@dataclass
class Paper:
    title: str
    abstract: str
    doi: str
    url: str
    year: int
    authors: List[str]
    source: str

async def search_arxiv(query: str, max_results: int = 10) -> List[Paper]:
    """arXiv'den makale çeker."""
    
    def _sync_search():
        client = arxiv.Client()
        search = arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.Relevance
        )
        papers = []
        for r in client.results(search):
            papers.append(Paper(
                title=r.title,
                abstract=r.summary,
                doi=r.doi or "",
                url=r.pdf_url,
                year=r.published.year if r.published else 0,
                authors=[a.name for a in r.authors],
                source="arxiv"
            ))
        return papers

    # asyncio ile sync fonksiyonu çalıştır
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync_search)


# TEST — direkt çalıştırınca test eder
if __name__ == "__main__":
    async def test():
        print("arXiv aranıyor...")
        papers = await search_arxiv("graph neural networks", max_results=3)
        for p in papers:
            print(f"\n📄 {p.title[:60]}...")
            print(f"   Yıl: {p.year} | Kaynak: {p.source}")
            print(f"   URL: {p.url}")
        print(f"\n✅ {len(papers)} makale bulundu!")

    asyncio.run(test())