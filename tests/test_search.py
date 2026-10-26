
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


if __name__ == "__main__":
    unittest.main()
