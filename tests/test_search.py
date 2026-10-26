
from pathlib import Path
from tempfile import TemporaryDirectory

from src.search import search_document, search_all_documents
import unittest

from src.search import search_document


class TestSearchDocument(unittest.TestCase):

    def test_normal_search(self):
        text = "Hello world\nPython is fun"
        result = search_document(text, "Python")
        self.assertEqual(result, [(2, "Python is fun")])

    def test_case_insensitive(self):
        text = "LANGUAGE is important"
        result = search_document(text, "language")
        self.assertEqual(result, [(1, "LANGUAGE is important")])

    def test_no_match(self):
        text = "I study linguistics"
        result = search_document(text, "biology")
        self.assertEqual(result, [])

    def test_empty_input(self):
        text = "Hello world"
        result = search_document(text, "")
        self.assertEqual(result, [])

    def test_whitespace(self):
        text = "Hello world"
        result = search_document(text, "   ")
        self.assertEqual(result, [])

    
    def test_case_sensitive_search(self):
        text = "Language\nlanguage\nLANGUAGE"

        result = search_document(
            text,
            "language",
            case_sensitive=True
        )

        self.assertEqual(
            result,
            [(2, "language")]
        )

    def test_case_insensitive_explicit(self):
        text = "Language\nlanguage\nLANGUAGE"

        result = search_document(
            text,
            "language",
            case_sensitive=False
        )

        self.assertEqual(len(result), 3)


    def test_multi_document_search(self):
        results = search_all_documents("data", "language")

        filenames = [result["filename"] for result in results]

        self.assertIn("linguistics.txt", filenames)
        self.assertIn("identity.txt", filenames)
        self.assertIn("ai.txt", filenames)

    
    def test_multi_document_with_temp_directory(self):
        with TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)

            (folder / "first.txt").write_text(
                "Language is powerful.\nPython is useful.",
                encoding="utf-8"
            )

            (folder / "second.txt").write_text(
                "I study language and identity.",
                encoding="utf-8"
            )

            (folder / "ignore.pdf").write_text(
                "Language appears here too.",
                encoding="utf-8"
            )

            results = search_all_documents(
                temp_dir,
                "language"
            )

            self.assertEqual(len(results), 2)

            self.assertEqual(
                [result["filename"] for result in results],
                ["first.txt", "second.txt"]
            )

            self.assertEqual(
                results[0]["line"],
                1
            )

if __name__ == "__main__":
    unittest.main()