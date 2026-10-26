
from pathlib import Path
from src.search import search_document


def main():
    file_path = Path(__file__).resolve().parent.parent / "data" / "linguistics.txt"

    with open(file_path, "r", encoding="utf-8") as file:
        text = file.read()

    print("Welcome to LinguaSearch v0.1!")

    keyword = input("Enter a keyword to search: ")

    if not keyword.strip():
        print("Please enter a keyword.")
        return

    results = search_document(text, keyword)

    print(f"\nFound {len(results)} matching lines:")

    for line_number, line in results:
        print(f"[Line {line_number}] {line}")


if __name__ == "__main__":
    main()
