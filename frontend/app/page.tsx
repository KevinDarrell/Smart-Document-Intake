"use client";

import { useEffect, useState } from "react";

import { AskCard } from "./components/AskCard";
import { DocumentList } from "./components/DocumentList";
import { IntakeCard } from "./components/IntakeCard";
import { useAskJob } from "./hooks/useAskJob";
import { useDocuments } from "./hooks/useDocuments";
import { card, muted } from "./styles";

export default function Page() {
  const [message, setMessage] = useState("");
  const documents = useDocuments(setMessage);
  const askJob = useAskJob(documents.activeDocumentCount, setMessage);

  useEffect(() => {
    askJob.restoreActiveJob();
    return askJob.closeStream;
  }, []);

  useEffect(() => {
    documents.refresh(documents.documentStatus);
  }, [documents.documentStatus]);

  return (
    <main style={{ minHeight: "100vh", background: "#f8fafc", color: "#111827", padding: "40px 20px" }}>
      <div style={{ maxWidth: 920, margin: "0 auto" }}>
        <header style={{ textAlign: "center", marginBottom: 28 }}>
          <div style={{ color: "#2563eb", fontSize: 13, fontWeight: 800, letterSpacing: "0.12em", textTransform: "uppercase" }}>
            Smart Document Intake
          </div>
          <h1 style={{ fontSize: "clamp(34px, 6vw, 56px)", lineHeight: 1, letterSpacing: -1.6, margin: "12px 0 14px" }}>
            Durable document Q&A
          </h1>
          <p style={{ ...muted, maxWidth: 650, margin: "0 auto", fontSize: 17, lineHeight: 1.6 }}>
            Add documents, ask grounded questions, and recover streaming answers across refreshes, flaky connections, and double-submits.
          </p>
        </header>

        <div style={{ display: "flex", justifyContent: "center", gap: 8, flexWrap: "wrap", marginBottom: 18 }}>
          {[
            "Streaming live",
            "Saved automatically",
            "Safe to refresh",
          ].map((label) => (
            <span key={label} style={{ background: "#ecfdf5", color: "#047857", border: "1px solid #bbf7d0", padding: "6px 10px", borderRadius: 999, fontSize: 13, fontWeight: 700 }}>
              ✓ {label}
            </span>
          ))}
        </div>

        {message && (
          <div style={{ ...card, padding: 14, marginBottom: 18, background: "#eff6ff", borderColor: "#bfdbfe", color: "#1e40af" }}>
            {message}
          </div>
        )}

        <IntakeCard
          activeDocumentCount={documents.activeDocumentCount}
          title={documents.title}
          body={documents.body}
          ingesting={documents.ingesting}
          setTitle={documents.setTitle}
          setBody={documents.setBody}
          ingest={documents.ingest}
        />

        <DocumentList
          docs={documents.docs}
          documentStatus={documents.documentStatus}
          setDocumentStatus={documents.setDocumentStatus}
          archiveDocument={documents.archiveDocument}
          restoreDocument={documents.restoreDocument}
        />

        <AskCard
          activeDocumentCount={documents.activeDocumentCount}
          question={askJob.question}
          answer={askJob.answer}
          askJob={askJob.askJob}
          loading={askJob.loading}
          setQuestion={askJob.setQuestion}
          ask={askJob.ask}
          cancelAnswer={askJob.cancelAnswer}
          retryAnswer={askJob.retryAnswer}
          copyAnswer={askJob.copyAnswer}
        />
      </div>
    </main>
  );
}
