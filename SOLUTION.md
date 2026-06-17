# Smart Document Intake — Solution

## Summary

I focused Part 1 on the core production failure mode from the prompt: users on flaky mobile connections who double-submit, navigate away, and come back mid-answer. The implementation turns `/ask` into a durable, idempotent, streaming job flow backed by SQLite, with a minimal UI that can recover in-progress answers.

Part 2 is submitted as a design note, as allowed by the prompt. I chose this over a fragile audio demo because the hard part is latency, ordering, buffering, distinct voices, and partial failure handling.

## Reviewer quick path

Core Part 1 files:

- `backend/app/ask_jobs.py` — durable ask jobs, idempotency, context snapshots, and cancellation state.
- `backend/app/workers.py` — background answer generation and persisted streaming chunks.
- `backend/app/routes.py` — `/ask`, `/ask/{job_id}`, SSE streaming, cancellation, document management, and health check routes.
- `backend/app/llm.py` — LLM prompts, including a document prompt-injection guard that treats uploaded content as untrusted data.
- `frontend/app/hooks/useAskJob.ts` — reload recovery, SSE reconnect, double-submit guard, retry, cancel, and copy behavior.
- `frontend/app/lib/storage.ts` — active ask request/job persistence for refresh recovery.

Verification commands:

```powershell
python -m py_compile backend\main.py
python -m unittest -v backend\test_main.py
npm --prefix frontend run build
```

## Part 1 audit: ranked production risks

1. **`/ask` was synchronous and non-durable.** A dropped connection, tab close, or proxy timeout could lose an in-progress answer and push users to retry.
2. **No idempotency for double-submit.** A double tap or network retry could trigger duplicate paid LLM work for the same question.
3. **No streaming.** Users waited for the entire model response before seeing anything, which is especially poor on mobile.
4. **No recovery after navigation/reload.** The frontend kept answer state in React memory only, so users could not come back to an in-progress result.
5. **Failures were not persisted as user-visible state.** Provider errors or malformed responses became generic request failures instead of recoverable job states.
6. **Citation trust was weak.** The prompt asked for citations, but the app did not structurally validate cited document IDs or expose source snippets.
7. **Prompt injection from document content.** Uploaded documents are untrusted input and may contain instructions that try to override the grounding/refusal policy. Production should treat document text as data, strengthen prompt boundaries, and add post-answer support validation.
8. **Context construction will not scale.** Every active document is sent to the model. That is acceptable for this demo, but production needs retrieval/chunking/token budgeting.

## What changed

### Backend

- Replaced blocking `/ask` behavior with a durable SQLite `ask_jobs` state machine:
  - `queued`, `running`, `completed`, `failed`, `cancelled`
  - accumulated answer text
  - stored error
  - context snapshot
  - timestamps
- Added client-provided idempotency keys for `/ask`:
  - same key + same question returns the same job
  - same key + different question returns `409 Conflict`
  - concurrent same-key requests converge on one job via database uniqueness
- Added `GET /ask/{job_id}` for recovery and `GET /ask/{job_id}/stream` for Server-Sent Events.
- Streamed model chunks as they arrive and persisted chunks incrementally so reconnects replay the latest answer.
- Added heartbeat SSE comments to keep idle connections alive.
- Added `POST /ask/{job_id}/cancel` so users can stop generation; retry creates a fresh job to keep history and idempotency clean.
- Stored a context snapshot per ask job so later corpus changes do not change the meaning of an already-started answer.
- Added startup recovery: jobs left `running` after a server restart are marked `failed` with a clear retry message.
- Added `/healthz` for database readiness, API-key configuration, active document count, and ask-job counts.
- Added citation metadata: parse `[doc N]`, validate referenced document IDs exist, return source titles/snippets, and warn on missing/no citations.
- Hardened the answer prompt against document prompt injection by explicitly treating uploaded document content as untrusted data, not instructions.
- Added normalized exact content duplicate detection: same body/content is rejected even if the title changes, avoiding duplicate corpus entries and unnecessary summarization calls.
- Added reversible document archive/restore. Archived docs are excluded from future ask context, while historical ask jobs retain their original context snapshots.
- Refactored the backend into small modules under `backend/app/` while keeping `backend/main.py` as the compatibility entrypoint for `uvicorn main:app`.

### Frontend

- Added idempotent ask submission with a persisted active request key.
- Added SSE streaming and incremental answer rendering.
- Added reload/navigation recovery using `localStorage` + `GET /ask/{job_id}`.
- Added Stop generating and Retry question controls.
- Added active/archived document views with Archive and Restore actions.
- Added source snippets and citation warnings below completed answers.
- Added duplicate-ingest messages, reliability badges, sample questions, and copy-answer support.
- Refactored the UI into hooks/components:
  - `hooks/useAskJob.ts`
  - `hooks/useDocuments.ts`
  - `components/AskCard.tsx`
  - `components/DocumentList.tsx`
  - `components/IntakeCard.tsx`
  - `components/Sources.tsx`

## How `/ask` handles the required scenarios

### Streams the answer

