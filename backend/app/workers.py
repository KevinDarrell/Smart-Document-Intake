import threading

from .ask_jobs import append_answer, claim_queued_job, get_job, job_status, mark_job
from .llm import build_answer_prompt, stream_answer

running_jobs: set[str] = set()
running_jobs_lock = threading.Lock()


def generate_answer(job_id: str):
    try:
        row = claim_queued_job(job_id)
        if not row:
            return
        if job_status(job_id) == "cancelled":
            return
        prompt = build_answer_prompt(row["question"], row["context"] or "")
        stream = stream_answer(prompt)
        saw_content = False
        for event in stream:
            if job_status(job_id) == "cancelled":
                return
            delta = event.choices[0].delta.content if event.choices else None
            if delta:
                saw_content = True
                append_answer(job_id, delta)
        if job_status(job_id) == "cancelled":
            return
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


def discard_running_job(job_id: str):
    with running_jobs_lock:
        running_jobs.discard(job_id)
