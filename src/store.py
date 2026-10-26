import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

SAMPLES = [
    (
        "The multilingual mind",
        "EN · 中文",
        [
            "Language and identity are deeply connected. The words we choose signal belonging, culture, and personal experience. Bilingual speakers can express different aspects of identity in each language. 语言与身份认同密切相关。双语者可以用不同语言表达不同的自我。",
            "Code-switching is the practice of alternating between languages within a conversation. It can express solidarity and adapt communication to a social context. 语码转换指在对话中切换语言，能够表达群体认同并适应社交环境。",
        ],
    ),
    (
        "A field guide to RAG",
        "EN · 中文",
        [
            "Retrieval-augmented generation (RAG) retrieves relevant passages before generating an answer. Grounding an answer in source documents makes evidence inspectable, but does not guarantee factual accuracy. 检索增强生成先检索相关段落，再生成回答。引用让证据可检查，但不能保证答案完全正确。",
            "Multilingual embeddings represent text from different languages in a shared vector space. A Chinese query can retrieve a relevant English passage based on semantic similarity. 多语言嵌入将不同语言的文本映射到共享向量空间，支持中文问题检索英文段落。",
            "A reliable RAG system keeps document IDs, page numbers, and original passages with every chunk. When evidence is missing, the system should say it cannot answer rather than invent a source. 可靠的系统应保留文档编号、页码和原文；证据不足时应明确表示无法回答。",
        ],
    ),
    (
        "Responsible AI notes",
        "EN · Español",
        [
            "Privacy starts with data minimization. Send only the retrieved passages needed for a question to an external model provider. Never expose an API key in browser code. La privacidad comienza con minimizar los datos. Nunca expongas una clave API en el navegador.",
            "Human evaluation should measure retrieval relevance, citation correctness, and whether the answer is supported by its sources. La evaluación humana debe medir la relevancia, la precisión de las citas y el respaldo de las fuentes.",
        ],
    ),
]


class Store:
    def __init__(self, path):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.db() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY, title TEXT NOT NULL, filename TEXT NOT NULL,
                size_bytes INTEGER NOT NULL, pages INTEGER NOT NULL,
                created_at TEXT NOT NULL, sample INTEGER NOT NULL DEFAULT 0,
                sha256 TEXT UNIQUE NOT NULL, pdf BLOB);
            CREATE TABLE IF NOT EXISTS chunks (
                id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                page INTEGER NOT NULL, text TEXT NOT NULL, embedding TEXT, embedding_model TEXT);
            CREATE INDEX IF NOT EXISTS chunks_document ON chunks(document_id);
            """)

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=20)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def list(self):
        with self.db() as db:
            return [
                dict(r)
                for r in db.execute(
                    "SELECT id,title,filename,size_bytes,pages,created_at,sample,(SELECT count(*) FROM chunks WHERE document_id=documents.id) AS chunks FROM documents ORDER BY created_at DESC,id"
                )
            ]

    def add(
        self,
        title,
        filename,
        pages,
        digest,
        pdf=None,
        sample=False,
        embeddings=None,
        model=None,
    ):
        doc_id = uuid4().hex
        rows = [
            (
                uuid4().hex,
                doc_id,
                page,
                text,
                json.dumps(embeddings[i]) if embeddings else None,
                model,
            )
            for i, (page, text) in enumerate(pages)
        ]
        with self.db() as db:
            if (
                db.execute("SELECT count(*) FROM documents").fetchone()[0] >= 100
                or db.execute("SELECT count(*) FROM chunks").fetchone()[0] + len(rows)
                > 5000
            ):
                raise ValueError(
                    "Workspace capacity reached (100 documents / 5,000 passages). Delete documents first."
                )
            db.execute(
                "INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    doc_id,
                    title,
                    filename,
                    len(pdf or b""),
                    max(p for p, _ in pages),
                    datetime.now(timezone.utc).isoformat(),
                    int(sample),
                    digest,
                    pdf,
                ),
            )
            db.executemany("INSERT INTO chunks VALUES (?,?,?,?,?,?)", rows)
        return next(d for d in self.list() if d["id"] == doc_id)

    def seed(self):
        with self.db() as db:
            if db.execute("SELECT 1 FROM metadata WHERE key='seeded'").fetchone():
                return
        for title, language, pages in SAMPLES:
            with self.db() as db:
                exists = db.execute(
                    "SELECT 1 FROM documents WHERE sha256=?", ("sample:" + title,)
                ).fetchone()
            if not exists:
                self.add(
                    title,
                    title + ".txt",
                    list(enumerate(pages, 1)),
                    "sample:" + title,
                    sample=True,
                )
        with self.db() as db:
            db.execute("INSERT OR IGNORE INTO metadata VALUES ('seeded','1')")

    def chunks(self, ids=None):
        with self.db() as db:
            sql = "SELECT c.*, d.title,d.filename,d.sample FROM chunks c JOIN documents d ON d.id=c.document_id"
            return [
                dict(r)
                for r in db.execute(
                    sql
                    + (
                        " WHERE d.id IN (" + ",".join("?" for _ in ids) + ")"
                        if ids
                        else ""
                    ),
                    ids or [],
                )
            ]
