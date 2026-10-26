
import json
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile


UPLOAD_DIR = (
    Path(__file__).resolve().parent.parent / "uploads"
)

MAX_FILE_SIZE = 5 * 1024 * 1024


def validate_document_id(document_id: str) -> None:
    if len(document_id) != 32:
        raise HTTPException(400, "Invalid document ID")

    if any(c not in "0123456789abcdef" for c in document_id):
        raise HTTPException(400, "Invalid document ID")


def get_document(document_id: str) -> dict:
    validate_document_id(document_id)

    metadata_path = UPLOAD_DIR / f"{document_id}.json"

    if not metadata_path.is_file():
        raise HTTPException(404, "Document not found")

    return json.loads(metadata_path.read_text(encoding="utf-8"))


def list_documents() -> list[dict]:
    if not UPLOAD_DIR.exists():
        return []

    documents = []

    for metadata_path in sorted(UPLOAD_DIR.glob("*.json")):
        metadata = json.loads(
            metadata_path.read_text(encoding="utf-8")
        )
        documents.append(metadata)

    return documents


async def save_document(file: UploadFile) -> dict:
    filename = file.filename or ""

    if Path(filename).suffix.lower() != ".pdf":
        raise HTTPException(400, "Only PDF files are allowed")

    content = await file.read(MAX_FILE_SIZE + 1)

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(413, "File exceeds 5 MB limit")

    if not content.startswith(b"%PDF-"):
        raise HTTPException(400, "Invalid PDF file")

    document_id = uuid4().hex
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    pdf_path = UPLOAD_DIR / f"{document_id}.pdf"
    metadata_path = UPLOAD_DIR / f"{document_id}.json"

    metadata = {
        "document_id": document_id,
        "filename": Path(filename).name,
        "size_bytes": len(content),
        "status": "uploaded"
    }

    try:
        pdf_path.write_bytes(content)
        metadata_path.write_text(
            json.dumps(metadata, indent=2),
            encoding="utf-8"
        )
    except OSError:
        pdf_path.unlink(missing_ok=True)
        metadata_path.unlink(missing_ok=True)
        raise HTTPException(500, "Could not save document")

    return metadata


def delete_document(document_id: str) -> dict:
    get_document(document_id)

    pdf_path = UPLOAD_DIR / f"{document_id}.pdf"
    metadata_path = UPLOAD_DIR / f"{document_id}.json"

    try:
        pdf_path.unlink(missing_ok=True)
        metadata_path.unlink()
    except OSError:
        raise HTTPException(500, "Could not delete document")

    return {
        "document_id": document_id,
        "status": "deleted"
    }
