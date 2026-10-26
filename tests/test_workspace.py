"""Integration tests use real PDF parsing and SQLite; providers are isolated doubles."""

import io
import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from src.app import create_app
from src.config import Settings
from src.rag import Provider
from src.store import Store


def pdf_bytes(
    text="Language and identity are connected. Bilingual speakers express culture.",
):
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject(
                {NameObject("/F1"): writer._add_object(font)}
            )
        }
    )
    stream = DecodedStreamObject()
    stream.set_data(("BT /F1 12 Tf 40 740 Td (" + text + ") Tj ET").encode())
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


@pytest.fixture
def settings(tmp_path):
    return Settings(
        database_path=str(tmp_path / "db.sqlite"),
        demo_seed=False,
        token="",
        api_key="",
        production=False,
    )


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as client:
        yield client


def upload(client, data=None, name="paper.pdf"):
    return client.post(
        "/api/documents",
        files={
            "file": (name, data if data is not None else pdf_bytes(), "application/pdf")
        },
    )


def test_full_document_lifecycle_and_restart(client, settings):
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/api/documents").json()["documents"] == []
    response = upload(client)
    assert response.status_code == 201, response.text
    doc = response.json()
    doc_id = doc["id"]
    assert doc["pages"] == 1 and doc["chunks"] == 1
    assert client.get(f"/api/documents/{doc_id}/file").content == pdf_bytes()
    assert (
        "identity"
        in client.get(f"/api/documents/{doc_id}").json()["passages"][0]["text"]
    )
    restarted = TestClient(create_app(settings))
    assert len(restarted.get("/api/documents").json()["documents"]) == 1
    assert (
        client.patch(
            f"/api/documents/{doc_id}", json={"title": "My research"}
        ).status_code
        == 200
    )
    assert client.get("/api/documents").json()["documents"][0]["title"] == "My research"
    assert client.delete(f"/api/documents/{doc_id}").status_code == 200
    assert client.get(f"/api/documents/{doc_id}").status_code == 404
    assert (
        client.post("/api/search", json={"query": "identity"}).json()["results"] == []
    )
    with Store(settings.database_path).db() as db:
        assert db.execute("SELECT count(*) FROM chunks").fetchone()[0] == 0


@pytest.mark.parametrize(
    "data,name,status",
    [
        (b"hello", "fake.pdf", 400),
        (b"%PDF-1.4\nnot a real PDF", "fake.pdf", 400),
        (b"hello", "notes.txt", 400),
        (b"%PDF-" + b"x" * 5 * 1024 * 1024, "big.pdf", 413),
    ],
)
def test_invalid_uploads(client, data, name, status):
    assert upload(client, data, name).status_code == status
    assert client.get("/api/documents").json()["documents"] == []


def test_scanned_pdf(client):
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    out = io.BytesIO()
    writer.write(out)
    response = upload(client, out.getvalue())
    assert response.status_code == 400
    assert "OCR" in response.text


def test_duplicates_and_safe_names(client):
    response = upload(client, name="../../paper.pdf")
    assert response.status_code == 201
    assert response.json()["filename"] == "paper.pdf"
    assert upload(client).status_code == 409


def test_search_and_citations(client):
    doc = upload(client).json()
    result = client.post("/api/search", json={"query": "identity"}).json()
    assert result["mode"] == "lexical" and result["results"][0]["page"] == 1
    answer = client.post("/api/ask", json={"query": "identity"}).json()
    assert answer["mode"] == "demo" and "[1]" in answer["answer"]
    assert answer["citations"][0]["document_id"] == doc["id"]
    assert client.post("/api/ask", json={"query": "penguins"}).json()["citations"] == []
    assert (
        client.post(
            "/api/search", json={"query": "identity", "document_ids": ["missing"]}
        ).status_code
        == 404
    )
    assert client.post("/api/search", json={"query": "  "}).status_code == 422
    assert client.post("/api/search", json={"query": "a" * 1501}).status_code == 422
    assert (
        client.post("/api/search", json={"query": "identity", "limit": 100}).status_code
        == 422
    )


def test_scope(client):
    first = upload(client).json()
    second = upload(client, pdf_bytes("Privacy is important."), "privacy.pdf").json()
    result = client.post(
        "/api/search", json={"query": "identity", "document_ids": [second["id"]]}
    ).json()
    assert result["results"] == []
    assert client.post(
        "/api/search", json={"query": "identity", "document_ids": [first["id"]]}
    ).json()["results"]


