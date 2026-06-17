import type { AskJob } from "../lib/types";
import { muted } from "../styles";

export function Sources({ askJob }: { askJob: AskJob }) {
  return (
    <>
      {askJob.citations?.length ? (
        <div style={{ borderTop: "1px solid #e5e7eb", padding: 12 }}>
          <div style={{ ...muted, fontSize: 13, fontWeight: 800, marginBottom: 8 }}>Sources validated by document id</div>
          <div style={{ display: "grid", gap: 8 }}>
            {askJob.citations.map((citation) => (
              <article
                key={citation.doc_id}
                style={{
                  border: `1px solid ${citation.valid ? "#bbf7d0" : "#fecaca"}`,
                  background: citation.valid ? "#f0fdf4" : "#fef2f2",
                  borderRadius: 12,
                  padding: 10,
                }}
              >
                <div style={{ color: citation.valid ? "#047857" : "#b91c1c", fontSize: 13, fontWeight: 800 }}>
                  doc {citation.doc_id} · {citation.title ?? "not found"}
                </div>
                {citation.snippet && (
                  <p style={{ ...muted, margin: "6px 0 0", fontSize: 13, lineHeight: 1.5 }}>
                    “{citation.snippet}”
                  </p>
                )}
              </article>
            ))}
          </div>
        </div>
      ) : null}
      {askJob.citation_warning && (
        <div style={{ borderTop: "1px solid #fde68a", background: "#fffbeb", color: "#92400e", padding: 12, fontSize: 13 }}>
          {askJob.citation_warning}
        </div>
      )}
    </>
  );
}
