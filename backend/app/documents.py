import hashlib
import json
import sqlite3
from contextlib import closing

from fastapi import HTTPException

from .database import db, now


def normalize_document_text(value: str):
    return " ".join(value.strip().split())


def document_fingerprint(title: str, body: str):
    # The active corpus should dedupe by knowledge content, not display title.
    # Titles are user-provided metadata and may be renamed without changing the document.
    normalized = normalize_document_text(body)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def find_active_duplicate(fingerprint: str):
    with closing(db()) as conn:
        return conn.execute(
            "SELECT id, title FROM documents WHERE fingerprint = ? AND active = 1",
            (fingerprint,),
        ).fetchone()


def insert_document(title: str, body: str, summary: str | None, facts, fingerprint: str):
    with closing(db()) as conn:
        try:
            cur = conn.execute(
                "INSERT INTO documents (title, body, summary, facts, created_at, fingerprint, active) VALUES (?,?,?,?,?,?,1)",
                (title, body, summary, json.dumps(facts), now(), fingerprint),
            )
            conn.commit()
            return cur.lastrowid
        except sqlite3.IntegrityError:
            conn.rollback()
            duplicate = conn.execute(
                "SELECT id, title FROM documents WHERE fingerprint = ? AND active = 1",
                (fingerprint,),
            ).fetchone()
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "This document content is already in the active corpus.",
                    "document_id": duplicate["id"] if duplicate else None,
                    "title": duplicate["title"] if duplicate else title,
                },
            )


def list_documents(status: str):
    if status not in {"active", "archived", "all"}:
        raise HTTPException(status_code=400, detail="status must be active, archived, or all.")
    where_clause = {
        "active": "WHERE active = 1",
        "archived": "WHERE active = 0",
        "all": "",
    }[status]
    with closing(db()) as conn:
        rows = conn.execute(
            f"SELECT id, title, summary, active FROM documents {where_clause} ORDER BY id DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def archive_active_document(document_id: int):
    with closing(db()) as conn:
        cur = conn.execute(
            "UPDATE documents SET active = 0 WHERE id = ? AND active = 1",
            (document_id,),
        )
        conn.commit()
    if cur.rowcount != 1:
        raise HTTPException(status_code=404, detail="Active document not found.")
    return {"id": document_id, "active": False}


def restore_archived_document(document_id: int):
    with closing(db()) as conn:
        existing = conn.execute(
            "SELECT id, fingerprint, active FROM documents WHERE id = ?",
            (document_id,),
        ).fetchone()
        if not existing or existing["active"]:
            raise HTTPException(status_code=404, detail="Archived document not found.")
        try:
            cur = conn.execute(
                "UPDATE documents SET active = 1 WHERE id = ? AND active = 0",
                (document_id,),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            conn.rollback()
            raise HTTPException(
                status_code=409,
                detail="This archived document duplicates an active document and cannot be restored.",
            )
    if cur.rowcount != 1:
        raise HTTPException(status_code=404, detail="Archived document not found.")
    return {"id": document_id, "active": True}
