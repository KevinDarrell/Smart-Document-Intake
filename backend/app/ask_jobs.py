import uuid
from contextlib import closing
from typing import Optional

import sqlite3
from fastapi import HTTPException

from .citations import validate_citations
from .database import db, now
from .models import TERMINAL_STATUSES


def serialize_job(row: sqlite3.Row):
    with closing(db()) as conn:
        citations, citation_warning = validate_citations(conn, row["answer"] or "", row["status"])
    return {
        "job_id": row["id"],
        "idempotency_key": row["idempotency_key"],
        "question": row["question"],
        "status": row["status"],
        "answer": row["answer"],
        "error": row["error"],
        "citations": citations,
        "citation_warning": citation_warning,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "completed_at": row["completed_at"],
    }


def get_job(job_id: str) -> Optional[sqlite3.Row]:
    with closing(db()) as conn:
        return conn.execute("SELECT * FROM ask_jobs WHERE id = ?", (job_id,)).fetchone()


def job_status(job_id: str):
    row = get_job(job_id)
    return row["status"] if row else None


def mark_job(job_id: str, status: str, error: Optional[str] = None):
    completed_at = now() if status in TERMINAL_STATUSES else None
    with closing(db()) as conn:
        conn.execute(
            """UPDATE ask_jobs
               SET status = ?, error = ?, updated_at = ?, completed_at = COALESCE(?, completed_at)
               WHERE id = ?""",
            (status, error, now(), completed_at, job_id),
        )
        conn.commit()


def append_answer(job_id: str, chunk: str):
    if not chunk:
        return
    with closing(db()) as conn:
        conn.execute(
            "UPDATE ask_jobs SET answer = answer || ?, updated_at = ? WHERE id = ? AND status = 'running'",
            (chunk, now(), job_id),
        )
        conn.commit()


def snapshot_documents(conn: sqlite3.Connection):
    docs = conn.execute("SELECT id, title, body FROM documents WHERE active = 1 ORDER BY id ASC").fetchall()
    if not docs:
        raise HTTPException(status_code=400, detail="No documents ingested yet.")
    return "\n\n".join(f"[doc {d['id']}] {d['title']}\n{d['body']}" for d in docs)


def claim_queued_job(job_id: str) -> Optional[sqlite3.Row]:
    with closing(db()) as conn:
        ts = now()
        cur = conn.execute(
            """UPDATE ask_jobs
               SET status = 'running', error = NULL, updated_at = ?
               WHERE id = ? AND status = 'queued'""",
            (ts, job_id),
        )
        conn.commit()
        if cur.rowcount != 1:
            return None
        return conn.execute("SELECT * FROM ask_jobs WHERE id = ?", (job_id,)).fetchone()


def create_or_get_ask_job(question: str, idempotency_key: str):
    with closing(db()) as conn:
        existing = conn.execute(
            "SELECT * FROM ask_jobs WHERE idempotency_key = ?",
            (idempotency_key,),
        ).fetchone()
        if existing:
            if existing["question"] != question:
                raise HTTPException(
                    status_code=409,
                    detail="Idempotency key already used for a different question.",
                )
            return serialize_job(existing)

        job_id = str(uuid.uuid4())
        ts = now()
        context = snapshot_documents(conn)
        conn.execute(
            """INSERT OR IGNORE INTO ask_jobs
               (id, idempotency_key, question, status, answer, error, context, created_at, updated_at)
               VALUES (?, ?, ?, 'queued', '', NULL, ?, ?, ?)""",
            (job_id, idempotency_key, question, context, ts, ts),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM ask_jobs WHERE idempotency_key = ?",
            (idempotency_key,),
        ).fetchone()
        if row["question"] != question:
            raise HTTPException(
                status_code=409,
                detail="Idempotency key already used for a different question.",
            )
        return serialize_job(row)


def cancel_job(job_id: str):
    row = get_job(job_id)
    if not row:
        raise HTTPException(status_code=404, detail="Ask job not found.")
    if row["status"] in TERMINAL_STATUSES:
        return serialize_job(row)
    mark_job(job_id, "cancelled", "Answer generation was cancelled by the user.")
    return serialize_job(get_job(job_id))
