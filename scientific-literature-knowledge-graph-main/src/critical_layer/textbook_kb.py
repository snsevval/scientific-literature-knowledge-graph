"""
Textbook Knowledge Base
PDF → Chunk → Embedding → FAISS

Klasör yapısı:
data/textbooks/
├── year1_temel/
├── year2_orta/
├── year3_ileri/
└── year4_uzman/

Kullanım:
    # İlk çalıştırma (index oluştur):
    python textbook_kb.py --build

    # Test:
    python textbook_kb.py --search "superconductivity critical temperature"
"""

import os
import json
import argparse
import numpy as np
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

# ─── Sabitler ────────────────────────────────────────────────────────────────

TEXTBOOK_DIR = Path(__file__).resolve().parent.parent.parent / "data"
INDEX_DIR    = Path(__file__).resolve().parent.parent.parent / "data" / "textbook_index"

YEAR_LEVELS = {
    "year1_temel":  1,
    "year2_orta":   2,
    "year3_ileri":  3,
    "year4_uzman":  4,
}

CHUNK_SIZE    = 800   # karakter
CHUNK_OVERLAP = 100
TOP_K         = 5     # kaç chunk döndür

# ─── Veri sınıfları ──────────────────────────────────────────────────────────

@dataclass
class TextChunk:
    text:       str
    source:     str   # PDF dosya adı
    year_level: int   # 1-4
    page:       int   # sayfa numarası
    chunk_id:   int   # sıra numarası

@dataclass
class SearchResult:
    chunk:    TextChunk
    score:    float   # düşük = daha yakın (L2 distance)
    verdict:  str     # "relevant" / "not_relevant"

# ─── PDF Okuma ────────────────────────────────────────────────────────────────

def extract_text_from_pdf(pdf_path: Path) -> List[Tuple[int, str]]:
    """PDF'den (sayfa_no, metin) listesi döndür."""
    try:
        from pypdf import PdfReader
    except ImportError:
        raise ImportError("pypdf yüklü değil: pip install pypdf --break-system-packages")

    reader = PdfReader(str(pdf_path))
    pages = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        if text and len(text.strip()) > 50:
            pages.append((i + 1, text))
    return pages


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """Metni örtüşen chunk'lara böl."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        if len(chunk.strip()) > 100:  # çok kısa chunk'ları atla
            chunks.append(chunk.strip())
        start += chunk_size - overlap
    return chunks


def load_all_chunks() -> List[TextChunk]:
    """Tüm PDF'leri oku, chunk'la."""
    all_chunks = []
    chunk_id = 0

    for year_folder, level in YEAR_LEVELS.items():
        folder_path = TEXTBOOK_DIR / year_folder
        if not folder_path.exists():
            print(f"⚠️  Klasör bulunamadı: {folder_path}")
            continue

        pdf_files = list(folder_path.glob("*.pdf"))
        if not pdf_files:
            print(f"⚠️  PDF bulunamadı: {folder_path}")
            continue

        for pdf_path in pdf_files:
            print(f"📖 Okunuyor: {pdf_path.name} (Level {level})")
            try:
                pages = extract_text_from_pdf(pdf_path)
                print(f"   {len(pages)} sayfa bulundu")

                for page_no, page_text in pages:
                    chunks = chunk_text(page_text)
                    for chunk_text_content in chunks:
                        all_chunks.append(TextChunk(
                            text=chunk_text_content,
                            source=pdf_path.name,
                            year_level=level,
                            page=page_no,
                            chunk_id=chunk_id
                        ))
                        chunk_id += 1

                print(f"   ✅ {chunk_id} toplam chunk")

            except Exception as e:
                print(f"   ❌ Hata: {e}")

    return all_chunks


# ─── Embedding ────────────────────────────────────────────────────────────────

def get_embedding_model():
    """Sentence transformer modelini yükle."""
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        raise ImportError("sentence-transformers yüklü değil: pip install sentence-transformers --break-system-packages")

    print("🧠 Embedding modeli yükleniyor (all-MiniLM-L6-v2)...")
    return SentenceTransformer("all-MiniLM-L6-v2")


def encode_chunks(model, chunks: List[TextChunk]) -> np.ndarray:
    """Chunk'ları vektöre çevir."""
    texts = [c.text for c in chunks]
    print(f"🔢 {len(texts)} chunk encode ediliyor...")

    # Batch'ler halinde işle (bellek için)
    batch_size = 256
    all_embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        embeddings = model.encode(batch, show_progress_bar=False)
        all_embeddings.append(embeddings)
        if i % 2000 == 0 and i > 0:
            print(f"   {i}/{len(texts)} tamamlandı...")

    return np.vstack(all_embeddings).astype("float32")


