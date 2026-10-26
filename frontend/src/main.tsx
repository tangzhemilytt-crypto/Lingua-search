import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  ArrowUpRight,
  ArrowUp,
  Search,
  Library,
  MessageSquare,
  Settings,
  Plus,
  FileText,
  Globe2,
  ChevronRight,
  X,
  Check,
  Download,
  Trash2,
  Pencil,
  UploadCloud,
  Sparkles,
  Link2,
  Menu,
  LoaderCircle,
  BookOpen,
  ShieldCheck,
  ArrowRight,
} from "lucide-react";
import { api, download, getToken } from "./api";
import type { Document, Passage, Source, Answer, Config } from "./api";
import "./styles.css";

type View = "overview" | "library" | "search" | "ask";
const suggestions = [
  "How does language shape identity?",
  "什么是检索增强生成？",
  "How do multilingual embeddings work?",
];
const formatDate = (date: string) =>
  new Date(date).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });
function App() {
  const [view, setView] = useState<View>("overview");
  const [docs, setDocs] = useState<Document[]>([]);
  const [config, setConfig] = useState<Config | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("");
  const [scope, setScope] = useState("");
  const [language, setLanguage] = useState("Auto");
  const [results, setResults] = useState<Source[] | null>(null);
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [lastQuery, setLastQuery] = useState("");
  const [settings, setSettings] = useState(false);
  const [token, setToken] = useState(getToken());
  const [mobile, setMobile] = useState(false);
  const [preview, setPreview] = useState<{
    title: string;
    passages: Passage[];
    page?: number;
  } | null>(null);
  const [deleting, setDeleting] = useState<Document | null>(null);
  const [renaming, setRenaming] = useState<Document | null>(null);
  const [newTitle, setNewTitle] = useState("");
  const [drag, setDrag] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const queryInput = useRef<HTMLTextAreaElement>(null);
  const pageRef = useRef<HTMLDivElement>(null);
  async function load() {
    setLoading(true);
    try {
      const c = await api<Config>("/config");
      setConfig(c);
      const d = await api<{ documents: Document[] }>("/documents");
      setDocs(d.documents);
      setError("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    void load();
  }, []);
  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(() => setNotice(""), 4500);
    return () => clearTimeout(timer);
  }, [notice]);
  useEffect(() => {
    if (!preview && !settings && !deleting && !renaming) return;
    const key = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setPreview(null);
        setSettings(false);
        setDeleting(null);
        setRenaming(null);
      }
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [preview, settings, deleting, renaming]);
  function navigate(next: View) {
    setView(next);
    setMobile(false);
    setError("");
    pageRef.current?.scrollTo(0, 0);
  }
  async function upload(file?: File) {
    if (!file || busy) return;
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setError("Please choose a PDF file.");
      return;
    }
    if (file.size > (config?.max_upload_mb || 5) * 1024 * 1024) {
      setError(`PDF must be smaller than ${config?.max_upload_mb || 5} MB.`);
      return;
    }
    setBusy(true);
    setError("");
    try {
      const data = new FormData();
      data.append("file", file);
      await api("/documents", { method: "POST", body: data });
      await load();
      setNotice("Your document is ready to explore.");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
      if (input.current) input.current.value = "";
    }
  }
  async function run(text = query, kind: View = view) {
    if (!text.trim() || busy) return;
    const next = kind === "search" ? "search" : "ask";
    setView(next);
    setBusy(true);
    setError("");
    setLastQuery(text);
    setQuery(text);
    setResults(null);
    setAnswer(null);
    try {
      const body = JSON.stringify({
        query: text,
        document_ids: scope ? [scope] : [],
        limit: 5,
        language,
      });
      if (next === "search") {
        const r = await api<{ results: Source[] }>("/search", {
          method: "POST",
          body,
        });
        setResults(r.results);
      } else setAnswer(await api<Answer>("/ask", { method: "POST", body }));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function openDocument(id: string, page?: number) {
    try {
      const d = await api<{ title: string; passages: Passage[] }>(
        `/documents/${id}`,
      );
      setPreview({ ...d, page });
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function remove() {
    if (!deleting) return;
    setBusy(true);
    try {
      await api(`/documents/${deleting.id}`, { method: "DELETE" });
      if (scope === deleting.id) setScope("");
      setDeleting(null);
      setResults(null);
      setAnswer(null);
      await load();
      setNotice("Document and its indexed passages deleted.");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function rename() {
    if (!renaming) return;
    setBusy(true);
    try {
      await api(`/documents/${renaming.id}`, {
        method: "PATCH",
        body: JSON.stringify({ title: newTitle }),
      });
      setRenaming(null);
      await load();
      setNotice("Document renamed.");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const filtered = docs.filter((d) =>
    (d.title + " " + d.filename).toLowerCase().includes(filter.toLowerCase()),
  );
  const passages = docs.reduce((sum, d) => sum + d.chunks, 0);
  const live = config?.mode === "ai";
  function Sources({ items }: { items: Source[] }) {
    return (
      <div className="source-list">
        {items.map((r, i) => (
          <button
            className="source-card"
            key={r.id}
            onClick={() => void openDocument(r.document_id, r.page)}
          >
            <span className="source-number">{r.number || i + 1}</span>
            <div>
              <strong>{r.title}</strong>
              <span>
                Page {r.page} · {r.sample ? "Sample document" : "Uploaded PDF"}
              </span>
              <p>{r.text}</p>
            </div>
            <ArrowUpRight size={16} />
          </button>
        ))}
      </div>
    );
  }
  return (
    <div className="app">
      <aside className={`sidebar ${mobile ? "mobile-open" : ""}`}>
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            navigate("overview");
          }}
        >
          <span className="brand-mark">
            L<span>•</span>
          </span>
          <span>
            LinguaSearch<small>KNOWLEDGE, CONNECTED</small>
          </span>
        </a>
        <div className="workspace">
          <span className="avatar">E</span>
          <div>
            My workspace<small>Personal knowledge space</small>
          </div>
          <ChevronRight size={15} />
        </div>
        <div className="nav-label">WORKSPACE</div>
        <nav aria-label="Main navigation">
          {(
            [
              { id: "overview", label: "Overview", icon: Globe2 },
              { id: "library", label: "Document library", icon: Library },
              { id: "search", label: "Explore & search", icon: Search },
              { id: "ask", label: "Ask your documents", icon: MessageSquare },
            ] as const
          ).map((n) => (
            <button
              key={n.id}
              className={view === n.id ? "active" : ""}
              onClick={() => navigate(n.id)}
            >
              <n.icon size={19} />
              {n.label}
              {n.id === "library" && (
                <span className="nav-count">{docs.length}</span>
              )}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="sidebar-note">
            <span className="little-orbit">✧</span>
            <strong>
              A world of knowledge.
              <br />
              One place to find it.
            </strong>
            <p>
              Your ideas don't stop at language.
              <br />
              Your search shouldn't either.
            </p>
            <span>
              Built for curious minds <ArrowUpRight size={13} />
            </span>
          </div>
          <button className="settings-button" onClick={() => setSettings(true)}>
            <Settings size={18} />
            Settings & connection
            <span className={`dot ${live ? "live" : ""}`} />
          </button>
          <div className="sidebar-footer">
            LinguaSearch <span>v1.0 · Portfolio edition</span>
          </div>
        </div>
      </aside>
      <div className="main-shell" ref={pageRef}>
        <header className="topbar">
          <div>
            <button
              className="icon-button mobile-toggle"
              aria-label="Toggle navigation"
              onClick={() => setMobile(!mobile)}
            >
              <Menu size={20} />
            </button>
            <span>Workspace</span>
            <ChevronRight size={13} />
            <strong>
              {
                {
                  overview: "Overview",
                  library: "Document library",
                  search: "Explore & search",
                  ask: "Ask your documents",
                }[view]
              }
            </strong>
          </div>
          <div>
            <span className="mode-pill">
              <span className={`dot ${live ? "live" : ""}`} />
              {live ? "AI connected" : "Offline demo"}
            </span>
            <a
              className="github-link"
              href="https://github.com/tangzhemilytt-crypto/Lingua-search"
              target="_blank"
              rel="noreferrer"
            >
              View project <ArrowUpRight size={14} />
            </a>
            <span className="avatar small">E</span>
          </div>
        </header>
        <main>
          {error && (
            <div role="alert" className="error-banner">
              <span>{error}</span>
              <button onClick={() => setError("")} aria-label="Dismiss error">
                <X size={16} />
              </button>
              {config?.auth_required && (
                <button onClick={() => setSettings(true)}>Open Settings</button>
              )}
            </div>
          )}
          {notice && (
            <div role="status" className="toast">
              <Check size={16} />
              {notice}
            </div>
          )}
          {view === "overview" && (
            <>
              <div className="page-heading">
                <div>
                  <span className="eyebrow">YOUR KNOWLEDGE WORKSPACE</span>
                  <h1>Big ideas. No language barriers.</h1>
                  <p>A little less searching. A lot more discovering.</p>
                </div>
                <button
                  className="primary"
                  onClick={() => input.current?.click()}
                  disabled={busy}
                >
                  <Plus size={17} />
                  Upload document
                </button>
              </div>
              <section className="hero">
                <div className="hero-content">
                  <span className="hero-tag">
                    <Sparkles size={14} /> CONNECT THE DOTS
                  </span>
                  <h2>
                    Your documents.
                    <br />A world of possibilities.
                  </h2>
                  <p>
                    Search beyond keywords. Ask in your own language.
                    <br />
                    Find answers grounded in what you've read.
                  </p>
                  <button
                    className="hero-action"
                    onClick={() => {
                      navigate("ask");
                      setTimeout(() => queryInput.current?.focus(), 0);
                    }}
                  >
                    Start a conversation <ArrowUpRight size={17} />
                  </button>
                </div>
                <div className="language-art" aria-hidden="true">
                  <div className="orbit orbit-one" />
                  <div className="orbit orbit-two" />
                  <div className="orbit orbit-three" />
                  <div className="orbital en">
                    Hello<span>English</span>
                  </div>
                  <div className="orbital zh">
                    你好<span>中文</span>
                  </div>
                  <div className="orbital es">
                    Hola<span>Español</span>
                  </div>
                  <div className="orbital ja">
                    こんにちは<span>日本語</span>
                  </div>
                  <div className="orbital-center">
                    <Globe2 size={48} strokeWidth={1} />
                  </div>
                  <span className="art-star star-one">✦</span>
                  <span className="art-star star-two">✧</span>
                  <span className="art-caption">
                    DIFFERENT LANGUAGES. SHARED UNDERSTANDING.
                  </span>
                </div>
              </section>
              <div className="stats-grid">
                <div className="stat">
                  <span className="stat-icon mint">
                    <Library size={20} />
                  </span>
                  <div>
                    <span>Documents in your library</span>
                    <strong>
                      {loading ? "—" : docs.length}
                      <small>A growing collection of ideas</small>
                    </strong>
                  </div>
                </div>
                <div className="stat">
                  <span className="stat-icon sand">
                    <BookOpen size={20} />
                  </span>
                  <div>
                    <span>Searchable passages</span>
                    <strong>
                      {loading ? "—" : passages}
                      <small>Every insight, connected to a source</small>
                    </strong>
                  </div>
                </div>
                <div className="stat">
                  <span className="stat-icon lavender">
                    <Globe2 size={20} />
                  </span>
                  <div>
                    <span>Retrieval mode</span>
                    <strong className="text-stat">
                      {live ? "Multilingual AI" : "Offline preview"}
                      <small>
                        {live
                          ? "Search across language boundaries"
                          : "Add a server API key to enable AI"}
                      </small>
                    </strong>
                  </div>
                </div>
              </div>
              <div className="overview-lower">
                <section className="panel recent-panel">
                  <div className="section-heading">
                    <div>
                      <h2>Your library</h2>
                      <p>A home for your next discovery.</p>
                    </div>
                    <button
                      className="text-button"
                      onClick={() => navigate("library")}
                    >
                      View all <ArrowRight size={15} />
                    </button>
                  </div>
                  {loading ? (
                    <div className="loading">
                      <LoaderCircle className="spin" size={20} />
                      Loading your library…
                    </div>
                  ) : docs.length ? (
                    docs.slice(0, 4).map((d) => (
                      <button
                        className="recent-row"
                        key={d.id}
                        onClick={() => void openDocument(d.id)}
                      >
                        <span
                          className={`file-icon ${d.sample ? "sample" : ""}`}
                        >
                          <FileText size={20} />
                        </span>
                        <span>
                          <strong>{d.title}</strong>
                          <small>
                            {d.sample ? "CURATED SAMPLE" : "PDF DOCUMENT"}{" "}
                            <i>·</i> {d.pages} pages
                          </small>
                        </span>
                        <span className="ready">
                          <span className="dot live" />
                          Ready
                        </span>
                        <ChevronRight size={16} />
                      </button>
                    ))
                  ) : (
                    <div className="empty">
                      <Library size={28} />
                      <h3>Your library starts here</h3>
                      <p>Upload your first PDF to start exploring.</p>
                    </div>
                  )}
                </section>
                <section className="panel quick-ask">
                  <span className="mini-label">
                    <MessageSquare size={16} />A GOOD QUESTION OPENS DOORS
                  </span>
                  <h2>
                    Where will your
                    <br />
                    curiosity take you?
                  </h2>
                  <p>Try a question from the sample library.</p>
                  <div>
                    {suggestions.map((q, i) => (
                      <button
                        key={q}
                        onClick={() => void run(q, "ask")}
                        disabled={busy}
                      >
                        <span>{q}</span>
                        <ArrowUpRight size={16} />
                        {i === 1 && <small>ASK IN ANOTHER LANGUAGE</small>}
                      </button>
                    ))}
                  </div>
                  <span className="grounded">
                    <ShieldCheck size={14} />
                    Every excerpt links back to its source
                  </span>
                </section>
              </div>
            </>
          )}
          {view === "library" && (
            <>
              <div className="page-heading">
                <div>
                  <span className="eyebrow">COLLECT. CONNECT. DISCOVER.</span>
                  <h1>Your document library</h1>
                  <p>Keep your knowledge close and your sources closer.</p>
                </div>
                <button
                  className="primary"
                  disabled={busy}
                  onClick={() => input.current?.click()}
                >
                  <Plus size={17} />
                  Upload document
                </button>
              </div>
              <div
                className={`drop-zone ${drag ? "drag" : ""}`}
                onDragOver={(e) => {
                  e.preventDefault();
                  setDrag(true);
                }}
                onDragLeave={() => setDrag(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setDrag(false);
                  void upload(e.dataTransfer.files[0]);
                }}
              >
                <UploadCloud size={28} />
                <div>
                  <strong>
                    {busy
                      ? "Processing your document…"
                      : "Drop a PDF here to add it to your library"}
                  </strong>
                  <p>
                    Text-based PDFs · Up to {config?.max_upload_mb || 5} MB ·
                    100 pages · One file at a time
                  </p>
                </div>
                <button
                  className="secondary"
                  disabled={busy}
                  onClick={() => input.current?.click()}
                >
                  Browse files
                </button>
              </div>
              <div className="library-toolbar">
                <h2>
                  All documents <span>{docs.length}</span>
                </h2>
                <label className="filter-input">
                  <Search size={17} />
                  <input
                    aria-label="Filter documents"
                    value={filter}
                    onChange={(e) => setFilter(e.target.value)}
                    placeholder="Find a document…"
                  />
                </label>
              </div>
              <div className="document-grid">
                {filtered.map((d) => (
                  <article className="document-card" key={d.id}>
                    <div className="document-card-top">
                      <span className={`file-icon ${d.sample ? "sample" : ""}`}>
                        <FileText size={24} />
                      </span>
                      <span className="type-label">
                        {d.sample ? "SAMPLE" : "PDF"}
                      </span>
                    </div>
                    <button
                      className="document-title"
                      onClick={() => void openDocument(d.id)}
                    >
                      {d.title}
                    </button>
                    <p>
                      {d.pages} pages <i>·</i> {d.chunks} passages
                    </p>
                    <div className="document-status">
                      <span className="ready">
                        <span className="dot live" />
                        Indexed & ready
                      </span>
                      <span>{formatDate(d.created_at)}</span>
                    </div>
                    <div className="document-actions">
                      <button onClick={() => void openDocument(d.id)}>
                        <BookOpen size={15} />
                        Read
                      </button>
                      <button
                        aria-label={`Rename ${d.title}`}
                        onClick={() => {
                          setRenaming(d);
                          setNewTitle(d.title);
                        }}
                      >
                        <Pencil size={15} />
                      </button>
                      {!d.sample && (
                        <button
                          aria-label={`Download ${d.title}`}
                          onClick={() =>
                            void download(d.id).catch((e) =>
                              setError(e.message),
                            )
                          }
                        >
                          <Download size={15} />
                        </button>
                      )}
                      <button
                        aria-label={`Delete ${d.title}`}
                        onClick={() => setDeleting(d)}
                      >
                        <Trash2 size={15} />
                      </button>
                    </div>
                  </article>
                ))}
              </div>
              {!loading && !filtered.length && (
                <div className="empty">
                  <Library size={32} />
                  <h3>
                    {filter
                      ? "No matching documents"
                      : "Make room for your first idea"}
                  </h3>
                  <p>
                    {filter
                      ? "Try a different title."
                      : "Upload a PDF using the button above."}
                  </p>
                </div>
              )}
            </>
          )}
          {(view === "ask" || view === "search") && (
            <>
              <div className="page-heading">
                <div>
                  <span className="eyebrow">
                    {view === "ask"
                      ? "A CONVERSATION WITH YOUR KNOWLEDGE"
                      : "FOLLOW YOUR CURIOSITY"}
                  </span>
                  <h1>
                    {view === "ask"
                      ? "Good questions. Grounded answers."
                      : "Find the idea you’re looking for."}
                  </h1>
                  <p>
                    {view === "ask"
                      ? "Ask your documents anything. See exactly where the answer comes from."
                      : "Explore passages across your library, with context intact."}
                  </p>
                </div>
              </div>
              <section className="query-panel">
                <div className="query-label">
                  {view === "ask" ? (
                    <MessageSquare size={18} />
                  ) : (
                    <Search size={18} />
                  )}
                  <label htmlFor="query">
                    {view === "ask"
                      ? "What would you like to understand?"
                      : "What are you looking for?"}
                  </label>
                </div>
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    void run();
                  }}
                >
                  <textarea
                    ref={queryInput}
                    id="query"
                    placeholder={
                      view === "ask"
                        ? "Ask a question in any language…"
                        : "Search for a topic, phrase, or idea…"
                    }
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    maxLength={1500}
                    onKeyDown={(e) => {
                      if (
                        e.key === "Enter" &&
                        !e.shiftKey &&
                        !e.nativeEvent.isComposing
                      ) {
                        e.preventDefault();
                        void run();
                      }
                    }}
                  />
                  <div className="query-controls">
                    <label>
                      <Library size={15} />
                      <select
                        aria-label="Document scope"
                        value={scope}
                        onChange={(e) => setScope(e.target.value)}
                      >
                        <option value="">All documents</option>
                        {docs.map((d) => (
                          <option key={d.id} value={d.id}>
                            {d.title}
                          </option>
                        ))}
                      </select>
                    </label>
                    {view === "ask" && (
                      <label>
                        <Globe2 size={15} />
                        <select
                          aria-label="Answer language"
                          value={language}
                          onChange={(e) => setLanguage(e.target.value)}
                        >
                          {[
                            "Auto",
                            "English",
                            "中文",
                            "Español",
                            "Français",
                            "日本語",
                          ].map((l) => (
                            <option key={l}>{l}</option>
                          ))}
                        </select>
                      </label>
                    )}
                    <button
                      className="primary"
                      type="submit"
                      disabled={busy || !query.trim()}
                    >
                      {busy ? (
                        <LoaderCircle className="spin" size={16} />
                      ) : (
                        <ArrowUp size={16} />
                      )}{" "}
                      {busy
                        ? "Working…"
                        : view === "ask"
                          ? "Ask question"
                          : "Search library"}
                    </button>
                  </div>
                </form>
              </section>
              <div className="mode-info">
                <ShieldCheck size={15} />
                {live
                  ? "AI answers use retrieved passages. Always check the original sources."
                  : "Offline mode uses keyword matching and original excerpts. Cross-language semantic search requires a server API key."}
              </div>
              {busy && (
                <div role="status" className="thinking">
                  <LoaderCircle className="spin" size={22} />
                  <div>
                    <strong>Connecting your ideas…</strong>
                    <p>
                      Retrieving relevant passages and following the evidence.
                    </p>
                  </div>
                </div>
              )}
              {!busy && answer && (
                <section className="answer-panel">
                  <div className="answer-heading">
                    <span className="answer-symbol">
                      <Sparkles size={20} />
                    </span>
                    <div>
                      <span className="eyebrow">
                        {answer.mode === "demo"
                          ? "EVIDENCE PREVIEW"
                          : "GROUNDED ANSWER"}
                      </span>
                      <h2>{lastQuery}</h2>
                    </div>
                  </div>
                  <div className="answer-text">
                    {answer.answer.split(/(\[\d+\])/g).map((part, i) => {
                      const match = part.match(/^\[(\d+)\]$/);
                      const source =
                        match &&
                        answer.citations.find(
                          (c) => c.number === Number(match[1]),
                        );
                      return source ? (
                        <button
                          key={i}
                          className="inline-citation"
                          aria-label={`Open citation ${source.number}`}
                          onClick={() =>
                            void openDocument(source.document_id, source.page)
                          }
                        >
                          {source.number}
                        </button>
                      ) : (
                        <React.Fragment key={i}>{part}</React.Fragment>
                      );
                    })}
                  </div>
                  {answer.citations.length > 0 && (
                    <>
                      <div className="sources-label">
                        <Link2 size={16} />
                        Sources · {answer.citations.length}
                      </div>
                      <Sources items={answer.citations} />
                    </>
                  )}
                </section>
              )}
              {!busy && results !== null && (
                <section className="results">
                  <div className="section-heading">
                    <h2>{results.length} relevant passages</h2>
                    <span className="type-label">
                      {live ? "SEMANTIC + KEYWORD" : "KEYWORD MATCH"}
                    </span>
                  </div>
                  {results.length ? (
                    <Sources items={results} />
                  ) : (
                    <div className="empty">
                      <Search size={30} />
                      <h3>No supporting passages found</h3>
                      <p>
                        Try another phrase, broaden your document scope, or
                        upload a relevant PDF.
                      </p>
                    </div>
                  )}
                </section>
              )}
              {!busy && !answer && results === null && (
                <div className="question-start">
                  <span className="question-start-icon">
                    <Globe2 size={28} />
                  </span>
                  <h2>Every discovery starts with a question.</h2>
                  <p>Explore your library from a new angle.</p>
                  <div className="suggestion-chips">
                    {suggestions.map((q) => (
                      <button
                        disabled={busy}
                        key={q}
                        onClick={() => void run(q, view)}
                      >
                        {q}
                        <ArrowUpRight size={14} />
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
          <footer className="main-footer">
            <span>
              <span className="brand-dot" />
              LinguaSearch
            </span>
            <span>Thoughtful search. Traceable answers.</span>
            <span>
              Made for a multilingual world <Globe2 size={13} />
            </span>
          </footer>
        </main>
      </div>
      <input
        ref={input}
        type="file"
        accept="application/pdf,.pdf"
        aria-label="Upload PDF"
        className="visually-hidden"
        onChange={(e) => void upload(e.target.files?.[0])}
      />
      {busy && view !== "ask" && view !== "search" && (
        <div className="processing" role="status">
          <LoaderCircle className="spin" size={18} />
          Processing… Please keep this page open.
        </div>
      )}
      {settings && (
        <Modal title="Settings & connection" onClose={() => setSettings(false)}>
          <div className="connection-status">
            <span className={`dot ${live ? "live" : ""}`} />
            <strong>
              {live ? "AI provider connected" : "Offline demo mode"}
            </strong>
          </div>
          <p>
            Without a model key, explore the sample library with keyword search
            and quoted excerpts. Cross-language semantic search and generated
            answers require a server-side API key.
          </p>
          <div className="settings-detail">
            <strong>Model configuration</strong>
            <p>
              Set OPENAI_API_KEY in the server’s .env file, then restart the
              backend. Never paste a model API key into this browser.
            </p>
            {live && <small>Embedding model: {config?.embedding_model}</small>}
          </div>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              sessionStorage.setItem("lingua-token", token.trim());
              setSettings(false);
              void load();
            }}
          >
            <label className="field-label" htmlFor="token">
              Workspace access token
            </label>
            <input
              id="token"
              type="password"
              autoComplete="off"
              placeholder="Only needed for a protected workspace"
              value={token}
              onChange={(e) => setToken(e.target.value)}
            />
            <small className="help-text">
              This is your WORKSPACE_TOKEN, separate from the model key. Kept
              only in this tab’s session. All token holders share this
              workspace.
            </small>
            <div className="modal-actions">
              <button
                type="button"
                className="secondary"
                onClick={() => {
                  sessionStorage.removeItem("lingua-token");
                  setToken("");
                  setDocs([]);
                  setAnswer(null);
                  setResults(null);
                  setPreview(null);
                  setSettings(false);
                  setNotice("Workspace token cleared.");
                }}
              >
                Clear token
              </button>
              <button className="primary">Save connection</button>
            </div>
          </form>
        </Modal>
      )}
      {preview && (
        <Modal title={preview.title} wide onClose={() => setPreview(null)}>
          <div className="preview-meta">
            <BookOpen size={16} />
            Extracted passages · Original text
            {preview.page && <span>Showing page {preview.page}</span>}
          </div>
          {preview.passages
            .filter((p) => !preview.page || p.page === preview.page)
            .map((p) => (
              <div className="preview-passage" key={p.id}>
                <span>PAGE {p.page}</span>
                <p>{p.text}</p>
              </div>
            ))}
          {preview.page && (
            <button
              className="secondary"
              onClick={() => setPreview({ ...preview, page: undefined })}
            >
              Read all pages
            </button>
          )}
        </Modal>
      )}
      {deleting && (
        <Modal title="Delete document?" onClose={() => setDeleting(null)}>
          <p>
            “{deleting.title}” and all its indexed passages will be permanently
            removed from this workspace.
          </p>
          <div className="modal-actions">
            <button className="secondary" onClick={() => setDeleting(null)}>
              Keep document
            </button>
            <button
              className="danger"
              disabled={busy}
              onClick={() => void remove()}
            >
              Delete document
            </button>
          </div>
        </Modal>
      )}
      {renaming && (
        <Modal title="Rename document" onClose={() => setRenaming(null)}>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void rename();
            }}
          >
            <label className="field-label" htmlFor="new-title">
              Document title
            </label>
            <input
              id="new-title"
              autoFocus
              maxLength={160}
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
            />
            <div className="modal-actions">
              <button
                type="button"
                className="secondary"
                onClick={() => setRenaming(null)}
              >
                Cancel
              </button>
              <button className="primary" disabled={busy || !newTitle.trim()}>
                Save title
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
function Modal({
  title,
  onClose,
  children,
  wide = false,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
  wide?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement;
    const element = ref.current;
    element?.querySelector<HTMLElement>("button,input")?.focus();
    const trap = (e: KeyboardEvent) => {
      if (e.key !== "Tab") return;
      const items = element?.querySelectorAll<HTMLElement>(
        "button:not(:disabled),input,select,textarea,a[href]",
      );
      if (!items?.length) return;
      const first = items[0],
        last = items[items.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    element?.addEventListener("keydown", trap);
    return () => {
      element?.removeEventListener("keydown", trap);
      previous?.focus();
    };
  }, []);
  return (
    <div
      className="modal-backdrop"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={ref}
        className={`modal ${wide ? "wide" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
      >
        <div className="modal-heading">
          <h2 id="modal-title">{title}</h2>
          <button
            className="icon-button"
            aria-label="Close dialog"
            onClick={onClose}
          >
            <X size={20} />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