`POST /ask` creates or returns an ask job. `GET /ask/{job_id}/stream` opens an SSE stream. The backend calls DeepSeek with `stream=True`, appends chunks to SQLite, and emits chunk events to the browser.

### Survives interruption

Generation runs in a background thread independent of the browser connection. If the user reloads, navigates away, or loses connectivity, the answer continues to be persisted. When the user returns, the frontend restores the active job from `localStorage`, fetches the latest job state, and reconnects to the stream if still active.

A server-process restart is handled conservatively: interrupted `running` jobs are marked `failed` with a retry message. The app does not pretend it can resume a provider stream mid-token.

### Avoids duplicate work on double-submit

The frontend uses a synchronous submit guard and reuses the active idempotency key. The backend enforces idempotency with a unique key and rejects key reuse for a different question. This prevents duplicate paid LLM calls for the same active question.

### Flow summary

```text
POST /ask + idempotency_key
  -> create or return ask_jobs row
  -> snapshot active documents into job context
  -> background worker claims queued job
  -> model streams tokens
  -> backend appends answer text to SQLite
  -> SSE stream replays persisted text and emits new chunks
  -> frontend stores job_id and reconnects after reload
```

## How to run

### Environment

Create a local root `.env` file as the single place for local secrets/config, and do not commit it:

```text
DEEPSEEK_API_KEY=your_deepseek_api_key
GEMINI_API_KEY=your_gemini_api_key
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
```

`.env.example` documents the expected variables. The apps read these values from their process environments. If your shell or tooling does not automatically load the root `.env`, set the variables in the terminal before running each app. For Next.js specifically, `frontend/.env.local` is also supported for `NEXT_PUBLIC_BACKEND_URL`.

### Backend

From the repository root:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
$env:DEEPSEEK_API_KEY="your_deepseek_api_key"
# Optional: only set this if the frontend is not running at the default http://localhost:3000
# $env:FRONTEND_ORIGIN="http://localhost:3000"
uvicorn main:app --reload --port 8000
```

Health check:

```powershell
curl http://localhost:8000/healthz
```

If `DEEPSEEK_API_KEY` is missing, `ok` and `deepseek_configured` are `false`; the server can start, but ingest/ask are not ready.

### Backend tests

From the repository root:

```powershell
python -m py_compile backend\main.py
python -m unittest -v backend\test_main.py
```

The tests do not call DeepSeek. They cover idempotency, health readiness, startup recovery, SSE replay, citation metadata/snippets, duplicate content detection, archive/restore, and cancellation behavior.

### Frontend

In a second terminal:

```powershell
cd frontend
npm install
$env:NEXT_PUBLIC_BACKEND_URL="http://localhost:8000" # if your shell/tooling did not load root .env
npm run dev
```

Open:

```text
http://localhost:3000
```

Build check:

```powershell
npm --prefix frontend run build
```

## Manual verification checklist

Use documents from `sample_documents.json`.

1. **Ingest documents**
   - Ingest 2-4 sample documents.
   - Re-ingest the same body with the same title: expect duplicate rejection.
   - Re-ingest the same body with a renamed title: expect duplicate rejection.
   - Reuse the same title with different body: expect allowed ingest.

2. **Archive and restore**
   - Archive a document and confirm it leaves Active.
   - Switch to Archived and restore it.
   - Archive it again and ask a question that would require it; the archived content should not be used for new answers.

3. **Streaming answer**
   - Ask: `How many paid annual leave days do full-time employees get?`
   - Expect incremental text, inline `[doc N]` citation, and Sources with a source snippet.

4. **Recovery after reload**
   - Ask a question that takes a few seconds.
   - Refresh while generating.
   - Expect the UI to recover the partial answer and reconnect.

5. **Stop and retry**
   - Ask a longer question.
   - Click Stop generating.
   - Expect status `cancelled`.
   - Click Retry question and confirm a new answer streams.

6. **Double-submit**
   - Click Ask rapidly multiple times.
   - Expect one active job and one backend job for the active idempotency key.

7. **Unsupported question refusal**
   - Ask: `What is the company's 2028 revenue target?`
   - Expect the model to say it does not know / the answer is not in the documents.

## What I prioritized

I prioritized the exact Part 1 reliability scenario: streaming answers, surviving client interruption, and avoiding duplicate work on double-submit.

I kept the implementation intentionally reviewable: SQLite, FastAPI background threads, SSE, and small modules. I avoided adding Redis/Celery/vector DB infrastructure because the take-home grades prioritization and effectiveness, not maximum architecture.

I also added a few high-leverage production-minded improvements around trust and control: health check, citation snippets, content duplicate detection, archive/restore, cancel, retry, and focused backend tests.

## What I cut and why

