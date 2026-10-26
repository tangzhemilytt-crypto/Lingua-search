"""Isolated PDF parser: bounded time by parent, memory/CPU on Unix."""

import io
import json
import sys


def extract(content):
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(content), strict=False)
    if reader.is_encrypted:
        raise ValueError("Password-protected PDFs are not supported.")
    if len(reader.pages) > 100:
        raise ValueError("Please upload a PDF with at most 100 pages.")
    chunks = []
    total = 0
    for number, page in enumerate(reader.pages, 1):
        text = (page.extract_text() or "").replace("\x00", "").strip()
        total += len(text)
        if total > 300_000:
            raise ValueError("PDF contains too much text (300,000 characters maximum).")
        for start in range(0, len(text), 950):
            passage = text[start : start + 1100].strip()
            if passage:
                chunks.append((number, passage))
    if not chunks:
        raise ValueError("No readable text found. Scanned PDFs need OCR before upload.")
    return chunks


if __name__ == "__main__":
    try:
        try:
            import resource

            resource.setrlimit(
                resource.RLIMIT_AS, (768 * 1024 * 1024, 768 * 1024 * 1024)
            )
            resource.setrlimit(resource.RLIMIT_CPU, (15, 15))
        except (ImportError, ValueError, OSError):
            pass
        print(json.dumps({"chunks": extract(sys.stdin.buffer.read())}))
    except Exception as exc:
        print(json.dumps({"error": str(exc)[:240]}))
        sys.exit(1)