def test_auth_and_production_fail_closed(settings):
    settings.production = True
    with pytest.raises(RuntimeError):
        create_app(settings)
    settings.token = "x" * 32
    client = TestClient(create_app(settings))
    assert client.get("/health").status_code == 200
    assert client.get("/api/config").json()["auth_required"]
    assert client.get("/api/documents").status_code == 401
    assert upload(client).status_code == 401
    assert client.get("/docs").status_code == 404
    assert (
        client.get(
            "/api/documents", headers={"Authorization": "Bearer " + settings.token}
        ).status_code
        == 200
    )
    assert "api_key" not in client.get("/api/config").text


def test_rate_limit(client):
    for _ in range(60):
        assert client.get("/api/documents").status_code == 200
    assert client.get("/api/documents").status_code == 429


def test_seed_is_idempotent(settings):
    settings.demo_seed = True
    one = TestClient(create_app(settings))
    two = TestClient(create_app(settings))
    assert len(one.get("/api/documents").json()["documents"]) == 3
    assert len(two.get("/api/documents").json()["documents"]) == 3
    assert one.get("/api/documents").headers["cache-control"] == "no-store"


class FakeProvider:
    def __init__(self):
        self.calls = []

    def embed(self, texts):
        self.calls.extend(texts)
        return [
            [1.0, 0.0] if ("identity" in t or "身份" in t) else [0.0, 1.0]
            for t in texts
        ]

    def answer(self, question, sources, language):
        return "语言与身份相连。 [1]", [1]


def test_multilingual_semantic_path_and_embedding_cache(settings):
    settings.api_key = "test-only"
    provider = FakeProvider()
    client = TestClient(create_app(settings, provider))
    upload(client)
    assert len(provider.calls) == 1
    query = {"query": "身份是什么？"}
    response = client.post("/api/ask", json=query)
    assert response.status_code == 200, response.text
    assert response.json()["citations"][0]["page"] == 1
    assert response.json()["mode"] == "ai"
    assert len(provider.calls) == 2  # PDF vector reused; only the query is embedded.
    assert client.post("/api/search", json=query).json()["results"][0]["score"] == 0.85
    assert len(provider.calls) == 3


def test_provider_failure_leaves_no_partial_document(settings):
    class Failed:
        def embed(self, texts):
            raise HTTPException(502, "Provider unavailable")

    settings.api_key = "test-only"
    client = TestClient(create_app(settings, Failed()))
    assert upload(client).status_code == 502
    assert client.get("/api/documents").json()["documents"] == []


@pytest.mark.parametrize(
    "payload",
    [
        {"answer": "Made up [99]", "citation_ids": [99]},
        {"answer": "No marker", "citation_ids": [1]},
        {"answer": "Unknown [1]", "citation_ids": []},
    ],
)
def test_reject_invalid_model_citations(settings, monkeypatch, payload):
    provider = Provider(settings)
    monkeypatch.setattr(
        provider,
        "post",
        lambda *args: {"choices": [{"message": {"content": json.dumps(payload)}}]},
    )
    with pytest.raises(HTTPException):
        provider.answer(
            "Question", [{"title": "Paper", "page": 1, "text": "Evidence"}], "English"
        )


def test_atomic_duplicate_constraint(settings):
    store = Store(settings.database_path)

    def add():
        try:
            store.add("Paper", "paper.txt", [(1, "Evidence")], "same-hash")
            return True
        except Exception:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(lambda _: add(), range(2))) == 1
    assert len(store.list()) == 1


def test_seeded_document_deletion_survives_restart(settings):
    settings.demo_seed = True
    client = TestClient(create_app(settings))
    doc = client.get("/api/documents").json()["documents"][0]
    assert client.delete("/api/documents/" + doc["id"]).status_code == 200
    restarted = TestClient(create_app(settings))
    assert len(restarted.get("/api/documents").json()["documents"]) == 2


def test_multipart_body_limit(client):
    response = upload(client, b"%PDF-" + b"x" * (6 * 1024 * 1024))
    assert response.status_code == 413


def test_encrypted_pdf(client):
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.encrypt("secret")
    output = io.BytesIO()
    writer.write(output)
    response = upload(client, output.getvalue())
    assert response.status_code == 400 and "Password-protected" in response.text


def test_page_limit(client):
    writer = PdfWriter()
    for _ in range(101):
        writer.add_blank_page(width=100, height=100)
    output = io.BytesIO()
    writer.write(output)
    assert upload(client, output.getvalue()).status_code == 400


def test_page_count_includes_blank_trailing_pages(client):
    writer = PdfWriter()
    writer.append(PdfReader(io.BytesIO(pdf_bytes())))
    writer.add_blank_page(width=612, height=792)
    output = io.BytesIO()
    writer.write(output)
    response = upload(client, output.getvalue())
    assert response.status_code == 201
    assert response.json()["pages"] == 2
    assert response.json()["chunks"] == 1
