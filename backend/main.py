"""
Smart Document Intake backend.

Compatibility entrypoint for `uvicorn main:app --reload --port 8000`.
The implementation lives in the `app` package so routes, persistence, workers,
and provider code can be reviewed independently.
"""
from app import config, routes
from app.ask_jobs import append_answer, claim_queued_job, get_job, job_status, mark_job, serialize_job
from app.citations import extract_cited_doc_ids, source_snippet, validate_citations
from app.config import DEEPSEEK_API_KEY, FRONTEND_ORIGIN, MODEL, client, require_deepseek_key
from app.database import db, ensure_column, init_db, now, recover_interrupted_jobs
from app.documents import document_fingerprint, normalize_document_text
from app.llm import build_answer_prompt
from app.models import AskReq, IngestReq, TERMINAL_STATUSES
from app.routes import app, ask, ask_status, ask_stream, cancel_ask, documents, healthz, ingest
from app.workers import ensure_job_running, generate_answer, running_jobs, running_jobs_lock
