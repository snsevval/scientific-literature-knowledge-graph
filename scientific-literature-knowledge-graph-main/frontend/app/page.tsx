"use client";
import { useState, useEffect, useCallback } from "react";
import ParticleCanvas from "./ParticleCanvas";
import Cursor from "./Cursor";

const API = "http://localhost:8000";

// ─── Types ───────────────────────────────────────────────────────────────────
interface Stats {
  Material?: number; Property?: number; Application?: number;
  Method?: number; Element?: number; Formula?: number;
  Paper?: number; Relations?: number;
}
interface PaperRecord {
  title: string;
  source: string;
  year: number | null;
  doi: string | null;
  status: "success" | "skipped" | "error" | "pending";
  entities: number;
  relations: number;
}
interface JobStatus {
  status: string; progress: number; current_paper?: string;
  expanded_queries?: string[]; total_papers?: number;
  papers?: PaperRecord[];
  summary?: { success: number; skipped: number; errors: number; total_entities: number; total_relations: number };
}
interface GraphNode { type: string; name: string; canonical?: string; }

// ─── Color map ───────────────────────────────────────────────────────────────
const NODE_COLORS: Record<string, string> = {
  Material: "#ff6b9d", Property: "#a78bfa", Application: "#34d399",
  Method: "#60a5fa", Element: "#fbbf24", Formula: "#f87171", Paper: "#dc58b9",
};

const STATUS_COLORS: Record<string, string> = {
  success: "#34d399",
  skipped: "#fbbf24",
  error: "#f87171",
  pending: "#6b7280",
};

const STATUS_LABELS: Record<string, string> = {
  success: " Başarılı",
  skipped: "⏭ Atlandı",
  error: "❌ Hata",
  pending: "⏳ Bekliyor",
};

const SOURCE_COLORS: Record<string, string> = {
  arxiv: "#f97316",
  openalex: "#60a5fa",
  crossref: "#a78bfa",
  unknown: "#6b7280",
};

// ─── Shared styles ───────────────────────────────────────────────────────────
const card: React.CSSProperties = {
  background: "var(--card)", border: "1px solid var(--border)",
  borderRadius: 16, padding: "2rem", backdropFilter: "blur(10px)",
};
const inputStyle: React.CSSProperties = {
  flex: 1, background: "rgba(255,255,255,0.05)", border: "1px solid var(--border)",
  borderRadius: 10, padding: "0.75rem 1.1rem", color: "var(--text)", fontSize: "0.9rem",
  fontFamily: "Poppins, sans-serif", outline: "none", transition: "border 0.3s",
};
const btnStyle: React.CSSProperties = {
  background: "linear-gradient(135deg, var(--main), var(--main2))",
  border: "none", borderRadius: 10, padding: "0.75rem 1.6rem",
  color: "white", fontWeight: 600, cursor: "pointer", fontSize: "0.9rem",
  fontFamily: "Poppins, sans-serif", whiteSpace: "nowrap",
  boxShadow: "0 0 20px rgba(220,88,185,0.3)", transition: "all 0.3s",
};

// ─── Spinner ─────────────────────────────────────────────────────────────────
const Spinner = () => (
  <span style={{ display: "inline-block", width: 13, height: 13, border: "2px solid rgba(255,255,255,0.3)", borderTopColor: "white", borderRadius: "50%", animation: "spin 0.7s linear infinite", marginRight: 6, verticalAlign: "middle" }} />
);

// ─── Section wrapper ─────────────────────────────────────────────────────────
const Section = ({ id, children }: { id: string; children: React.ReactNode }) => (
  <section id={id} style={{ padding: "1.5rem 8%", maxWidth: 900, margin: "0 auto" }}>
    {children}
  </section>
);

