import aiohttp
import asyncio
from typing import List
from retrieval.arxiv_source import Paper


async def search_crossref(query: str, max_results: int = 10) -> List[Paper]:
    """CrossRef'ten makale çeker — title bazlı arama, relevance sıralaması."""

    url = "https://api.crossref.org/works"
    params = {
        "query.title": query,   # sadece title'da ara
        "rows": max_results,
        "sort": "relevance",    # alakalılığa göre sırala
        "select": "title,abstract,DOI,URL,published,author,type"
    }
    headers = {
        "User-Agent": "ActiveScience/1.0 (mailto:research@example.com)"
    }

    papers = []

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, headers=headers) as resp:
            if resp.status != 200:
                print(f"CrossRef hata: {resp.status}")
                return []

            data = await resp.json()
            items = data.get("message", {}).get("items", [])

            for r in items:
                title_list = r.get("title", [])
                title = title_list[0] if title_list else ""
                if not title:
                    continue

                # Abstract (HTML temizle)
                abstract = r.get("abstract", "") or ""
                abstract = abstract.replace("<jats:p>", "").replace("</jats:p>", "")
                abstract = abstract.replace("<jats:italic>", "").replace("</jats:italic>", "")
                abstract = abstract.replace("<jats:bold>", "").replace("</jats:bold>", "")

                doi = r.get("DOI", "") or ""
                url_paper = r.get("URL", "") or f"https://doi.org/{doi}"

                pub = r.get("published", {})
                date_parts = pub.get("date-parts", [[0]])
                year = date_parts[0][0] if date_parts and date_parts[0] else 0

                authors = []
                for a in r.get("author", []):
                    given = a.get("given", "")
                    family = a.get("family", "")
                    name = f"{given} {family}".strip()
                    if name:
                        authors.append(name)

                papers.append(Paper(
                    title=title,
                    abstract=abstract,
                    doi=doi,
                    url=url_paper,
                    year=year,
                    authors=authors,
                    source="crossref"
                ))

    return papers


if __name__ == "__main__":
    async def test():
        print("CrossRef aranıyor...")
        papers = await search_crossref("superconducting nanowires", max_results=3)
        for p in papers:
            print(f"\n{p.title[:70]}")
            print(f"   Yıl: {p.year} | DOI: {p.doi[:40] if p.doi else 'yok'}")
            print(f"   Abstract: {p.abstract[:80]}..." if p.abstract else "   Abstract: yok")
        print(f"\n{len(papers)} makale bulundu!")

    asyncio.run(test())