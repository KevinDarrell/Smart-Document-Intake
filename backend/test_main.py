import importlib
import os
import shutil
import sqlite3
import sys
import tempfile
import time
import unittest

from fastapi.testclient import TestClient


class FakeMessage:
    content = '{"summary": "Duplicate test summary.", "facts": ["one", "two", "three"]}'


class FakeChoice:
    message = FakeMessage()


class FakeCompletion:
    choices = [FakeChoice()]


class FakeChatCompletions:
    def __init__(self):
        self.calls = 0

    def create(self, **kwargs):
        self.calls += 1
        return FakeCompletion()


class FakeChat:
    def __init__(self):
        self.completions = FakeChatCompletions()


class FakeClient:
    def __init__(self):
        self.chat = FakeChat()


class BackendBehaviorTests(unittest.TestCase):
    def setUp(self):
        if os.path.dirname(__file__) not in sys.path:
            sys.path.insert(0, os.path.dirname(__file__))
        self.tmp_dir = tempfile.mkdtemp(prefix="smart-intake-test-")
        os.environ["DB_PATH"] = os.path.join(self.tmp_dir, "test.db")
        os.environ["DEEPSEEK_API_KEY"] = "test-key"
        os.environ["FRONTEND_ORIGIN"] = "http://localhost:3000"
        for module_name in list(sys.modules):
            if module_name == "main" or module_name == "app" or module_name.startswith("app."):
                sys.modules.pop(module_name, None)
        self.main = importlib.import_module("main")
        self.main.routes.ensure_job_running = lambda job_id: None
        self.client = TestClient(self.main.app)
        self.seed_document()

    def tearDown(self):
        for module_name in list(sys.modules):
            if module_name == "main" or module_name == "app" or module_name.startswith("app."):
                sys.modules.pop(module_name, None)
        try:
            shutil.rmtree(self.tmp_dir)
        except PermissionError:
            pass

    def seed_document(self):
        with sqlite3.connect(os.environ["DB_PATH"]) as conn:
            conn.execute(
                "INSERT INTO documents (title, body, summary, facts, created_at, fingerprint, active) VALUES (?, ?, ?, ?, ?, ?, 1)",
                (
                    "Policy",
                    "Employees get 12 days of annual leave.",
                    "Leave policy.",
                    "[]",
                    time.time(),
                    self.main.document_fingerprint("Policy", "Employees get 12 days of annual leave."),
                ),
            )
            conn.commit()

    def ask(self, question="How many leave days?", key="same-key-123"):
        return self.client.post("/ask", json={"question": question, "idempotency_key": key})

    def test_same_idempotency_key_returns_same_job(self):
        first = self.ask()
        second = self.ask()

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()["job_id"], second.json()["job_id"])

        with sqlite3.connect(os.environ["DB_PATH"]) as conn:
            count = conn.execute("SELECT COUNT(*) FROM ask_jobs").fetchone()[0]
        self.assertEqual(count, 1)

    def test_same_idempotency_key_different_question_conflicts(self):
        first = self.ask(question="How many leave days?", key="conflict-key-123")
        conflict = self.ask(question="What are working hours?", key="conflict-key-123")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(conflict.status_code, 409)

    def test_healthz_reports_readiness(self):
        response = self.client.get("/healthz")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["ok"])
        self.assertTrue(body["deepseek_configured"])
        self.assertEqual(body["database"], "ok")

    def test_duplicate_ingest_returns_conflict_without_second_llm_call(self):
        fake_client = FakeClient()
        self.main.config.client = fake_client
        payload = {"title": "Duplicate", "body": "Same body text."}

        first = self.client.post("/ingest", json=payload)
        second = self.client.post("/ingest", json=payload)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 409)
        self.assertEqual(fake_client.chat.completions.calls, 1)
        self.assertEqual(second.json()["detail"]["message"], "This document content is already in the active corpus.")

    def test_duplicate_ingest_rejects_same_body_with_different_title(self):
        fake_client = FakeClient()
        self.main.config.client = fake_client

        first = self.client.post("/ingest", json={"title": "Duplicate A", "body": "Same body text."})
        second = self.client.post("/ingest", json={"title": "Duplicate B 123", "body": "Same body text."})

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 409)
        self.assertEqual(fake_client.chat.completions.calls, 1)
        self.assertEqual(second.json()["detail"]["message"], "This document content is already in the active corpus.")

    def test_duplicate_ingest_allows_same_title_with_different_body(self):
        fake_client = FakeClient()
        self.main.config.client = fake_client

        first = self.client.post("/ingest", json={"title": "Policy", "body": "First policy body."})
        second = self.client.post("/ingest", json={"title": "Policy", "body": "Second policy body."})

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(fake_client.chat.completions.calls, 2)

    def test_archive_document_hides_it_from_active_documents(self):
        response = self.client.delete("/documents/1")
        documents = self.client.get("/documents")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"id": 1, "active": False})
        self.assertEqual(documents.json(), [])

    def test_archived_documents_are_visible_and_restorable(self):
        archive = self.client.delete("/documents/1")
        archived = self.client.get("/documents?status=archived")
        restore = self.client.post("/documents/1/restore")
        active = self.client.get("/documents?status=active")

        self.assertEqual(archive.status_code, 200)
        self.assertEqual(archived.status_code, 200)
        self.assertEqual(archived.json()[0]["id"], 1)
        self.assertEqual(archived.json()[0]["active"], 0)
        self.assertEqual(restore.status_code, 200)
        self.assertEqual(restore.json(), {"id": 1, "active": True})
        self.assertEqual(active.json()[0]["id"], 1)
        self.assertEqual(active.json()[0]["active"], 1)

    def test_restore_duplicate_archived_document_conflicts(self):
        fingerprint = self.main.document_fingerprint("Policy", "Employees get 12 days of annual leave.")
        with sqlite3.connect(os.environ["DB_PATH"]) as conn:
            conn.execute(
                "INSERT INTO documents (title, body, summary, facts, created_at, fingerprint, active) VALUES (?, ?, ?, ?, ?, ?, 0)",
                ("Policy Copy", "Employees get 12 days of annual leave.", "Archived duplicate.", "[]", time.time(), fingerprint),
            )
            archived_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.commit()

        response = self.client.post(f"/documents/{archived_id}/restore")

        self.assertEqual(response.status_code, 409)
        self.assertIn("duplicates an active document", response.json()["detail"])

    def test_archived_documents_are_excluded_from_ask_context(self):
        with sqlite3.connect(os.environ["DB_PATH"]) as conn:
            conn.execute(
                "INSERT INTO documents (title, body, summary, facts, created_at) VALUES (?, ?, ?, ?, ?)",
                ("Security", "MFA is required for staff accounts.", "Security policy.", "[]", time.time()),
            )
            conn.commit()

        archive = self.client.delete("/documents/1")
        ask = self.ask(question="What is required for staff accounts?", key="archive-context-key")

        self.assertEqual(archive.status_code, 200)
        self.assertEqual(ask.status_code, 200)
        with sqlite3.connect(os.environ["DB_PATH"]) as conn:
            context = conn.execute(
                "SELECT context FROM ask_jobs WHERE id = ?",
                (ask.json()["job_id"],),
            ).fetchone()[0]
        self.assertNotIn("Employees get 12 days", context)
        self.assertIn("MFA is required", context)

    def test_cancel_queued_job_marks_it_cancelled(self):
        ask = self.ask(question="Cancel this?", key="cancel-key-123")

        response = self.client.post(f"/ask/{ask.json()['job_id']}/cancel")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "cancelled")
        self.assertIn("cancelled", body["error"])

    def test_cancelled_job_stream_emits_terminal_payload(self):
        ask = self.ask(question="Cancel stream?", key="cancel-stream-key")
        self.client.post(f"/ask/{ask.json()['job_id']}/cancel")

        response = self.client.get(f"/ask/{ask.json()['job_id']}/stream")

        self.assertEqual(response.status_code, 200)
        self.assertIn('"status": "cancelled"', response.text)
        self.assertIn("event: error", response.text)

    def test_generate_answer_does_not_complete_cancelled_job(self):
        ask = self.ask(question="Already cancelled?", key="cancel-generate-key")
        job_id = ask.json()["job_id"]
        self.client.post(f"/ask/{job_id}/cancel")

        self.main.generate_answer(job_id)

        with sqlite3.connect(os.environ["DB_PATH"]) as conn:
            status = conn.execute("SELECT status FROM ask_jobs WHERE id = ?", (job_id,)).fetchone()[0]
        self.assertEqual(status, "cancelled")

    def test_startup_recovery_marks_running_jobs_failed(self):
        with sqlite3.connect(os.environ["DB_PATH"]) as conn:
            conn.execute(
                """INSERT INTO ask_jobs
                   (id, idempotency_key, question, status, answer, error, context, created_at, updated_at)
                   VALUES (?, ?, ?, 'running', ?, NULL, ?, ?, ?)""",
                ("job-running", "running-key", "Q?", "partial", "[doc 1] Policy", time.time(), time.time()),
            )
            conn.commit()

        self.main.recover_interrupted_jobs()

        with sqlite3.connect(os.environ["DB_PATH"]) as conn:
            status, error = conn.execute("SELECT status, error FROM ask_jobs WHERE id = ?", ("job-running",)).fetchone()
        self.assertEqual(status, "failed")
        self.assertIn("Server restarted", error)

    def insert_completed_job(self, job_id, key, answer):
        with sqlite3.connect(os.environ["DB_PATH"]) as conn:
            conn.execute(
                """INSERT INTO ask_jobs
                   (id, idempotency_key, question, status, answer, error, context, created_at, updated_at, completed_at)
                   VALUES (?, ?, ?, 'completed', ?, NULL, ?, ?, ?, ?)""",
                (job_id, key, "Q?", answer, "[doc 1] Policy", time.time(), time.time(), time.time()),
            )
            conn.commit()

    def test_sse_replays_persisted_answer_and_done_event(self):
        self.insert_completed_job("job-complete", "complete-key", "Persisted answer [doc 1].")

        response = self.client.get("/ask/job-complete/stream")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Persisted answer [doc 1].", response.text)
        self.assertIn("event: done", response.text)

    def test_completed_job_returns_valid_citation_metadata(self):
        self.insert_completed_job("job-cited", "cited-key", "Employees get 12 days [doc 1].")

        response = self.client.get("/ask/job-cited")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(
            body["citations"],
            [
                {
                    "doc_id": 1,
                    "title": "Policy",
                    "valid": True,
                    "snippet": "Employees get 12 days of annual leave.",
                }
            ],
        )
        self.assertIsNone(body["citation_warning"])

    def test_completed_job_warns_for_missing_citation(self):
        self.insert_completed_job("job-missing-citation", "missing-citation-key", "Answer [doc 999].")

        response = self.client.get("/ask/job-missing-citation")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["citations"], [{"doc_id": 999, "title": None, "valid": False, "snippet": None}] )
        self.assertIn("doc 999", body["citation_warning"])

    def test_completed_job_warns_when_no_citations_found(self):
        self.insert_completed_job("job-no-citation", "no-citation-key", "Answer without sources.")

        response = self.client.get("/ask/job-no-citation")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["citations"], [])
        self.assertIn("No document citations", body["citation_warning"])


if __name__ == "__main__":
    unittest.main()
