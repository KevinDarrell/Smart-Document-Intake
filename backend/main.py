"""
Smart Document Intake — baseline backend.

Ingest a document, summarize it and extract a few fields with an LLM, and answer
questions grounded only in the stored documents (with citations; it says so when
the answer isn't present). See TAKEHOME.md.
"""
import json
import os
import sqlite3
import time
from contextlib import closing

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from pydantic import BaseModel

DB_PATH = os.environ.get("DB_PATH", "intake.db")
MODEL = "deepseek-chat"

client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
    base_url="https://api.deepseek.com",
)

app = FastAPI(title="Smart Document Intake")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with closing(db()) as conn:
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
        conn.commit()


init_db()


class IngestReq(BaseModel):
    title: str
    body: str


class AskReq(BaseModel):
    question: str


@app.post("/ingest")
def ingest(req: IngestReq):
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
            (req.title, req.body, data.get("summary"), json.dumps(data.get("facts")), time.time()),
        )
        conn.commit()
        return {"id": cur.lastrowid, "summary": data.get("summary"), "facts": data.get("facts")}


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
        docs = conn.execute("SELECT id, title, body FROM documents").fetchall()
    if not docs:
        raise HTTPException(status_code=400, detail="No documents ingested yet.")
    context = "\n\n".join(f"[doc {d['id']}] {d['title']}\n{d['body']}" for d in docs)
    prompt = (
        "Answer the question using ONLY the documents below. Cite the doc ids you used. "
        "If the answer is not in the documents, say you don't know.\n\n"
        f"{context}\n\nQUESTION: {req.question}"
    )
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    return {"answer": resp.choices[0].message.content}
