
import unittest

from fastapi.testclient import TestClient
from src.api import app


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


if __name__ == "__main__":
    unittest.main()
