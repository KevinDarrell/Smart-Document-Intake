# Smart Document Intake — Solution

## Requirement coverage

### Part 1

Implemented:

- **Stream the answer as it is generated:** `GET /ask/{job_id}/stream` returns Server-Sent Events, and the frontend renders chunks incrementally.
- **Survive interruption:** `/ask` creates a durable SQLite-backed job, stores partial answer text as it arrives, and the frontend restores the active job from `localStorage` after reload/navigation.
- **Never duplicate work on double-submit:** the frontend reuses a persisted active idempotency key, and the backend enforces idempotency with a unique key plus atomic `INSERT OR IGNORE`.
- **Recover after coming back:** `GET /ask/{job_id}` returns the latest job status and accumulated answer; the frontend reconnects if the job is still active.
- **Operational polish:** `GET /healthz` reports database reachability, API-key configuration, document count, and ask-job counts without exposing secrets.

### Part 2

Submitted a design note rather than a fragile demo. The note focuses on low time-to-first-sound, ordered playback, distinct speaker voices, buffering, retry behavior, and validation.

## Part 1: Ranked production audit

1. **`/ask` was synchronous and non-durable.** The baseline tied the LLM request to one HTTP request. On a flaky mobile connection, a dropped tab or proxy timeout would lose the answer and encourage users to retry.
2. **No idempotency meant double-submit duplicated work.** A double tap or network retry could trigger multiple paid LLM calls for the same question, with racing responses in the UI.
3. **No streaming created poor perceived latency.** Users waited for the full model response before seeing anything, which is especially bad on mobile.
4. **No recovery path after navigation.** The frontend held answer state only in React memory; a reload discarded in-progress work.
5. **Provider and malformed-response failures were not represented as user-visible state.** Failures became generic request errors rather than persisted job status that can be shown or retried.
6. **Grounding/citation is prompt-only.** The answer prompt asks the model to cite documents and refuse unsupported questions, but there is no structured citation validation yet.
7. **Context construction will not scale.** Every full document is included in every question prompt. This is acceptable for the small demo corpus, but production would need chunking/retrieval and token budgets.

## What I changed

I changed `/ask` from a blocking request into a small durable job system backed by SQLite.

### Backend

- Added an `ask_jobs` table with:
  - `id`
  - `idempotency_key`
  - `question`
  - `status` (`queued`, `running`, `completed`, `failed`)
  - accumulated `answer`
  - `error`
  - document `context` snapshot
  - timestamps
- `POST /ask` now accepts a client-generated `idempotency_key`.
  - It uses atomic `INSERT OR IGNORE`, then always reads the row by `idempotency_key`.
  - Repeated submissions with the same key return the same job instead of starting duplicate work.
- The job stores a snapshot of the current document context at creation time, so the answer is generated against the document set that existed when the user asked.
- The background worker claims jobs through the database by transitioning `queued -> running`. Only the process that successfully claims the row may call the LLM.
- Added `GET /ask/{job_id}` to recover the latest persisted state.
- Added `GET /ask/{job_id}/stream` using Server-Sent Events.
  - On connect/reconnect it replays the persisted answer accumulated so far.
  - It then streams new text as the background worker appends chunks to SQLite.
  - It emits heartbeat comments to keep idle mobile/proxy connections alive.
- The DeepSeek call now uses streaming mode and persists chunks incrementally.
- SQLite is opened with WAL mode and a busy timeout to behave better under the small amount of concurrency this demo needs.
- Added `GET /healthz` for a quick operational check: database status, DeepSeek configuration, document count, and ask-job counts.
- On startup, interrupted `running` jobs are marked `failed` with a clear retry message rather than being left stuck forever or accidentally resumed by appending duplicate output.

### Frontend

- The Ask flow now creates and persists an idempotency key for the active submission.
- Retries/double-invocations for the same active question reuse that key until the job becomes terminal.
- It connects to the SSE stream and renders the answer incrementally.
- It stores the active job id in `localStorage` while the job is not terminal.
- On page load, it recovers an active job via `GET /ask/{job_id}` and reconnects to the stream if needed.
- It has a synchronous `submittingRef` guard so rapid double taps are blocked before React state updates propagate.
- The UI shows job status and recovery/progress messages.
- Added reviewer-friendly UI polish: reliability badges, sample questions, empty-state guidance, and a Copy answer button.

