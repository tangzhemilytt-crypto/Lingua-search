
def search_document(
    text: str,
    keyword: str,
    case_sensitive: bool = False
) -> list[tuple[int, str]]:

    results = []

    if not keyword.strip():
        return results

    if case_sensitive:
        search_keyword = keyword
    else:
        search_keyword = keyword.lower()

    for line_number, line in enumerate(
        text.splitlines(), start=1
    ):
        if case_sensitive:
            search_line = line
        else:
            search_line = line.lower()

        if search_keyword in search_line:
            results.append((line_number, line))

    return results
