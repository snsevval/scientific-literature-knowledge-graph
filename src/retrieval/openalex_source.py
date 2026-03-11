import aiohttp
import asyncio
from typing import List
from retrieval.arxiv_source import Paper


async def search_openalex(query: str, max_results: int = 10) -> List[Paper]:
    """OpenAlex'ten makale çeker — Materials Science concept filtresi ile."""

    url = "https://api.openalex.org/works"
    params = {
        "search": query,
        "per-page": max_results,
        # Sadece Materials Science concept'i — tek ID, 400 hatası yok
        "filter": "is_oa:true,concepts.id:C192562407",
        "sort": "relevance_score:desc",
        "select": "title,abstract_inverted_index,doi,primary_location,publication_year,authorships,id"
    }

    papers = []

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as resp:
            if resp.status != 200:
                print(f"OpenAlex hata: {resp.status}")
                return []

            data = await resp.json()
            results = data.get("results", [])

            for r in results:
                abstract = ""
                inv = r.get("abstract_inverted_index")
                if inv:
                    word_pos = []
                    for word, positions in inv.items():
                        for pos in positions:
                            word_pos.append((pos, word))
                    word_pos.sort(key=lambda x: x[0])
                    abstract = " ".join(w for _, w in word_pos)

                doi = r.get("doi", "") or ""
                if doi.startswith("https://doi.org/"):
                    doi = doi.replace("https://doi.org/", "")

                loc = r.get("primary_location") or {}
                pdf_url = loc.get("pdf_url") or loc.get("landing_page_url") or ""

                authors = []
                for a in r.get("authorships", []):
                    name = a.get("author", {}).get("display_name", "")
                    if name:
                        authors.append(name)

                title = r.get("title", "") or ""
                year = r.get("publication_year", 0) or 0

                if title:
                    papers.append(Paper(
                        title=title,
                        abstract=abstract,
                        doi=doi,
                        url=pdf_url,
                        year=year,
                        authors=authors,
                        source="openalex"
                    ))

    return papers


if __name__ == "__main__":
    async def test():
        print("OpenAlex aranıyor...")
        papers = await search_openalex("superconducting nanowires", max_results=3)
        for p in papers:
            print(f"\n{p.title[:70]}")
            print(f"   Yıl: {p.year}")
        print(f"\n{len(papers)} makale bulundu!")
    asyncio.run(test())