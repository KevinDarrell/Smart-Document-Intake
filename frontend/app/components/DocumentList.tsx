import type { Doc, DocumentStatus } from "../lib/types";
import { archiveButton, card, muted, restoreButton, secondaryButton } from "../styles";

type Props = {
  docs: Doc[];
  documentStatus: DocumentStatus;
  setDocumentStatus: (status: DocumentStatus) => void;
  archiveDocument: (documentId: number) => void;
  restoreDocument: (documentId: number) => void;
};

export function DocumentList({ docs, documentStatus, setDocumentStatus, archiveDocument, restoreDocument }: Props) {
  return (
    <section style={{ ...card, marginBottom: 18 }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "flex-start", marginBottom: 14 }}>
        <div>
          <div style={{ ...muted, fontSize: 13, fontWeight: 700 }}>02 · Corpus</div>
          <h2 style={{ margin: "4px 0 0", fontSize: 24 }}>Documents</h2>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", justifyContent: "flex-end" }}>
          {(["active", "archived"] as DocumentStatus[]).map((status) => (
            <button
              key={status}
              onClick={() => setDocumentStatus(status)}
              style={{
                ...secondaryButton,
                background: documentStatus === status ? "#111827" : "#fff",
                color: documentStatus === status ? "#fff" : "#374151",
                borderColor: documentStatus === status ? "#111827" : "#d1d5db",
                fontWeight: 700,
              }}
            >
              {status === "active" ? "Active" : "Archived"}
            </button>
          ))}
          <span style={{ background: "#f3f4f6", padding: "5px 9px", borderRadius: 999, fontSize: 13 }}>{docs.length}</span>
        </div>
      </div>
      {docs.length === 0 ? (
        <p style={{ ...muted, marginBottom: 0 }}>
          {documentStatus === "active" ? "Ingest at least one document before asking questions." : "No archived documents yet."}
        </p>
      ) : (
        <div style={{ display: "grid", gap: 10 }}>
          {docs.map((document) => (
            <article key={document.id} style={{ border: "1px solid #e5e7eb", borderRadius: 12, padding: 14, background: "#fbfdff" }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 10, alignItems: "flex-start" }}>
                <div>
                  <div style={{ color: "#2563eb", fontSize: 12, fontWeight: 800, textTransform: "uppercase", letterSpacing: "0.08em" }}>doc {document.id}</div>
                  <strong>{document.title}</strong>
                </div>
                {documentStatus === "active" ? (
                  <button onClick={() => archiveDocument(document.id)} style={archiveButton}>
                    Archive
                  </button>
                ) : (
                  <button onClick={() => restoreDocument(document.id)} style={restoreButton}>
                    Restore
                  </button>
                )}
              </div>
              <p style={{ ...muted, margin: "6px 0 0", lineHeight: 1.5 }}>{document.summary ?? "Summarizing…"}</p>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
