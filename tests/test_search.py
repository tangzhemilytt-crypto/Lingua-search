
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



if __name__ == "__main__":
    unittest.main()
