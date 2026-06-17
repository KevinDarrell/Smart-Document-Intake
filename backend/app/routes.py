import asyncio
import json

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .ask_jobs import cancel_job, create_or_get_ask_job, get_job, serialize_job
from .config import DEEPSEEK_API_KEY, FRONTEND_ORIGIN
from .database import db, init_db, recover_interrupted_jobs
from .documents import (
    archive_active_document,
    document_fingerprint,
    find_active_duplicate,
    insert_document,
    list_documents,
    restore_archived_document,
)
from .llm import summarize_document
from .models import AskReq, IngestReq
from .workers import discard_running_job, ensure_job_running

app = FastAPI(title="Smart Document Intake")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()
recover_interrupted_jobs()


def sse(event: str, data):
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def sse_comment(comment: str):
    return f": {comment}\n\n"


@app.post("/ingest")
def ingest(req: IngestReq):
    fingerprint = document_fingerprint(req.title, req.body)
    duplicate = find_active_duplicate(fingerprint)
    if duplicate:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "This document content is already in the active corpus.",
                "document_id": duplicate["id"],
                "title": duplicate["title"],
            },
        )

    data = summarize_document(req.title, req.body)
    document_id = insert_document(req.title, req.body, data.get("summary"), data.get("facts"), fingerprint)
    return {"id": document_id, "summary": data.get("summary"), "facts": data.get("facts")}


@app.get("/healthz")
def healthz():
    with db() as conn:
        documents_count = conn.execute("SELECT COUNT(*) AS count FROM documents WHERE active = 1").fetchone()["count"]
        status_rows = conn.execute(
            "SELECT status, COUNT(*) AS count FROM ask_jobs GROUP BY status"
        ).fetchall()
    ask_jobs = {status: 0 for status in ["queued", "running", "completed", "failed"]}
    ask_jobs.update({row["status"]: row["count"] for row in status_rows})
    deepseek_configured = bool(DEEPSEEK_API_KEY)
    return {
        "ok": deepseek_configured,
        "database": "ok",
        "deepseek_configured": deepseek_configured,
        "documents": documents_count,
        "ask_jobs": ask_jobs,
    }


@app.get("/documents")
def documents(status: str = "active"):
    return list_documents(status)


@app.delete("/documents/{document_id}")
def archive_document(document_id: int):
    return archive_active_document(document_id)


@app.post("/documents/{document_id}/restore")
def restore_document(document_id: int):
    return restore_archived_document(document_id)


@app.post("/ask")
def ask(req: AskReq):
    job = create_or_get_ask_job(req.question, req.idempotency_key)
    ensure_job_running(job["job_id"])
    return job


@app.post("/ask/{job_id}/cancel")
def cancel_ask(job_id: str):
    job = cancel_job(job_id)
    discard_running_job(job_id)
    return job


@app.get("/ask/{job_id}")
def ask_status(job_id: str):
    row = get_job(job_id)
    if not row:
        raise HTTPException(status_code=404, detail="Ask job not found.")
    ensure_job_running(job_id)
    return serialize_job(get_job(job_id) or row)


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
            if row["status"] in {"failed", "cancelled"}:
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
