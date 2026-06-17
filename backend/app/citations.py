import re

CITATION_PATTERN = re.compile(r"\[\s*doc\s+(\d+)\s*\]", re.IGNORECASE)


def extract_cited_doc_ids(answer: str):
    seen = set()
    doc_ids = []
    for match in CITATION_PATTERN.finditer(answer or ""):
        doc_id = int(match.group(1))
        if doc_id not in seen:
            seen.add(doc_id)
            doc_ids.append(doc_id)
    return doc_ids


def source_snippet(body: str, max_chars: int = 240):
    text = " ".join((body or "").split())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def validate_citations(conn, answer: str, status: str):
    doc_ids = extract_cited_doc_ids(answer)
    if not doc_ids:
        warning = "No document citations were found in the completed answer." if status == "completed" else None
        return [], warning

    placeholders = ",".join("?" for _ in doc_ids)
    rows = conn.execute(
        f"SELECT id, title, body FROM documents WHERE id IN ({placeholders})",
        doc_ids,
    ).fetchall()
    docs_by_id = {row["id"]: row for row in rows}
    citations = [
        {
            "doc_id": doc_id,
            "title": docs_by_id[doc_id]["title"] if doc_id in docs_by_id else None,
            "valid": doc_id in docs_by_id,
            "snippet": source_snippet(docs_by_id[doc_id]["body"]) if doc_id in docs_by_id else None,
        }
        for doc_id in doc_ids
    ]
    missing = [doc_id for doc_id in doc_ids if doc_id not in docs_by_id]
    warning = None
    if missing:
        warning = "Some cited documents were not found: " + ", ".join(f"doc {doc_id}" for doc_id in missing) + "."
    return citations, warning