## How the new `/ask` handles the required scenarios

### Streams the answer

The backend calls DeepSeek with `stream=True`; chunks are appended to the `ask_jobs.answer` column. The SSE endpoint sends `chunk` events to the browser as text becomes available.

### Survives interruption

Generation runs in a background thread independent of the SSE client connection. If the browser closes, reloads, or temporarily loses connectivity, the background job continues and the partial/final answer remains in SQLite.

When the user returns, the frontend reads the saved job id from `localStorage`, fetches the current job state, and reconnects to `/ask/{job_id}/stream` if the job is still active.

### Avoids duplicate work on double-submit

The frontend avoids obvious duplicate clicks with a synchronous submit guard and by disabling the Ask button while active. More importantly, the backend stores `idempotency_key` with a unique constraint and uses atomic insert/read semantics so repeated submissions with the same key return the existing job.

In production I would also include a user/session id and possibly a normalized question/document-set hash in the idempotency scope. For this take-home, a client-generated key demonstrates the core mechanism with minimal moving parts.

## How to run

### Backend

From the repository root:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
$env:DEEPSEEK_API_KEY="your_deepseek_api_key"
uvicorn main:app --reload --port 8000
```

Health check in another terminal:

```powershell
curl http://localhost:8000/healthz
```

Expected shape:

```json
{
  "ok": true,
  "database": "ok",
  "deepseek_configured": true,
  "documents": 0,
  "ask_jobs": {
    "queued": 0,
    "running": 0,
    "completed": 0,
    "failed": 0
  }
}
```

### Frontend

Open a second terminal from the repository root:

```powershell
cd frontend
npm install
```

Create `frontend/.env.local`:

```text
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
```

Then run:

```powershell
npm run dev
```

Open:

```text
http://localhost:3000
```

## Demo script

For a quick reviewer demo:

1. Open `http://localhost:8000/healthz` to confirm the backend and database are ready.
2. Ingest the handbook and support SOP documents from `sample_documents.json`.
3. Use one of the sample question buttons in the UI.
4. Refresh the page while the answer is streaming to show persisted recovery.
5. Use the fixed-key API check below to show backend idempotency.

## Manual verification checklist

Use documents from `sample_documents.json`.

### 1. Ingest documents

In the UI:

1. Copy a sample document title into **Title**.
2. Copy its body into the textarea.
3. Click **Ingest**.
4. Repeat for 2-4 sample documents.

Expected:

- Document count increases.
- Each document shows a one-sentence summary after ingest.

### 2. Streaming answer

Ask:

```text
How many paid annual leave days do full-time employees get?
```

Expected:

- Status changes to queued/running/generating.
- Answer appears incrementally, not only after the whole response finishes.
- Final answer cites the relevant doc id, e.g. `[doc 1]`.

### 3. Recovery after reload

1. Ask a question that takes a few seconds.
2. While it is generating, refresh the browser tab.

Expected:

- The UI says it recovered an in-progress answer.
- Existing partial text is still visible.
- The stream reconnects and continues until completion.

### 4. Double-submit behavior

1. Enter a question.
2. Click **Ask** rapidly multiple times.

Expected:

- The UI only tracks one active job.
- The job id remains the same for the active request.
- The backend returns the same job for repeated submissions using the same idempotency key.

Optional API-level check with a fixed key:

```powershell
$body = @{ question = "What are standard working hours?"; idempotency_key = "manual-test-12345" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://localhost:8000/ask -ContentType "application/json" -Body $body
Invoke-RestMethod -Method Post -Uri http://localhost:8000/ask -ContentType "application/json" -Body $body
```

Expected:

- Both responses have the same `job_id`.

### 5. Unsupported question refusal

Ask:

```text
What is the company's 2028 revenue target?
```

Expected:

- The model should say it does not know / the answer is not in the documents.
- It should not invent a target.

## What I prioritized

I prioritized the exact Part 1 failure mode: mobile users on unreliable connections who retry or navigate away. The durable job model, SSE replay, and idempotency key directly address that.

