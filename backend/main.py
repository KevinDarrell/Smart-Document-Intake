"""
Smart Document Intake — baseline backend.

Ingest a document, summarize it and extract a few fields with an LLM, and answer
questions grounded only in the stored documents (with citations; it says so when
the answer isn't present). See TAKEHOME.md.
"""
import asyncio
import json
import os
import sqlite3
import threading
import time
import uuid
from contextlib import closing
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from openai import OpenAI
from pydantic import BaseModel, Field

DB_PATH = os.environ.get("DB_PATH", "intake.db")
MODEL = "deepseek-chat"
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
TERMINAL_STATUSES = {"completed", "failed"}

client = OpenAI(
    api_key=DEEPSEEK_API_KEY or "missing-key",
    base_url="https://api.deepseek.com",
)

app = FastAPI(title="Smart Document Intake")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

running_jobs: set[str] = set()
running_jobs_lock = threading.Lock()


def db():
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def now():
    return time.time()


def ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str):
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db():
    with closing(db()) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(
            """CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                summary TEXT,
                facts TEXT,
                created_at REAL
            )"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS ask_jobs (
                id TEXT PRIMARY KEY,
                idempotency_key TEXT NOT NULL UNIQUE,
                question TEXT NOT NULL,
                status TEXT NOT NULL,
                answer TEXT NOT NULL DEFAULT '',
                error TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                completed_at REAL
            )"""
        )
        ensure_column(conn, "ask_jobs", "context", "TEXT")
        conn.commit()


def recover_interrupted_jobs():
    with closing(db()) as conn:
        ts = now()
        conn.execute(
            """UPDATE ask_jobs
               SET status = 'failed',
                   error = 'Server restarted while this answer was generating. Please ask again.',
                   updated_at = ?,
                   completed_at = ?
               WHERE status = 'running'""",
            (ts, ts),
        )
        conn.commit()


init_db()
recover_interrupted_jobs()


