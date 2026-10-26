
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from fastapi.testclient import TestClient
from src.api import app

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch


client = TestClient(app)


class TestAPI(unittest.TestCase):

    def test_health(self):
        response = client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_search(self):
        response = client.get(
            "/search",
            params={"keyword": "language"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 3)

    def test_empty_keyword(self):
        response = client.get(
            "/search",
            params={"keyword": " "}
        )

        self.assertEqual(response.status_code, 400)

    def test_missing_keyword(self):
        response = client.get("/search")

        self.assertEqual(response.status_code, 422)


    def test_post_search(self):
        response = client.post(
            "/search",
            json={
                "keyword": "Language",
                "case_sensitive": True
            }
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 2)

    def test_post_default_case(self):
        response = client.post(
            "/search",
            json={"keyword": "language"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 3)

    def test_post_empty_keyword(self):
        response = client.post(
            "/search",
            json={"keyword": ""}
        )

        self.assertEqual(response.status_code, 422)

    def test_post_whitespace_keyword(self):
        response = client.post(
            "/search",
            json={"keyword": "   "}
        )

        self.assertEqual(response.status_code, 400)

    def test_post_missing_keyword(self):
        response = client.post(
            "/search",
            json={"case_sensitive": True}
        )

        self.assertEqual(response.status_code, 422)

    
    def test_multi_document_api(self):
        with TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)

            (folder / "first.txt").write_text(
                "Language matters.",
                encoding="utf-8"
            )

            (folder / "second.txt").write_text(
                "We study language.",
                encoding="utf-8"
            )

            with patch("src.api.DATA_DIR", folder):
                response = client.post(
                    "/search/all",
                    json={
                        "keyword": "language",
                        "case_sensitive": False
                    }
                )

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["count"], 2)
            self.assertEqual(
                response.json()["results"][0]["filename"],
                "first.txt"
            )

    def test_multi_document_invalid_keyword(self):
        response = client.post(
            "/search/all",
            json={"keyword": "   "}
        )

        self.assertEqual(response.status_code, 400)


    def test_upload_pdf(self):
        with TemporaryDirectory() as temp_dir:
            with patch(
                "src.documents.UPLOAD_DIR",
                Path(temp_dir)
            ):
                response = client.post(
                    "/documents",
                    files={
                        "file": (
                            "paper.pdf",
                            b"%PDF-1.4\nTest PDF content",
                            "application/pdf"
                        )
                    }
                )

                self.assertEqual(response.status_code, 201)

                body = response.json()
                self.assertEqual(body["filename"], "paper.pdf")
                self.assertEqual(body["status"], "uploaded")

                saved_file = (
                    Path(temp_dir) /
                    f"{body['document_id']}.pdf"
                )

                self.assertTrue(saved_file.exists())
                self.assertEqual(
                    saved_file.read_bytes(),
                    b"%PDF-1.4\nTest PDF content"
                )

    
    def test_document_lifecycle(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from unittest.mock import patch

        with TemporaryDirectory() as temp_dir:
            with patch(
                "src.documents.UPLOAD_DIR",
                Path(temp_dir)
            ):
                # CREATE
                upload_response = client.post(
                    "/documents",
                    files={
                        "file": (
                            "paper.pdf",
                            b"%PDF-1.4\nTest content",
                            "application/pdf"
                        )
                    }
                )

                self.assertEqual(
                    upload_response.status_code, 201
                )

                document_id = upload_response.json()["document_id"]

                # READ ALL
                list_response = client.get("/documents")
                self.assertEqual(list_response.status_code, 200)
                self.assertEqual(
                    len(list_response.json()["documents"]), 1
                )

                # READ ONE
                get_response = client.get(
                    f"/documents/{document_id}"
                )
                self.assertEqual(get_response.status_code, 200)
                self.assertEqual(
                    get_response.json()["filename"],
                    "paper.pdf"
                )

                # DELETE
                delete_response = client.delete(
                    f"/documents/{document_id}"
                )
                self.assertEqual(
                    delete_response.status_code, 200
                )

                # CONFIRM DELETION
                final_response = client.get(
                    f"/documents/{document_id}"
                )
                self.assertEqual(
                    final_response.status_code, 404
                )

if __name__ == "__main__":
    unittest.main()
