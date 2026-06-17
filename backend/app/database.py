import sqlite3
import time
from contextlib import closing

from .config import DB_PATH


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
        ensure_column(conn, "documents", "fingerprint", "TEXT")
        ensure_column(conn, "documents", "active", "INTEGER NOT NULL DEFAULT 1")
        ensure_column(conn, "ask_jobs", "context", "TEXT")
        conn.execute(
            """CREATE UNIQUE INDEX IF NOT EXISTS idx_documents_active_fingerprint
               ON documents(fingerprint)
               WHERE active = 1 AND fingerprint IS NOT NULL"""
        )
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
