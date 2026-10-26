

from pathlib import Path

from fastapi import FastAPI, HTTPException

from src.search import search_document


app = FastAPI(title="LinguaSearch API")

DATA_FILE = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "linguistics.txt"
)


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/search")
def search(keyword: str):
    if not keyword.strip():
        raise HTTPException(
            status_code=400,
            detail="Keyword cannot be empty"
        )

    text = DATA_FILE.read_text(encoding="utf-8")
    matches = search_document(text, keyword)

    results = [
        {"line": line_number, "text": line}
        for line_number, line in matches
    ]

    return {
        "keyword": keyword,
        "count": len(results),
        "results": results
    }
