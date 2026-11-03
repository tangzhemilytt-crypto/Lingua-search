"""Production MVP API. Legacy tutorial endpoints remain in src.api."""

import hashlib
import hmac
import json
import sqlite3
import subprocess
import sys
import threading
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from src.config import Settings
from src.rag import Provider, retrieve, build_answer
from src.schemas import Query, Question, Rename
from src.public_demo import create_demo_router
from src.store import Store


class BodyLimit:
    def __init__(self, app, limit):
        self.app, self.limit = app, limit

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        received = 0

        async def bounded_receive():
            nonlocal received
            message = await receive()
            received += len(message.get("body", b""))
            if received > self.limit:
                raise HTTPException(413, "Request is too large.")
            return message

        await self.app(scope, bounded_receive, send)


def create_app(settings=None, provider=None, demo_provider=None):
    settings = settings or Settings()
    if settings.production and len(settings.token) < 32:
        raise RuntimeError(
            "Production requires WORKSPACE_TOKEN with at least 32 characters."
        )
    store = Store(settings.database_path)
    provider = provider or Provider(settings)
    if settings.demo_seed:
        store.seed()
    operations = threading.Lock()
    rate_lock = threading.Lock()
    requests = defaultdict(deque)

    @asynccontextmanager
    async def lifespan(app):
        yield

    app = FastAPI(
        title="LinguaSearch",
        version="1.0.0",
        lifespan=lifespan,
        docs_url=None if settings.production else "/docs",
        redoc_url=None,
        openapi_url=None if settings.production else "/openapi.json",
    )
    app.state.store = store
    app.add_middleware(
        BodyLimit, limit=settings.max_upload_mb * 1024 * 1024 + 128 * 1024
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins.split(","),
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "Authorization"],
    )

    @app.middleware("http")
    async def headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; object-src 'none'"
        )
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    def authorize(request: Request):
        auth = request.headers.get("authorization", "")
        if settings.token and not hmac.compare_digest(auth, "Bearer " + settings.token):
            raise HTTPException(401, "Enter your workspace access token in Settings.")
        # Only the socket IP is trusted; forwarded headers must be controlled by deployment.
        ip = request.client.host if request.client else "local"
        now = time.monotonic()
        with rate_lock:
            # Bound memory; a single workspace is intentionally small.
            for key in list(requests):
                if not requests[key] or now - requests[key][-1] > 60:
                    del requests[key]
            if len(requests) >= 1000 and ip not in requests:
                raise HTTPException(429, "Server is busy. Try again in a minute.")
            window = requests[ip]
            while window and now - window[0] > 60:
                window.popleft()
            if len(window) >= 60:
                raise HTTPException(429, "Too many requests. Try again in a minute.")
            window.append(now)

    def lock_operation():
        if not operations.acquire(blocking=False):
            raise HTTPException(
                409,
                "Another upload or AI operation is running. Please try again shortly.",
            )
        try:
            yield
        finally:
            operations.release()

    secure = [Depends(authorize)]
    busy = [Depends(authorize), Depends(lock_operation)]

    @app.get("/health")
    def health():
        with store.db() as db:
            db.execute("SELECT 1")
        return {"status": "ok"}

    @app.get("/api/config")
    def config():
        return {
            "mode": "ai" if settings.api_key else "demo",
            "auth_required": bool(settings.token),
            "max_upload_mb": settings.max_upload_mb,
            "embedding_model": settings.embedding_model if settings.api_key else None,
            "chat_model": settings.chat_model if settings.api_key else None,
            "provider": settings.provider if settings.api_key else None,
            "max_model_requests_per_day": settings.max_model_requests_per_day,
            "public_demo_enabled": settings.public_demo_enabled,
            "max_demo_model_requests_per_day": settings.max_demo_model_requests_per_day,
        }

    @app.get("/api/documents", dependencies=secure)
    def documents():
        return {"documents": store.list()}

    def document(doc_id):
        with store.db() as db:
            row = db.execute(
                "SELECT id,title,filename,pages,sample FROM documents WHERE id=?",
                (doc_id,),
            ).fetchone()
        if not row:
            raise HTTPException(404, "Document not found.")
        return dict(row)

    @app.post("/api/documents", status_code=201, dependencies=busy)
    async def upload(file: UploadFile):
        try:
            if not file.filename or Path(file.filename).suffix.lower() != ".pdf":
                raise HTTPException(400, "Only PDF files are supported.")
            content = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
            if len(content) > settings.max_upload_mb * 1024 * 1024:
                raise HTTPException(413, "PDF exceeds the upload size limit.")
            if not content.startswith(b"%PDF-"):
                raise HTTPException(400, "This is not a valid PDF.")

            def parse():
                try:
                    result = subprocess.run(
                        [sys.executable, "-m", "src.pdf_worker"],
                        input=content,
                        capture_output=True,
                        timeout=20,
                    )
                    parsed = json.loads(result.stdout)
                    if "error" in parsed:
                        raise HTTPException(400, parsed["error"])
                    return parsed
                except (subprocess.TimeoutExpired, json.JSONDecodeError):
                    raise HTTPException(
                        400, "PDF could not be processed within the safe parsing limit."
                    )

            parsed = await run_in_threadpool(parse)
            chunks = parsed["chunks"]
            digest = hashlib.sha256(content).hexdigest()
            with store.db() as db:
                if db.execute(
                    "SELECT 1 FROM documents WHERE sha256=?", (digest,)
                ).fetchone():
                    raise HTTPException(409, "This PDF is already in your library.")
            vectors = (
                await run_in_threadpool(provider.embed, [c[1] for c in chunks])
                if settings.api_key
                else None
            )
            filename = file.filename.replace("\\", "/").split("/")[-1][:200]
            try:
                return store.add(
                    Path(filename).stem,
                    filename,
                    chunks,
                    digest,
                    content,
                    page_count=parsed["pages"],
                    embeddings=vectors,
                    model=settings.embedding_cache_key if vectors else None,
                )
            except sqlite3.IntegrityError:
                raise HTTPException(409, "This PDF is already in your library.")
            except ValueError as exc:
                raise HTTPException(409, str(exc))
        finally:
            await file.close()

    @app.get("/api/documents/{doc_id}", dependencies=secure)
    def detail(doc_id: str):
        return {
            **document(doc_id),
            "passages": [
                {"id": r["id"], "page": r["page"], "text": r["text"]}
                for r in store.chunks([doc_id])
            ],
        }

    @app.get("/api/documents/{doc_id}/file", dependencies=secure)
    def download(doc_id: str):
        info = document(doc_id)
        with store.db() as db:
            pdf = db.execute(
                "SELECT pdf FROM documents WHERE id=?", (doc_id,)
            ).fetchone()[0]
        if not pdf:
            raise HTTPException(
                404, "Demo documents are text excerpts; no PDF is attached."
            )
        return Response(
            pdf,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{doc_id}.pdf"'},
        )

    @app.patch("/api/documents/{doc_id}", dependencies=busy)
    def rename(doc_id: str, body: Rename):
        document(doc_id)
        with store.db() as db:
            db.execute("UPDATE documents SET title=? WHERE id=?", (body.title, doc_id))
        return document(doc_id)

    @app.delete("/api/documents/{doc_id}", dependencies=busy)
    def delete(doc_id: str):
        document(doc_id)
        with store.db() as db:
            db.execute("DELETE FROM documents WHERE id=?", (doc_id,))
        return {"status": "deleted", "id": doc_id}

    def find(body):
        for doc_id in body.document_ids:
            document(doc_id)
        return retrieve(
            store, provider, settings, body.query, body.document_ids, body.limit
        )

    @app.post("/api/search", dependencies=busy)
    def search(body: Query):
        return {
            "results": find(body),
            "mode": "semantic" if settings.api_key else "lexical",
        }

    @app.post("/api/ask", dependencies=busy)
    def ask(body: Question):
        return build_answer(body, find(body), provider, settings)

    if settings.public_demo_enabled:
        demo_store = Store(settings.database_path + ".public-demo")
        demo_store.seed()
        app.state.demo_store = demo_store
        app.include_router(create_demo_router(
            settings, demo_store, demo_provider or Provider(settings, scope="demo"), operations))

    dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
    if dist.is_dir():
        app.mount("/", StaticFiles(directory=dist, html=True), name="web")
    return app


app = create_app()
