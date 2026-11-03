"""Anonymous, read-only demo backed by a separate curated corpus.

No route here can read or modify private workspace documents, even if the
caller supplies a private document ID or a valid owner token.
"""
import hashlib
import json
import threading
import time
from collections import defaultdict, deque
from copy import copy

from fastapi import APIRouter, Depends, HTTPException, Request

from src.rag import retrieve, build_answer
from src.schemas import Query, Question


def create_demo_router(settings, store, provider, operations):
    router = APIRouter(prefix="/api/demo", tags=["Public read-only demo"])
    windows = defaultdict(deque)
    rate_lock = threading.Lock()
    offline = copy(settings)
    offline.api_key = ""

    def limit(request: Request):
        ip = request.client.host if request.client else "local"
        now = time.monotonic()
        with rate_lock:
            for key in list(windows):
                if not windows[key] or now-windows[key][-1] > 60:
                    del windows[key]
            if len(windows) >= 1000 and ip not in windows:
                raise HTTPException(429,"Public demo is busy. Please try again in a minute.")
            window = windows[ip]
            while window and now-window[0] > 60:
                window.popleft()
            if len(window) >= 120:
                raise HTTPException(429,"Public demo is busy. Please try again in a minute.")
            window.append(now)

    def exclusive():
        if not operations.acquire(blocking=False):
            raise HTTPException(409,"Another question is being processed. Please try again shortly.")
        try:
            yield
        finally:
            operations.release()

    def info(doc_id):
        doc = next((d for d in store.list() if d["id"] == doc_id),None)
        if doc is None:
            raise HTTPException(404,"Demo document not found.")
        return doc

    def validate_scope(body):
        for doc_id in body.document_ids:
            info(doc_id)

    def key_for(kind, body):
        corpus = [(d["id"], d["title"], d["chunks"]) for d in store.list()]
        raw = json.dumps([kind,body.model_dump(),settings.provider,
                          settings.embedding_cache_key,settings.chat_model,corpus],sort_keys=True)
        return "public-cache:" + hashlib.sha256(raw.encode()).hexdigest()

    def cached(key):
        with store.db() as db:
            row = db.execute("SELECT value FROM metadata WHERE key=?",(key,)).fetchone()
        if row:
            return {**json.loads(row[0]),"cached":True,
                    "notice":"Previously generated from these demo documents; no new AI call was needed."}

    def remember(key, value):
        with store.db() as db:
            db.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES (?,?)",(key,json.dumps(value)))
            db.execute("DELETE FROM metadata WHERE key IN (SELECT key FROM metadata WHERE key LIKE 'public-cache:%' ORDER BY rowid DESC LIMIT -1 OFFSET 100)")

    @router.get("/documents",dependencies=[Depends(limit)])
    def documents():
        return {"documents":store.list(),"access":"public"}

    @router.get("/documents/{doc_id}",dependencies=[Depends(limit)])
    def detail(doc_id: str):
        return {**info(doc_id),"access":"public","passages":[
            {"id":r["id"],"page":r["page"],"text":r["text"]} for r in store.chunks([doc_id])]}

    def execute(body, kind):
        validate_scope(body)
        key = key_for(kind,body)
        saved = cached(key)
        if saved:
            return saved
        active = settings
        notice = ""
        try:
            sources = retrieve(store,provider,active,body.query,body.document_ids,body.limit)
            result = (build_answer(body,sources,provider,active,public_demo=True) if kind == "ask" else
                      {"results":sources,"mode":"semantic" if active.api_key else "lexical"})
        except HTTPException as error:
            if error.status_code not in (429,502):
                raise
            active = offline
            notice = "Public AI is temporarily unavailable or its shared allowance is used up. Showing keyword-matched excerpts instead. Try a suggested question or come back later."
            sources = retrieve(store,provider,active,body.query,body.document_ids,body.limit)
            result = (build_answer(body,sources,provider,active,public_demo=True) if kind == "ask" else
                      {"results":sources,"mode":"lexical"})
        result = {**result,"access":"public","cached":False,"notice":notice}
        if settings.api_key and active.api_key:
            remember(key,result)
        return result

    @router.post("/search",dependencies=[Depends(limit),Depends(exclusive)])
    def search(body: Query):
        return execute(body,"search")

    @router.post("/ask",dependencies=[Depends(limit),Depends(exclusive)])
    def ask(body: Question):
        return execute(body,"ask")

    return router