# ─── FAISS Index ──────────────────────────────────────────────────────────────

def build_index(embeddings: np.ndarray):
    """FAISS flat L2 index oluştur."""
    try:
        import faiss
    except ImportError:
        raise ImportError("faiss yüklü değil: pip install faiss-cpu --break-system-packages")

    dim = embeddings.shape[1]
    print(f"📊 FAISS index oluşturuluyor (dim={dim}, {len(embeddings)} vektör)...")
    index = faiss.IndexFlatL2(dim)
    index.add(embeddings)
    return index


def save_index(index, chunks: List[TextChunk], embeddings: np.ndarray):
    """Index ve metadata'yı kaydet."""
    try:
        import faiss
    except ImportError:
        raise ImportError("faiss yüklü değil")

    INDEX_DIR.mkdir(parents=True, exist_ok=True)

    # FAISS index
    faiss.write_index(index, str(INDEX_DIR / "textbook.index"))

    # Chunk metadata (JSON)
    metadata = [
        {
            "text":       c.text,
            "source":     c.source,
            "year_level": c.year_level,
            "page":       c.page,
            "chunk_id":   c.chunk_id
        }
        for c in chunks
    ]
    with open(INDEX_DIR / "chunks.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    print(f"💾 Index kaydedildi: {INDEX_DIR}/")
    print(f"   textbook.index ({index.ntotal} vektör)")
    print(f"   chunks.json ({len(metadata)} chunk)")


def load_index():
    """Kayıtlı index'i yükle."""
    try:
        import faiss
    except ImportError:
        raise ImportError("faiss yüklü değil")

    index_path  = INDEX_DIR / "textbook.index"
    chunks_path = INDEX_DIR / "chunks.json"

    if not index_path.exists() or not chunks_path.exists():
        raise FileNotFoundError(
            f"Index bulunamadı: {INDEX_DIR}\n"
            "Önce 'python textbook_kb.py --build' çalıştır"
        )

    index = faiss.read_index(str(index_path))

    with open(chunks_path, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    chunks = [
        TextChunk(
            text=m["text"],
            source=m["source"],
            year_level=m["year_level"],
            page=m["page"],
            chunk_id=m["chunk_id"]
        )
        for m in metadata
    ]

    return index, chunks


# ─── Ana API ─────────────────────────────────────────────────────────────────

class TextbookKB:
    """
    Textbook Knowledge Base — Critical Layer için ana arayüz.

    Kullanım:
        kb = TextbookKB()
        results = kb.search("superconductivity critical temperature", top_k=3)
        for r in results:
            print(r.chunk.source, r.score, r.chunk.text[:200])
    """

    def __init__(self):
        self.index  = None
        self.chunks = None
        self.model  = None
        self._loaded = False

    def _lazy_load(self):
        """İlk aramada index ve modeli yükle."""
        if self._loaded:
            return
        print("📚 Textbook KB yükleniyor...")
        self.index, self.chunks = load_index()
        self.model = get_embedding_model()
        self._loaded = True
        print(f"✅ KB hazır: {len(self.chunks)} chunk")

    def search(self, query: str, top_k: int = TOP_K, max_level: int = 4) -> List[SearchResult]:
        """
        Query'e en yakın chunk'ları döndür.

        Args:
            query:     Aranacak claim veya soru
            top_k:     Kaç sonuç dönsün
            max_level: Maksimum year level (1-4), daha basit sonuçlar için düşür
        """
        self._lazy_load()

        # Query'i encode et
        query_vec = self.model.encode([query]).astype("float32")

        # FAISS arama — daha fazla aday al, sonra filtrele
        k_search = min(top_k * 4, len(self.chunks))
        distances, indices = self.index.search(query_vec, k_search)

        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx < 0 or idx >= len(self.chunks):
                continue
            chunk = self.chunks[idx]

            # Level filtresi
            if chunk.year_level > max_level:
                continue

            results.append(SearchResult(
                chunk=chunk,
                score=float(dist),
                verdict="relevant" if dist < 50.0 else "not_relevant"
            ))

            if len(results) >= top_k:
                break

        return results

    def search_by_level(self, query: str, top_k: int = 3) -> List[SearchResult]:
        """
        Year1'den başlayarak ara, her seviyeden en iyi sonucu al.
        Critical Layer için hiyerarşik arama.
        """
        self._lazy_load()
        query_vec = self.model.encode([query]).astype("float32")

        all_results = []
        for level in range(1, 5):
            level_chunks = [c for c in self.chunks if c.year_level == level]
            if not level_chunks:
                continue

            # Bu level'daki chunk index'lerini bul
            level_indices = [c.chunk_id for c in level_chunks]

            # Tüm index'te ara, sonra filtrele
            k_search = min(50, len(self.chunks))
            distances, indices = self.index.search(query_vec, k_search)

            for dist, idx in zip(distances[0], indices[0]):
                if idx < 0:
                    continue
                chunk = self.chunks[idx]
                if chunk.year_level == level:
                    all_results.append(SearchResult(
                        chunk=chunk,
                        score=float(dist),
                        verdict="relevant" if dist < 50.0 else "not_relevant"
                    ))
                    break  # Her level'dan en iyi 1 sonuç

        # Score'a göre sırala
        all_results.sort(key=lambda x: x.score)
        return all_results[:top_k]


# ─── Build Pipeline ──────────────────────────────────────────────────────────

def build_knowledge_base():
    """Tüm PDF'leri işle ve index oluştur."""
    print("=" * 60)
    print("📚 Textbook Knowledge Base Build Pipeline")
    print("=" * 60)

    # 1. PDF'leri oku ve chunk'la
    chunks = load_all_chunks()
    if not chunks:
        print("❌ Hiç chunk bulunamadı! PDF klasörlerini kontrol et.")
        return

    print(f"\n✅ Toplam {len(chunks)} chunk oluşturuldu")

    # Level dağılımı
    for level in range(1, 5):
        level_chunks = [c for c in chunks if c.year_level == level]
        print(f"   Level {level}: {len(level_chunks)} chunk")

    # 2. Embedding
    model = get_embedding_model()
    embeddings = encode_chunks(model, chunks)
    print(f"✅ Embeddings: {embeddings.shape}")

    # 3. FAISS index
    index = build_index(embeddings)

    # 4. Kaydet
    save_index(index, chunks, embeddings)

    print("\n🎉 Knowledge Base hazır!")
    print(f"   Kullanmak için: kb = TextbookKB()")


# ─── CLI ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Textbook Knowledge Base")
    parser.add_argument("--build",  action="store_true", help="Index oluştur")
    parser.add_argument("--search", type=str,            help="Test araması yap")
    parser.add_argument("--top_k",  type=int, default=3, help="Kaç sonuç (default: 3)")
    args = parser.parse_args()

    if args.build:
        build_knowledge_base()

    elif args.search:
        kb = TextbookKB()
        print(f"\n🔍 Arama: '{args.search}'\n")
        results = kb.search(args.search, top_k=args.top_k)

        for i, r in enumerate(results, 1):
            print(f"[{i}] {r.chunk.source} | Level {r.chunk.year_level} | Sayfa {r.chunk.page} | Score: {r.score:.2f}")
            print(f"    {r.chunk.text[:300]}...")
            print()

    else:
        parser.print_help()