I kept the implementation intentionally small: one FastAPI file, SQLite, no Redis, no Celery, no vector DB. That makes the behavior easy to review and run in a take-home setting.

## What I cut and why

- **Vector search / embeddings:** useful for production scale, but not necessary to prove the requested streaming/durability behavior.
- **Full citation validation:** important, but more time-consuming than the core transport/durability requirement. I kept strict prompt instructions and documented validation as next work.
- **Multi-user auth/session scoping:** production would need it; this assignment app has no auth baseline.
- **External queue/worker:** Redis/Celery/RQ would be more production-like but would add setup friction. SQLite plus a background thread is enough to demonstrate the state machine.
- **Working audio implementation:** Part 2 explicitly allows a design note, and a strong design is less fragile than rushing codec/API integration.

## Remaining failure modes and next steps

1. **Process restarts are handled conservatively but not resumably.** Startup marks interrupted `running` jobs as `failed` with a retry message. A production worker could resume or retry from chunk-level state instead.
2. **In-memory `running_jobs` is only a local convenience.** The database claim protects `queued -> running`, but multiple production workers would still be better served by an external queue and worker process.
3. **The answer is stored as one growing text field.** For more robust replay and auditing, store chunks in an `ask_chunks` table with sequence numbers.
4. **Prompt-only grounding can hallucinate citations.** Add structured output, citation extraction, and post-validation that cited doc ids exist and support the answer.
5. **All documents are sent to the model.** Add chunking, retrieval, and max-token budgeting before real usage.
6. **No cancellation endpoint.** Users cannot stop an unwanted generation yet.
7. **No automated tests.** I would add tests for idempotency, SSE replay, failed jobs, and reconnect behavior.

## Part 2: Audio design note

Goal: turn a short two-speaker dialogue into audio with low time-to-first-sound, smooth playback, and distinct voices.

### Proposed architecture

1. Parse the dialogue into ordered turns:

```json
{
  "turnIndex": 0,
  "speaker": "rep",
  "text": "Hi Pak Andi..."
}
```

2. Assign a stable voice per speaker:

```json
{
  "rep": "voice_a",
  "client": "voice_b"
}
```

3. Generate audio per turn as independent segments using Gemini TTS.

4. Start playback as soon as turn 0 is ready, instead of waiting for the entire dialogue.

5. While turn 0 is playing, generate turns 1-N in parallel with a small concurrency limit.

6. Maintain a playback buffer/manifest:

```json
{
  "dialogueId": "...",
  "segments": [
    { "turnIndex": 0, "speaker": "rep", "status": "ready", "url": "/audio/0.wav" },
    { "turnIndex": 1, "speaker": "client", "status": "generating", "url": null }
  ]
}
```

7. The player consumes segments in order. It may generate ahead out-of-order, but playback order remains strict.

### Low-latency strategy

- Generate the first turn immediately at highest priority.
- Begin playback once the first segment is ready.
- Generate the next 2-3 turns concurrently to avoid gaps.
- Use a small jitter buffer: do not start if there is only a tiny amount of audio and the next segment is far behind, but avoid waiting for the full dialogue.
- Cache generated segments by `(voice, text hash, model settings)` so retries or replays do not regenerate audio.

### Partial failure behavior

- If turn N fails but turn N-1 is playing, retry turn N in the background.
- If retry still fails before playback reaches it, pause with a clear “regenerating segment” message rather than skipping silently.
- If a later turn is ready before an earlier failed turn, keep it buffered but do not play out of order.
- Persist the manifest so reloads can resume without regenerating completed segments.

### Validation

I would measure:

- Time to first sound.
- Gap duration between turns.
- Voice consistency per speaker.
- Correct playback order under out-of-order generation.
- Behavior when one segment generation fails.
- Behavior after browser reload mid-dialogue.

### Why design note over demo

The assignment says a strong design note is better than a fragile demo. The tricky part is not just calling a TTS API; it is ordering, buffering, retrying, preserving distinct speaker voices, and starting playback quickly without causing mid-dialogue stalls. I chose to explain that system clearly rather than add a brittle partially working audio path.
