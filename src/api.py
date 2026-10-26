
from fastapi import UploadFile
from src.documents import (
    save_document,
    list_documents,
    get_document,
    delete_document,
)
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.search import search_document, search_all_documents

app = FastAPI(title="LinguaSearch API")

DATA_FILE = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "linguistics.txt"
)
DATA_DIR = DATA_FILE.parent

# Define the expected JSON request body
class SearchRequest(BaseModel):
    keyword: str = Field(min_length=1)
    case_sensitive: bool = False


def perform_search(
    keyword: str,
    case_sensitive: bool = False
):
    if not keyword.strip():
        raise HTTPException(
            status_code=400,
            detail="Keyword cannot be empty"
        )

    text = DATA_FILE.read_text(encoding="utf-8")

    matches = search_document(
        text,
        keyword,
        case_sensitive=case_sensitive
    )

    results = [
        {"line": line_number, "text": line}
        for line_number, line in matches
    ]

    return {
        "keyword": keyword,
        "case_sensitive": case_sensitive,
        "count": len(results),
        "results": results
    }


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/search")
def get_search(keyword: str):
    return perform_search(keyword)


@app.post("/search")
def post_search(request: SearchRequest):
    return perform_search(
        request.keyword,
        case_sensitive=request.case_sensitive
    )

@app.post("/search/all")
def post_search_all(request: SearchRequest):
    if not request.keyword.strip():
        raise HTTPException(
            status_code=400,
            detail="Keyword cannot be empty"
        )

    results = search_all_documents(
        folder_path=str(DATA_DIR),
        keyword=request.keyword,
        case_sensitive=request.case_sensitive
    )

    return {
        "keyword": request.keyword,
        "case_sensitive": request.case_sensitive,
        "count": len(results),
        "results": results
    }

@app.post("/documents", status_code=201)
async def upload_document(file: UploadFile):
    return await save_document(file)


@app.get("/documents")
def get_documents():
    return {
        "documents": list_documents()
    }


@app.get("/documents/{document_id}")
def get_document_by_id(document_id: str):
    return get_document(document_id)


@app.delete("/documents/{document_id}")
def remove_document(document_id: str):
    return delete_document(document_id)