- **Vector search / embeddings:** useful at scale, but not required to prove durable streaming and idempotent ask behavior.
- **Semantic citation validation:** important before real production, but larger than the core transport/durability requirement. I added structural citation validation and source snippets instead.
- **Semantic near-duplicate detection:** exact normalized content dedupe is deterministic and safe. Paraphrase/near-duplicate detection would need embeddings or shingling plus a confirmation UX.
- **Multi-user auth/session scoping:** production needs it, but the baseline app has no auth model.
- **External queue/worker:** Redis/Celery/RQ would be more production-like, but SQLite + background thread proves the state machine without extra setup friction.
- **Working audio demo:** Part 2 explicitly allows a design note, and a strong latency/ordering/failure design is less fragile than rushing codec/API integration.

## Remaining failure modes and next steps

1. **Server restarts are not resumable mid-token.** Running jobs are failed safely. A production worker could retry from chunk-level state.
2. **Single-process worker assumption.** This take-home implementation assumes one backend process. The SQLite status transition from `queued` to `running` prevents duplicate claiming in the demo, but production should use an external queue/worker with leases or heartbeats because daemon threads and the in-memory `running_jobs` set do not coordinate across replicas or survive process exits.
3. **Answers are stored as one growing text field.** Store chunks in an `ask_chunks` table with sequence numbers for stronger replay/auditability.
4. **Citation validation is structural, not semantic.** The app verifies cited doc IDs and shows snippets, but does not prove every claim is supported. Add claim-level support checks for production.
5. **Document prompt-injection defenses are prompt-level only.** The answer prompt tells the model to treat uploaded content as untrusted data, but production should also add retrieval isolation, claim verification, and tests with malicious documents that attempt to override instructions.
6. **All active documents are sent to the model.** Add chunking, retrieval, and token budgeting before large corpora.
7. **Duplicate detection is exact, not semantic.** Same normalized body is blocked, but paraphrased or lightly rewritten duplicates can still be ingested.
8. **Cancellation is cooperative.** The app stops local persistence/streaming, but cannot guarantee the provider stops billing immediately after a streaming request has started.
9. **Retry creates a new job.** This keeps history and idempotency clean, but does not mutate failed/cancelled rows in place.
10. **Tests are focused, not exhaustive.** I would add browser E2E tests for reload/reconnect UX, prompt-injection cases, and provider-failure cases before production.

## Part 2: Audio design note

Goal: turn a 6-10 turn, two-speaker roleplay into audio that starts quickly, plays smoothly, preserves turn order, and uses distinct voices.

### Proposed architecture

Use segmented generation instead of one large audio file.

1. Parse the dialogue into ordered turns:

```json
{ "turn_index": 0, "speaker": "rep", "text": "Hi Pak Andi..." }
```

2. Assign a stable Gemini voice per speaker:

```json
{ "rep": "voice_a", "client": "voice_b" }
```

3. Create an audio dialogue job with a manifest:

```json
{
  "dialogue_id": "dlg_123",
  "status": "generating",
  "segments": [
    { "turn_index": 0, "speaker": "rep", "status": "queued", "audio_url": null },
    { "turn_index": 1, "speaker": "client", "status": "queued", "audio_url": null }
  ]
}
```

4. Generate turn 0 first and start playback as soon as it is ready.
5. Generate the next 2-3 turns concurrently while playback begins.
6. Stream manifest updates to the frontend with SSE or poll the manifest if SSE is unavailable.
7. The player only plays segments in `turn_index` order, even if later turns finish first.

Possible API shape:

```http
POST /audio/dialogues
GET  /audio/dialogues/{dialogue_id}
GET  /audio/dialogues/{dialogue_id}/events
GET  /audio/segments/{segment_id}
```

### Low-latency strategy

- Prioritize segment 0 for low time-to-first-sound.
- Start playback when segment 0 is ready instead of waiting for the full dialogue.
- Generate a small lookahead buffer, for example 2-3 segments, to reduce gaps between turns.
- Use a short jitter buffer for very short first turns so playback does not immediately stall.
- Cache segments by `voice + normalized_text + model + audio_settings` so retries/replays do not regenerate ready audio.

### Ordering and buffering

Generation can finish out of order, but playback cannot. The manifest is the source of truth:

```text
queued -> generating -> ready
                  \-> retrying -> ready
                  \-> failed
```

If segment 2 finishes before segment 1, segment 2 stays buffered. The player waits for segment 1 or pauses with a clear retry state if segment 1 fails.

### Partial failure behavior

- Retry a failed segment with bounded backoff.
- Keep ready later segments buffered, but do not skip ahead silently.
- If playback reaches a failed/retrying segment, pause with “regenerating this line.”
- Persist the manifest so reloads can resume ready segments without regenerating them.
- If the same dialogue is submitted twice, idempotency can return the existing dialogue job or reuse cached segments.

### Validation plan

I would validate:

- time to first sound
- gap duration between turns
- voice consistency per speaker
- strict playback order under out-of-order generation
- retry behavior for a failed segment
- reload recovery mid-dialogue
- duplicate dialogue submission/caching behavior

### Why design note over demo

The prompt says a strong design note beats a fragile demo. The production risk is not just calling Gemini TTS; it is making playback start fast while preserving speaker identity, turn order, buffering, retry behavior, and recovery. This design keeps the first slice simple and reliable while leaving room for more advanced audio streaming later.