// ─── Paper Table ─────────────────────────────────────────────────────────────
const PaperTable = ({ papers }: { papers: PaperRecord[] }) => {
  const [filter, setFilter] = useState<string>("all");

  const filtered = filter === "all" ? papers : papers.filter(p => p.status === filter);

  return (
    <div style={{ marginTop: "1.2rem" }}>
      {/* Filter tabs */}
      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "0.8rem", flexWrap: "wrap" }}>
        {["all", "success", "skipped", "error"].map(f => (
          <button key={f} onClick={() => setFilter(f)} style={{
            background: filter === f ? "rgba(220,88,185,0.2)" : "rgba(255,255,255,0.04)",
            border: `1px solid ${filter === f ? "var(--main)" : "var(--border)"}`,
            borderRadius: 8, padding: "0.3rem 0.9rem", color: "var(--text)",
            fontSize: "0.75rem", cursor: "pointer", fontFamily: "Poppins,sans-serif",
            transition: "all 0.2s",
          }}>
            {f === "all" ? `Tümü (${papers.length})` :
             f === "success" ? `✅ Başarılı (${papers.filter(p=>p.status==="success").length})` :
             f === "skipped" ? `⏭ Atlandı (${papers.filter(p=>p.status==="skipped").length})` :
             `❌ Hata (${papers.filter(p=>p.status==="error").length})`}
          </button>
        ))}
      </div>

      {/* Table */}
      <div style={{ overflowX: "auto", borderRadius: 10, border: "1px solid var(--border)" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.78rem" }}>
          <thead>
            <tr style={{ borderBottom: "1px solid var(--border)", background: "rgba(0,0,0,0.3)" }}>
              <th style={{ padding: "0.7rem 1rem", textAlign: "left", opacity: 0.5, fontWeight: 600 }}>Başlık</th>
              <th style={{ padding: "0.7rem 0.8rem", textAlign: "center", opacity: 0.5, fontWeight: 600, whiteSpace: "nowrap" }}>Kaynak</th>
              <th style={{ padding: "0.7rem 0.8rem", textAlign: "center", opacity: 0.5, fontWeight: 600 }}>Yıl</th>
              <th style={{ padding: "0.7rem 0.8rem", textAlign: "center", opacity: 0.5, fontWeight: 600 }}>Durum</th>
              <th style={{ padding: "0.7rem 0.8rem", textAlign: "center", opacity: 0.5, fontWeight: 600 }}>Entity</th>
              <th style={{ padding: "0.7rem 0.8rem", textAlign: "center", opacity: 0.5, fontWeight: 600 }}>Relation</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr><td colSpan={6} style={{ padding: "2rem", textAlign: "center", opacity: 0.4 }}>Makale yok</td></tr>
            ) : filtered.map((p, i) => (
              <tr key={i} style={{ borderBottom: "1px solid rgba(255,255,255,0.05)", transition: "background 0.2s" }}
                onMouseEnter={e => (e.currentTarget.style.background = "rgba(220,88,185,0.05)")}
                onMouseLeave={e => (e.currentTarget.style.background = "transparent")}>
                <td style={{ padding: "0.7rem 1rem", maxWidth: 300 }}>
                  <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", opacity: 0.85 }} title={p.title}>
                    {p.title}
                  </div>
                </td>
                <td style={{ padding: "0.7rem 0.8rem", textAlign: "center" }}>
                  <span style={{
                    padding: "0.2rem 0.6rem", borderRadius: 6, fontSize: "0.7rem", fontWeight: 600,
                    background: `${SOURCE_COLORS[p.source?.toLowerCase()] || SOURCE_COLORS.unknown}22`,
                    color: SOURCE_COLORS[p.source?.toLowerCase()] || SOURCE_COLORS.unknown,
                    border: `1px solid ${SOURCE_COLORS[p.source?.toLowerCase()] || SOURCE_COLORS.unknown}44`,
                  }}>
                    {p.source || "?"}
                  </span>
                </td>
                <td style={{ padding: "0.7rem 0.8rem", textAlign: "center", opacity: 0.6 }}>
                  {p.year || "–"}
                </td>
                <td style={{ padding: "0.7rem 0.8rem", textAlign: "center" }}>
                  <span style={{ color: STATUS_COLORS[p.status], fontSize: "0.75rem", fontWeight: 600 }}>
                    {STATUS_LABELS[p.status]}
                  </span>
                </td>
                <td style={{ padding: "0.7rem 0.8rem", textAlign: "center" }}>
                  {p.status === "success" ? (
                    <span style={{ color: "#a78bfa", fontWeight: 700 }}>{p.entities}</span>
                  ) : <span style={{ opacity: 0.3 }}>–</span>}
                </td>
                <td style={{ padding: "0.7rem 0.8rem", textAlign: "center" }}>
                  {p.status === "success" ? (
                    <span style={{ color: "#34d399", fontWeight: 700 }}>{p.relations}</span>
                  ) : <span style={{ opacity: 0.3 }}>–</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════════════════════
export default function Home() {
  const [query, setQuery] = useState("");
  const [maxPer, setMaxPer] = useState(3);
  const [jobId, setJobId] = useState<string | null>(null);
  const [job, setJob] = useState<JobStatus | null>(null);
  const [searching, setSearching] = useState(false);
  const [showTable, setShowTable] = useState(false);

  const [stats, setStats] = useState<Stats>({});
  const [nodes, setNodes] = useState<GraphNode[]>([]);

  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const [answer, setAnswer] = useState<{ text: string; cypher: string } | null>(null);

  const [scrollPct, setScrollPct] = useState(0);

  useEffect(() => {
    const onScroll = () => {
      const pct = (window.scrollY / (document.body.scrollHeight - window.innerHeight)) * 100;
      setScrollPct(pct);
    };
    window.addEventListener("scroll", onScroll);
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const loadStats = useCallback(async () => {
    try {
      const [sRes, nRes] = await Promise.all([fetch(`${API}/graph/stats`), fetch(`${API}/graph/nodes`)]);
      setStats(await sRes.json());
      const ns = await nRes.json();
      setNodes(Array.isArray(ns) ? ns : []);
    } catch {}
  }, []);

  useEffect(() => { loadStats(); }, [loadStats]);

  useEffect(() => {
    if (!jobId) return;
    const iv = setInterval(async () => {
      try {
        const res = await fetch(`${API}/search/progress/${jobId}`);
        const d: JobStatus = await res.json();
        setJob(d);
        if (d.status === "completed" || d.status === "error") {
          clearInterval(iv);
          setSearching(false);
          loadStats();
        }
      } catch {}
    }, 1500);
    return () => clearInterval(iv);
  }, [jobId, loadStats]);

  const startSearch = async () => {
    if (!query.trim()) return;
    setSearching(true);
    setJob(null);
    setShowTable(false);
    try {
      const res = await fetch(`${API}/search/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, max_per_source: maxPer }),
      });
      const d = await res.json();
      setJobId(d.job_id);
    } catch {
      alert("API bağlantı hatası! uvicorn çalışıyor mu?");
      setSearching(false);
    }
  };

  const askGraph = async (q?: string) => {
    const qText = q ?? question;
    if (!qText.trim()) return;
    if (q) setQuestion(q);
    setAsking(true);
    setAnswer(null);
    try {
      const res = await fetch(`${API}/graph/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: qText }),
      });
      const d = await res.json();
      setAnswer({ text: d.answer || d.error || "Sonuç bulunamadı.", cypher: d.cypher || "" });
    } catch {
      alert("API bağlantı hatası!");
    }
    setAsking(false);
  };

  const statKeys: (keyof Stats)[] = ["Material", "Property", "Application", "Method", "Element", "Formula", "Paper", "Relations"];
  const suggestions = [
    "Which materials have superconductivity?",
    "What applications are materials used in?",
    "Which methods synthesize materials?",
    "Hangi materyaller kuantum hesaplamada?",
    "What elements are found in nanowires?",
  ];

  const byType: Record<string, string[]> = {};
  nodes.forEach((n) => {
    if (!byType[n.type]) byType[n.type] = [];
    if (n.name && byType[n.type].length < 6) byType[n.type].push(n.name);
  });

  const statusLabel = !job ? "" :
    job.status === "completed" ? " Tamamlandı!" :
    job.status === "error" ? " Hata!" :
    job.status === "running" ? " İşleniyor..." : " Başlatılıyor...";

  return (
    <>
      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes fadeUp { from { opacity:0; transform:translateY(24px); } to { opacity:1; transform:translateY(0); } }
        .fade-up { animation: fadeUp 0.7s ease forwards; }
        input:focus { border-color: var(--main) !important; box-shadow: 0 0 15px rgba(220,88,185,0.2); }
        .stat-card:hover { border-color: var(--main) !important; transform: translateY(-3px); box-shadow: 0 0 20px rgba(220,88,185,0.15); }
        .suggestion:hover { border-color: var(--main) !important; background: rgba(220,88,185,0.2) !important; }
        .nav-link:hover { color: var(--main) !important; opacity: 1 !important; }
        .btn-main:hover { transform: translateY(-2px); box-shadow: 0 0 30px rgba(220,88,185,0.5) !important; }
        .toggle-btn:hover { border-color: var(--main) !important; color: var(--main) !important; }
      `}</style>

      <ParticleCanvas />
      <Cursor />

      <div style={{ position: "fixed", top: 0, left: 0, height: 3, width: `${scrollPct}%`, background: "linear-gradient(90deg,var(--main),var(--main2))", zIndex: 9998, boxShadow: "0 0 8px var(--main)", transition: "width 0.1s" }} />

      <header style={{ position: "fixed", top: "1.5rem", left: 0, width: "100%", padding: "1.2rem 8%", background: "rgba(220,88,185,0.07)", backdropFilter: "blur(12px)", borderBottom: "1px solid var(--border)", display: "flex", justifyContent: "space-between", alignItems: "center", zIndex: 100 }}>
        <div style={{ fontSize: "1.6rem", fontWeight: 800 }}>
          Active<span style={{ color: "var(--main)", textShadow: "0 0 20px var(--main)" }}>Science</span>
          <span style={{ fontSize: "0.85rem", opacity: 0.5, fontWeight: 400, marginLeft: 6 }}>v2</span>
        </div>
        <nav style={{ display: "flex", gap: "2rem" }}>
          {["search", "stats", "reasoning"].map((id) => (
            <a key={id} href={`#${id}`} className="nav-link" style={{ color: "var(--text)", opacity: 0.7, fontSize: "0.9rem", textDecoration: "none", transition: "0.3s", textTransform: "capitalize" }}>
              {id === "search" ? "Arama" : id === "stats" ? "Graph" : "Sorgula"}
            </a>
          ))}
        </nav>
      </header>

      <main style={{ position: "relative", zIndex: 1, paddingTop: "7rem" }}>

        <div style={{ minHeight: "38vh", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", textAlign: "center", padding: "4rem 8% 2rem" }}>
          <h1 className="fade-up" style={{ fontSize: "clamp(2rem,5vw,3rem)", fontWeight: 800, lineHeight: 1.2 }}>
            Akademik <span style={{ color: "var(--main)", textShadow: "0 0 30px var(--main)" }}>Knowledge Graph</span><br />Sistemi
          </h1>
          <p className="fade-up" style={{ opacity: 0.55, marginTop: "1rem", fontSize: "0.95rem", maxWidth: 520, animationDelay: "0.15s" }}>
            Çoklu kaynaklardan makale topla · AI ile entity çıkar · Neo4j'e yaz · Graph'ı sorgula
          </p>
        </div>

        {/* SEARCH */}
        <Section id="search">
          <div style={card} className="fade-up">
            <h2 style={{ marginBottom: "1.2rem", fontSize: "1.1rem", opacity: 0.85 }}>
              <span style={{ color: "var(--main)" }}>Literatür Tara</span>
            </h2>

            <div style={{ display: "flex", gap: "0.8rem", marginBottom: "0.6rem" }}>
              <input
                style={inputStyle} value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && startSearch()}
                placeholder="Araştırma konusu gir... (örn: superconducting nanowires)"
              />
              <input
                type="number" min={1} max={50} value={maxPer}
                onChange={(e) => setMaxPer(Number(e.target.value))}
                title="Kaynak başına makale sayısı"
                style={{ ...inputStyle, flex: "none", width: 70, textAlign: "center" }}
              />
              <button className="btn-main" disabled={searching} onClick={startSearch} style={{ ...btnStyle, opacity: searching ? 0.5 : 1 }}>
                {searching ? <><Spinner />Tarıyor...</> : "Tara"}
              </button>
            </div>
            <p style={{ fontSize: "0.75rem", opacity: 0.4 }}>Sayı: kaynak başına max makale (arXiv + OpenAlex + CrossRef)</p>

            {/* Progress */}
            {(searching || job) && (
              <div style={{ marginTop: "1rem", background: "rgba(0,0,0,0.3)", border: "1px solid var(--border)", borderRadius: 12, padding: "1.2rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.82rem", opacity: 0.7 }}>
                  <span>{statusLabel}</span>
                  <span>{job?.progress ?? 0}%</span>
                </div>
                <div style={{ background: "rgba(255,255,255,0.05)", borderRadius: 99, height: 8, margin: "0.8rem 0", overflow: "hidden" }}>
                  <div style={{ height: "100%", width: `${job?.progress ?? 0}%`, background: "linear-gradient(90deg,var(--main),var(--main2))", borderRadius: 99, transition: "width 0.5s ease", boxShadow: "0 0 10px var(--main)" }} />
                </div>
                {job?.current_paper && <div style={{ fontSize: "0.75rem", opacity: 0.45, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>📄 {job.current_paper}</div>}
                {job?.expanded_queries && (
                  <div style={{ marginTop: "0.6rem", display: "flex", flexWrap: "wrap", gap: "0.4rem" }}>
                    {job.expanded_queries.map((q, i) => (
                      <span key={i} style={{ fontSize: "0.72rem", background: "rgba(220,88,185,0.1)", border: "1px solid var(--border)", borderRadius: 6, padding: "0.2rem 0.6rem", opacity: i === 0 ? 1 : 0.6 }}>{q}</span>
                    ))}
                  </div>
                )}
                {job?.status === "completed" && job.summary && (
                  <div style={{ marginTop: "0.8rem", display: "flex", gap: "1.5rem", fontSize: "0.8rem", opacity: 0.7, flexWrap: "wrap" }}>
                    <span>✅ {job.summary.success} başarılı</span>
                    <span>⏭ {job.summary.skipped} atlandı</span>
                    <span>❌ {job.summary.errors} hatalı</span>
                    <span>🧩 {job.summary.total_entities} entity</span>
                    <span>🔗 {job.summary.total_relations} relation</span>
                  </div>
                )}

                {/* Toggle table button */}
                {job?.papers && job.papers.length > 0 && (
                  <button
                    className="toggle-btn"
                    onClick={() => setShowTable(!showTable)}
                    style={{ marginTop: "0.8rem", background: "transparent", border: "1px solid var(--border)", borderRadius: 8, padding: "0.4rem 1rem", color: "var(--text)", fontSize: "0.78rem", cursor: "pointer", fontFamily: "Poppins,sans-serif", transition: "all 0.2s" }}>
                    {showTable ? "▲ Tabloyu Gizle" : `▼ Makale Tablosunu Göster (${job.papers.length})`}
                  </button>
                )}

                {/* Paper table */}
                {showTable && job?.papers && job.papers.length > 0 && (
                  <PaperTable papers={job.papers} />
                )}
              </div>
            )}
          </div>
        </Section>

        {/* STATS */}
        <Section id="stats">
          <div style={card} className="fade-up">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.2rem" }}>
              <h2 style={{ fontSize: "1.1rem", opacity: 0.85 }}><span style={{ color: "var(--main)" }}>Knowledge Graph</span></h2>
              <button onClick={loadStats} style={{ background: "transparent", border: "1px solid var(--border)", borderRadius: 8, padding: "0.4rem 1rem", color: "var(--text)", fontSize: "0.8rem", cursor: "pointer", fontFamily: "Poppins,sans-serif", transition: "0.3s" }}>↻ Güncelle</button>
            </div>

            {/* Legend */}
            <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem", marginBottom: "1rem" }}>
              {Object.entries(NODE_COLORS).filter(([k]) => k !== "Paper").map(([type, color]) => (
                <span key={type} style={{ display: "flex", alignItems: "center", gap: "0.3rem", fontSize: "0.72rem", opacity: 0.7 }}>
                  <span style={{ width: 8, height: 8, borderRadius: "50%", background: color, display: "inline-block" }} />
                  {type}
                </span>
              ))}
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "1rem", marginBottom: "1.2rem" }}>
              {statKeys.map((k) => (
                <div key={k} className="stat-card" style={{ background: "var(--card)", border: `1px solid ${NODE_COLORS[k as string] || "var(--border)"}33`, borderRadius: 12, padding: "1rem", textAlign: "center", transition: "all 0.3s", cursor: "default" }}>
                  <div style={{ fontSize: "1.8rem", fontWeight: 800, color: NODE_COLORS[k as string] || "var(--main)", textShadow: `0 0 15px ${NODE_COLORS[k as string] || "var(--main)"}66` }}>{stats[k] ?? "–"}</div>
                  <div style={{ fontSize: "0.72rem", opacity: 0.5, marginTop: "0.2rem" }}>{k}</div>
                </div>
              ))}
            </div>

            <div style={{ height: 1, background: "linear-gradient(90deg,transparent,var(--border),transparent)", margin: "0.5rem 0 1rem" }} />
            <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem" }}>
              {Object.keys(byType).length === 0
                ? <span style={{ opacity: 0.4, fontSize: "0.8rem" }}>Henüz node yok — önce bir arama yap!</span>
                : Object.entries(byType).flatMap(([type, names]) =>
                    names.map((name) => (
                      <span key={type + name} style={{ padding: "0.3rem 0.8rem", borderRadius: 99, fontSize: "0.72rem", fontWeight: 600, border: `1px solid ${NODE_COLORS[type] || "var(--border)"}`, color: NODE_COLORS[type] || "var(--text)", background: `${NODE_COLORS[type] || "#fff"}18` }}>{name}</span>
                    ))
                  )
              }
            </div>
          </div>
        </Section>

        {/* REASONING */}
        <Section id="reasoning">
          <div style={{ ...card, marginBottom: "3rem" }} className="fade-up">
            <h2 style={{ marginBottom: "0.4rem", fontSize: "1.1rem", opacity: 0.85 }}><span style={{ color: "var(--main)" }}>Graph Reasoning</span></h2>
            <p style={{ fontSize: "0.8rem", opacity: 0.45, marginBottom: "1rem" }}>Doğal dilde soru sor → Cypher'a çevrilir → Neo4j'den cevap gelir</p>

            <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem", marginBottom: "1rem" }}>
              {suggestions.map((s) => (
                <span key={s} className="suggestion" onClick={() => askGraph(s)}
                  style={{ background: "rgba(220,88,185,0.1)", border: "1px solid var(--border)", borderRadius: 8, padding: "0.4rem 0.9rem", fontSize: "0.77rem", cursor: "pointer", transition: "0.3s", color: "var(--text)" }}>
                  {s}
                </span>
              ))}
            </div>

            <div style={{ display: "flex", gap: "0.8rem" }}>
              <input
                style={inputStyle} value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && askGraph()}
                placeholder="Graph'a soru sor..."
              />
              <button className="btn-main" disabled={asking} onClick={() => askGraph()} style={{ ...btnStyle, opacity: asking ? 0.5 : 1 }}>
                {asking ? <><Spinner />Sorgulanıyor...</> : "Sor"}
              </button>
            </div>

            {answer && (
              <div style={{ marginTop: "1.2rem", background: "rgba(0,0,0,0.4)", border: "1px solid var(--border)", borderRadius: 10, padding: "1.2rem" }}>
                <div style={{ fontSize: "0.72rem", opacity: 0.5, marginBottom: "0.5rem", letterSpacing: "0.1em" }}>CEVAP</div>
                <div style={{ fontSize: "0.9rem", lineHeight: 1.7 }}>{answer.text}</div>
                <div style={{ fontSize: "0.72rem", opacity: 0.35, marginTop: "0.8rem", fontFamily: "monospace", wordBreak: "break-all", borderTop: "1px solid var(--border)", paddingTop: "0.6rem" }}>
                  🔧 {answer.cypher}
                </div>
              </div>
            )}
          </div>
        </Section>
      </main>

      <footer style={{ textAlign: "center", padding: "2rem 8%", borderTop: "1px solid var(--border)", fontSize: "0.78rem", opacity: 0.35, position: "relative", zIndex: 1 }}>
        ActiveScience v2 &nbsp;·&nbsp; Neo4j + Ollama LLaMA + FastAPI &nbsp;·&nbsp; Multi-Agent Knowledge Graph
      </footer>
    </>
  );
}