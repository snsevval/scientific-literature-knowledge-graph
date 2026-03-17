import asyncio
import hashlib
import io
import aiohttp
import fitz  # PyMuPDF
from typing import List
from retrieval.arxiv_source import Paper, search_arxiv
from retrieval.openalex_source import search_openalex
from retrieval.crossref_source import search_crossref

UNPAYWALL_EMAIL = "223405063@ogrenci.ibu.edu.tr"


def make_paper_id(paper: Paper) -> str:
    if paper.doi:
        return paper.doi.lower().strip()
    raw = f"{paper.title.lower().strip()}_{paper.year}"
    return hashlib.md5(raw.encode()).hexdigest()


def deduplicate(papers: List[Paper]) -> List[Paper]:
    seen = {}
    unique = []
    for paper in papers:
        pid = make_paper_id(paper)
        if pid not in seen:
            seen[pid] = paper
            unique.append(paper)
        else:
            existing = seen[pid]
            if not existing.abstract and paper.abstract:
                existing.abstract = paper.abstract
    return unique


def is_relevant(paper: Paper, original_query: str) -> bool:
    if not paper.title:
        return False

    stop_words = {"the", "a", "an", "of", "in", "for", "and", "or", "with", "on", "at", "to"}
    query_words = [
        w.lower().strip('"') for w in original_query.split()
        if len(w.strip('"')) >= 3 and w.lower().strip('"') not in stop_words
    ]

    if not query_words:
        return True

    title_lower = paper.title.lower()

    def matches(word: str) -> bool:
        return word in title_lower or word.rstrip("s") in title_lower

    matched = sum(1 for w in query_words if matches(w))

    if len(query_words) <= 2:
        return matched == len(query_words)
    else:
        return matched > len(query_words) / 2


async def get_pdf_url_unpaywall(doi: str, session: aiohttp.ClientSession) -> str:
    try:
        url = f"https://api.unpaywall.org/v2/{doi}?email={UNPAYWALL_EMAIL}"
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
            if resp.status != 200:
                return ""
            data = await resp.json()
            best = data.get("best_oa_location") or {}
            pdf_url = best.get("url_for_pdf") or best.get("url") or ""
            return pdf_url
    except Exception:
        return ""


async def extract_text_from_pdf(pdf_url: str, session: aiohttp.ClientSession) -> str:
    try:
        async with session.get(pdf_url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status != 200:
                return ""
            content = await resp.read()
            doc = fitz.open(stream=io.BytesIO(content), filetype="pdf")
            text = ""
            for page in doc[:3]:
                text += page.get_text()
                if len(text) > 3000:
                    break
            doc.close()
            return text[:3000].strip()
    except Exception:
        return ""


async def enrich_with_unpaywall(papers: List[Paper]) -> List[Paper]:
    to_enrich = [p for p in papers if not p.abstract and p.doi]

    if not to_enrich:
        return papers

    print(f"   Unpaywall: {len(to_enrich)} makale zenginleştiriliyor...")

    async with aiohttp.ClientSession() as session:
        for paper in to_enrich:
            pdf_url = await get_pdf_url_unpaywall(paper.doi, session)
            if pdf_url:
                text = await extract_text_from_pdf(pdf_url, session)
                if text:
                    paper.abstract = text
                    paper.url = pdf_url
                    print(f"   PDF bulundu: {paper.title[:50]}")
                else:
                    print(f"   PDF indirilemedi: {paper.title[:50]}")
            else:
                print(f"   OA PDF yok: {paper.title[:50]}")

    return papers


async def search_all(query: str, max_per_source: int = 10, original_query: str = "") -> List[Paper]:
    filter_query = original_query or query

    print(f"\n'{query}' için arama başlatılıyor...")
    print("   Kaynaklar: arXiv | OpenAlex | CrossRef")

    results = await asyncio.gather(
        search_arxiv(query, max_per_source),
        search_openalex(query, max_per_source),
        search_crossref(query, max_per_source),
        return_exceptions=True
    )

    arxiv_papers, openalex_papers, crossref_papers = results

    if isinstance(arxiv_papers, Exception):
        print(f"   arXiv hatası: {arxiv_papers}")
        arxiv_papers = []
    if isinstance(openalex_papers, Exception):
        print(f"   OpenAlex hatası: {openalex_papers}")
        openalex_papers = []
    if isinstance(crossref_papers, Exception):
        print(f"   CrossRef hatası: {crossref_papers}")
        crossref_papers = []

    print(f"\n   Ham sonuçlar:")
    print(f"      arXiv    : {len(arxiv_papers)} makale")
    print(f"      OpenAlex : {len(openalex_papers)} makale")
    print(f"      CrossRef : {len(crossref_papers)} makale")

    all_papers = arxiv_papers + openalex_papers + crossref_papers
    print(f"      Toplam   : {len(all_papers)} makale (filtre öncesi)")

    filtered = [p for p in all_papers if is_relevant(p, filter_query)]
    dropped = len(all_papers) - len(filtered)
    if dropped > 0:
        print(f"      Filtrelendi: {dropped} alakasız makale atıldı")

    unique_papers = deduplicate(filtered)
    print(f"      Benzersiz: {len(unique_papers)} makale (tekilleştirme sonrası)")

    # Unpaywall zenginleştirme
    unique_papers = await enrich_with_unpaywall(unique_papers)

    return unique_papers


if __name__ == "__main__":
    async def test():
        papers = await search_all("superconducting nanowires", max_per_source=5)
        print(f"\n{'='*60}")
        print(f"SONUÇLAR — {len(papers)} benzersiz makale")
        print(f"{'='*60}")
        for i, p in enumerate(papers, 1):
            print(f"\n{i}. {p.title[:70]}")
            print(f"   Kaynak : {p.source} | Yıl: {p.year}")
            print(f"   Abstract: {'VAR' if p.abstract else 'YOK'}")

    asyncio.run(test())