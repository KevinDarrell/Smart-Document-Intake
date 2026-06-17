"use client";

import { useEffect, useState } from "react";

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

type Doc = { id: number; title: string; summary: string | null };

export default function Page() {
  const [docs, setDocs] = useState<Doc[]>([]);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [loading, setLoading] = useState(false);

  async function refresh() {
    const r = await fetch(`${BACKEND}/documents`);
    setDocs(await r.json());
  }

  useEffect(() => {
    refresh();
  }, []);

  async function ingest() {
    if (!title || !body) return;
    await fetch(`${BACKEND}/ingest`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title, body }),
    });
    setTitle("");
    setBody("");
    refresh();
  }

  async function ask() {
    setLoading(true);
    setAnswer("");
    const r = await fetch(`${BACKEND}/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    const data = await r.json();
    setAnswer(data.answer ?? data.detail ?? "(no answer)");
    setLoading(false);
  }

  const input: React.CSSProperties = { width: "100%", padding: 8, marginBottom: 8, boxSizing: "border-box" };
  const btn: React.CSSProperties = { padding: "8px 16px", cursor: "pointer" };

  return (
    <main>
      <h1>Smart Document Intake</h1>
      <p style={{ color: "#666" }}>See TAKEHOME.md.</p>

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
        <button onClick={ingest} style={btn}>Ingest</button>
      </section>

      <section style={{ marginTop: 24 }}>
        <h2>Documents ({docs.length})</h2>
        <ul>
          {docs.map((d) => (
            <li key={d.id}>
              <b>{d.title}</b> — {d.summary ?? "…"}
            </li>
          ))}
        </ul>
      </section>

      <section style={{ marginTop: 24 }}>
        <h2>Ask</h2>
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask a question about your documents…"
          style={input}
        />
        <button onClick={ask} style={btn}>{loading ? "Asking…" : "Ask"}</button>
        {answer && (
          <pre style={{ whiteSpace: "pre-wrap", background: "#f5f5f5", padding: 12, marginTop: 12 }}>{answer}</pre>
        )}
      </section>
    </main>
  );
}
