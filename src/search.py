
def search_document(text, keyword):
    results = []

    if not keyword.strip():
        return results

    for line_number, line in enumerate(text.splitlines(), start=1):
        if keyword.lower() in line.lower():
            results.append((line_number, line))

    return results
