"use client";

import { useEffect, useRef, useState } from "react";

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
const ACTIVE_JOB_KEY = "smart-intake-active-ask-job";
const ACTIVE_REQUEST_KEY = "smart-intake-active-ask-request";
const SAMPLE_QUESTIONS = [
  "How many paid annual leave days do full-time employees get?",
  "What are the P1 ticket escalation rules?",
  "What security practices are required for staff accounts?",
];

type Doc = { id: number; title: string; summary: string | null };
type AskStatus = "queued" | "running" | "completed" | "failed";
type AskJob = {
  job_id: string;
  idempotency_key: string;
  question: string;
  status: AskStatus;
  answer: string;
  error: string | null;
};
type ActiveAskRequest = { question: string; idempotency_key: string };

function newIdempotencyKey() {
  if (crypto.randomUUID) return crypto.randomUUID();
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function terminal(status: AskStatus) {
  return status === "completed" || status === "failed";
}

export default function Page() {
  const [docs, setDocs] = useState<Doc[]>([]);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [askJob, setAskJob] = useState<AskJob | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const eventSourceRef = useRef<EventSource | null>(null);
  const submittingRef = useRef(false);

  async function refresh() {
    const r = await fetch(`${BACKEND}/documents`);
    setDocs(await r.json());
  }

  function closeStream() {
    eventSourceRef.current?.close();
    eventSourceRef.current = null;
  }

  function rememberJob(job: AskJob | null) {
    if (job && !terminal(job.status)) {
      localStorage.setItem(ACTIVE_JOB_KEY, job.job_id);
      localStorage.setItem(
        ACTIVE_REQUEST_KEY,
        JSON.stringify({ question: job.question, idempotency_key: job.idempotency_key } satisfies ActiveAskRequest),
      );
    } else {
      localStorage.removeItem(ACTIVE_JOB_KEY);
      localStorage.removeItem(ACTIVE_REQUEST_KEY);
    }
  }

  function getOrCreateActiveRequest(trimmedQuestion: string): ActiveAskRequest {
    const stored = localStorage.getItem(ACTIVE_REQUEST_KEY);
    if (stored) {
      try {
        const parsed = JSON.parse(stored) as ActiveAskRequest;
        if (parsed.question === trimmedQuestion && parsed.idempotency_key) return parsed;
      } catch {
        localStorage.removeItem(ACTIVE_REQUEST_KEY);
      }
    }
    const request = { question: trimmedQuestion, idempotency_key: newIdempotencyKey() };
    localStorage.setItem(ACTIVE_REQUEST_KEY, JSON.stringify(request));
    return request;
  }

  async function recoverMissingStream(jobId: string) {
    try {
      const r = await fetch(`${BACKEND}/ask/${jobId}`);
      if (!r.ok) {
        localStorage.removeItem(ACTIVE_JOB_KEY);
        localStorage.removeItem(ACTIVE_REQUEST_KEY);
        setAskJob(null);
        setLoading(false);
        setMessage("Previous answer job is no longer available. You can ask again.");
        closeStream();
        return;
      }
      const job = (await r.json()) as AskJob;
      setAskJob(job);
      setAnswer(job.answer || "");
      setLoading(!terminal(job.status));
      rememberJob(job);
      if (terminal(job.status)) {
        setMessage(job.status === "completed" ? "Answer complete." : `Error: ${job.error}`);
        closeStream();
      } else {
        setMessage("Connection interrupted. Browser will keep reconnecting…");
      }
    } catch {
      setMessage("Connection interrupted. Browser will keep reconnecting…");
    }
  }

  function connectStream(jobId: string) {
    closeStream();
    const source = new EventSource(`${BACKEND}/ask/${jobId}/stream`);
    eventSourceRef.current = source;

    source.addEventListener("status", (event) => {
      const job = JSON.parse((event as MessageEvent).data) as AskJob;
      setAskJob(job);
      setQuestion(job.question);
      setAnswer(job.answer || "");
      setLoading(!terminal(job.status));
      rememberJob(job);
      setMessage(job.status === "queued" ? "Queued…" : "Generating answer… saved automatically.");
    });

    source.addEventListener("chunk", (event) => {
      const data = JSON.parse((event as MessageEvent).data) as { chunk: string; answer: string };
      setAnswer(data.answer);
      setMessage(`Generating answer… saved ${data.answer.length.toLocaleString()} characters so far. Safe to refresh.`);
      setLoading(true);
    });

    source.addEventListener("done", (event) => {
      const job = JSON.parse((event as MessageEvent).data) as AskJob;
      setAskJob(job);
      setAnswer(job.answer || "");
      setLoading(false);
      setMessage("Answer complete and saved.");
      rememberJob(job);
      closeStream();
    });

    source.addEventListener("error", (event) => {
      if ((event as MessageEvent).data) {
        const job = JSON.parse((event as MessageEvent).data) as AskJob;
        setAskJob(job);
        setAnswer(job.answer || "");
        setMessage(job.error ? `Error: ${job.error}` : "Stream failed.");
        setLoading(false);
        rememberJob(job);
        closeStream();
      } else {
        recoverMissingStream(jobId);
      }
    });
  }

  async function restoreActiveJob() {
    const jobId = localStorage.getItem(ACTIVE_JOB_KEY);
    if (!jobId) return;
    try {
      const r = await fetch(`${BACKEND}/ask/${jobId}`);
      if (!r.ok) {
        localStorage.removeItem(ACTIVE_JOB_KEY);
        localStorage.removeItem(ACTIVE_REQUEST_KEY);
        return;
      }
      const job = (await r.json()) as AskJob;
      setAskJob(job);
      setQuestion(job.question);
      setAnswer(job.answer || "");
      if (terminal(job.status)) {
        setLoading(false);
        rememberJob(job);
        setMessage(job.status === "completed" ? "Recovered completed answer." : `Recovered failed answer: ${job.error}`);
      } else {
        setLoading(true);
        setMessage("Recovered in-progress answer. Reconnecting…");
        connectStream(job.job_id);
      }
    } catch {
      setMessage("Could not recover the previous answer yet.");
    }
  }

  useEffect(() => {
    refresh();
    restoreActiveJob();
    return closeStream;
  }, []);

  async function ingest() {
    if (!title || !body) return;
    setMessage("Ingesting document…");
    const r = await fetch(`${BACKEND}/ingest`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title, body }),
    });
    if (!r.ok) {
      const data = await r.json().catch(() => ({}));
      setMessage(data.detail ?? "Could not ingest document.");
      return;
    }
    setTitle("");
    setBody("");
    setMessage("Document ingested.");
    refresh();
  }

  async function ask() {
    const trimmedQuestion = question.trim();
    if (!trimmedQuestion || submittingRef.current || docs.length === 0) return;
    if (loading && askJob) {
      connectStream(askJob.job_id);
      return;
    }

    submittingRef.current = true;
    setLoading(true);
    setAnswer("");
    setMessage("Starting answer job…");
    const request = getOrCreateActiveRequest(trimmedQuestion);
    try {
      const r = await fetch(`${BACKEND}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(request),
      });
      const data = await r.json();
      if (!r.ok) {
        setLoading(false);
        localStorage.removeItem(ACTIVE_REQUEST_KEY);
        setMessage(data.detail ?? "Could not start answer job.");
        return;
      }
      const job = data as AskJob;
      setAskJob(job);
      rememberJob(job);
      connectStream(job.job_id);
    } finally {
      submittingRef.current = false;
    }
  }

  async function copyAnswer() {
    await navigator.clipboard.writeText(answer);
    setMessage("Answer copied to clipboard.");
  }

  const input: React.CSSProperties = {
    width: "100%",
    padding: 10,
    marginBottom: 8,
    boxSizing: "border-box",
    border: "1px solid #d0d7de",
    borderRadius: 8,
  };
  const btn: React.CSSProperties = {
    padding: "9px 16px",
    cursor: loading || docs.length === 0 ? "not-allowed" : "pointer",
    border: 0,
    borderRadius: 8,
    background: "#111827",
    color: "white",
  };
  const secondaryBtn: React.CSSProperties = {
    padding: "7px 10px",
    cursor: "pointer",
    border: "1px solid #d0d7de",
    borderRadius: 999,
    background: "white",
    color: "#111827",
  };
  const muted: React.CSSProperties = { color: "#666" };
  const badge: React.CSSProperties = {
    display: "inline-block",
    margin: "0 8px 8px 0",
    padding: "4px 8px",
    background: "#ecfdf5",
    border: "1px solid #a7f3d0",
    borderRadius: 999,
    color: "#065f46",
    fontSize: 13,
  };

  return (
    <main>
      <h1>Smart Document Intake</h1>
      <p style={muted}>Durable, streaming document Q&A with reconnect recovery.</p>
      <div aria-label="Reliability features" style={{ marginBottom: 12 }}>
        <span style={badge}>✓ Streaming live</span>
        <span style={badge}>✓ Saved automatically</span>
        <span style={badge}>✓ Safe to refresh</span>
      </div>
      {message && (
        <div style={{ background: "#eef6ff", border: "1px solid #b6dcff", padding: 10, borderRadius: 8 }}>{message}</div>
      )}

      <section style={{ marginTop: 24 }}>
        <h2>Add a document</h2>
        <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Title" style={input} />
        <textarea
          value={body}
          onChange={(e) => setBody(e.target.value)}
          placeholder="Paste document text…"
          rows={5}
          style={input}
        />
        <button onClick={ingest} style={{ ...btn, cursor: "pointer" }}>Ingest</button>
      </section>

      <section style={{ marginTop: 24 }}>
        <h2>Documents ({docs.length})</h2>
        {docs.length === 0 ? (
          <p style={muted}>Ingest at least one document before asking questions.</p>
        ) : (
          <ul>
            {docs.map((d) => (
              <li key={d.id}>
                <b>{d.title}</b> — {d.summary ?? "…"}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section style={{ marginTop: 24 }}>
        <h2>Ask</h2>
        <div style={{ marginBottom: 8 }}>
          <p style={{ ...muted, marginBottom: 6 }}>Try a sample question:</p>
          {SAMPLE_QUESTIONS.map((sample) => (
            <button key={sample} onClick={() => setQuestion(sample)} style={{ ...secondaryBtn, margin: "0 8px 8px 0" }}>
              {sample}
            </button>
          ))}
        </div>
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask a question about your documents…"
          style={input}
        />
        <button onClick={ask} disabled={loading || docs.length === 0} style={btn}>{loading ? "Generating…" : "Ask"}</button>
        {docs.length === 0 && <p style={muted}>Add documents first so answers can be grounded.</p>}
        {askJob && (
          <p style={muted}>
            Job <code>{askJob.job_id.slice(0, 8)}</code> · {askJob.status}
          </p>
        )}
        {answer && (
          <div>
            <button onClick={copyAnswer} style={{ ...secondaryBtn, marginTop: 12 }}>Copy answer</button>
            <pre
              style={{
                whiteSpace: "pre-wrap",
                background: "#f6f8fa",
                border: "1px solid #d0d7de",
                borderRadius: 8,
                padding: 12,
                marginTop: 12,
              }}
            >
              {answer}
            </pre>
          </div>
        )}
      </section>
    </main>
  );
}