class IngestReq(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    body: str = Field(min_length=1, max_length=50_000)


class AskReq(BaseModel):
    question: str = Field(min_length=1, max_length=2_000)
    idempotency_key: str = Field(min_length=8, max_length=200)


def serialize_job(row: sqlite3.Row):
    return {
        "job_id": row["id"],
        "idempotency_key": row["idempotency_key"],
        "question": row["question"],
        "status": row["status"],
        "answer": row["answer"],
        "error": row["error"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "completed_at": row["completed_at"],
    }


def get_job(job_id: str) -> Optional[sqlite3.Row]:
    with closing(db()) as conn:
        return conn.execute("SELECT * FROM ask_jobs WHERE id = ?", (job_id,)).fetchone()


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
    docs = conn.execute("SELECT id, title, body FROM documents ORDER BY id ASC").fetchall()
    if not docs:
        raise HTTPException(status_code=400, detail="No documents ingested yet.")
    return "\n\n".join(f"[doc {d['id']}] {d['title']}\n{d['body']}" for d in docs)


def require_deepseek_key():
    if not DEEPSEEK_API_KEY:
        raise RuntimeError("DEEPSEEK_API_KEY is not configured.")


def build_answer_prompt(question: str, context: str):
    return (
        "Answer the question using ONLY the documents below. Cite the doc ids you used. "
        "If the answer is not in the documents, say you don't know. "
        "Do not use outside knowledge. Keep citations inline like [doc 1].\n\n"
        f"{context}\n\nQUESTION: {question}"
    )


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


def generate_answer(job_id: str):
    try:
        row = claim_queued_job(job_id)
        if not row:
            return
        require_deepseek_key()
        prompt = build_answer_prompt(row["question"], row["context"] or "")
        stream = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            stream=True,
        )
        saw_content = False
        for event in stream:
            delta = event.choices[0].delta.content if event.choices else None
            if delta:
                saw_content = True
                append_answer(job_id, delta)
        if not saw_content:
            append_answer(job_id, "(No answer was generated.)")
        mark_job(job_id, "completed")
    except Exception as exc:
        mark_job(job_id, "failed", str(exc))
    finally:
        with running_jobs_lock:
            running_jobs.discard(job_id)


def ensure_job_running(job_id: str):
    row = get_job(job_id)
    if not row or row["status"] != "queued":
        return
    with running_jobs_lock:
        if job_id in running_jobs:
            return
        running_jobs.add(job_id)
    thread = threading.Thread(target=generate_answer, args=(job_id,), daemon=True)
    thread.start()


def sse(event: str, data):
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def sse_comment(comment: str):
    return f": {comment}\n\n"


@app.post("/ingest")
def ingest(req: IngestReq):
    try:
        require_deepseek_key()
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    prompt = (
        "Summarize the document in one sentence and extract exactly 3 key facts. "
        'Return JSON: {"summary": string, "facts": [string, string, string]}.\n\n'
        f"TITLE: {req.title}\n\nBODY:\n{req.body}"
    )
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    data = json.loads(resp.choices[0].message.content)
    with closing(db()) as conn:
        cur = conn.execute(
            "INSERT INTO documents (title, body, summary, facts, created_at) VALUES (?,?,?,?,?)",
            (req.title, req.body, data.get("summary"), json.dumps(data.get("facts")), now()),
        )
        conn.commit()
        return {"id": cur.lastrowid, "summary": data.get("summary"), "facts": data.get("facts")}


@app.get("/healthz")
def healthz():
    with closing(db()) as conn:
        documents_count = conn.execute("SELECT COUNT(*) AS count FROM documents").fetchone()["count"]
        status_rows = conn.execute(
            "SELECT status, COUNT(*) AS count FROM ask_jobs GROUP BY status"
        ).fetchall()
    ask_jobs = {status: 0 for status in ["queued", "running", "completed", "failed"]}
    ask_jobs.update({row["status"]: row["count"] for row in status_rows})
    return {
        "ok": True,
        "database": "ok",
        "deepseek_configured": bool(DEEPSEEK_API_KEY),
        "documents": documents_count,
        "ask_jobs": ask_jobs,
    }


@app.get("/documents")
def documents():
    with closing(db()) as conn:
        rows = conn.execute(
            "SELECT id, title, summary FROM documents ORDER BY id DESC"
        ).fetchall()
        return [dict(r) for r in rows]


@app.post("/ask")
def ask(req: AskReq):
    with closing(db()) as conn:
        job_id = str(uuid.uuid4())
        ts = now()
        context = snapshot_documents(conn)
        conn.execute(
            """INSERT OR IGNORE INTO ask_jobs
               (id, idempotency_key, question, status, answer, error, context, created_at, updated_at)
               VALUES (?, ?, ?, 'queued', '', NULL, ?, ?, ?)""",
            (job_id, req.idempotency_key, req.question, context, ts, ts),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM ask_jobs WHERE idempotency_key = ?",
            (req.idempotency_key,),
        ).fetchone()
        job = serialize_job(row)
    ensure_job_running(job["job_id"])
    return job


@app.get("/ask/{job_id}")
def ask_status(job_id: str):
    row = get_job(job_id)
    if not row:
        raise HTTPException(status_code=404, detail="Ask job not found.")
    ensure_job_running(job_id)
    return serialize_job(row)


@app.get("/ask/{job_id}/stream")
async def ask_stream(job_id: str):
    if not get_job(job_id):
        raise HTTPException(status_code=404, detail="Ask job not found.")
    ensure_job_running(job_id)

    async def events():
        sent_len = 0
        last_status = None
        while True:
            row = get_job(job_id)
            if not row:
                yield sse("error", {"error": "Ask job not found."})
                return

            answer = row["answer"] or ""
            if sent_len == 0 or row["status"] != last_status:
                yield sse("status", serialize_job(row))
                last_status = row["status"]
            if len(answer) > sent_len:
                chunk = answer[sent_len:]
                sent_len = len(answer)
                yield sse("chunk", {"chunk": chunk, "answer": answer})
            else:
                yield sse_comment("heartbeat")

            if row["status"] == "completed":
                yield sse("done", serialize_job(row))
                return
            if row["status"] == "failed":
                yield sse("error", serialize_job(row))
                return

            await asyncio.sleep(0.25)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
