import { card, input, muted, primaryButton } from "../styles";

type Props = {
  activeDocumentCount: number;
  title: string;
  body: string;
  ingesting: boolean;
  setTitle: (value: string) => void;
  setBody: (value: string) => void;
  ingest: () => void;
};

export function IntakeCard({ activeDocumentCount, title, body, ingesting, setTitle, setBody, ingest }: Props) {
  const disabled = !title || !body || ingesting;
  return (
    <section style={{ ...card, marginBottom: 18 }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "baseline", marginBottom: 10 }}>
        <div>
          <div style={{ ...muted, fontSize: 13, fontWeight: 700 }}>01 · Intake</div>
          <h2 style={{ margin: "4px 0 0", fontSize: 24 }}>Add a document</h2>
        </div>
        <span style={{ ...muted, fontSize: 13 }}>{activeDocumentCount} active</span>
      </div>
      <input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Document title" style={input} />
      <textarea
        value={body}
        onChange={(event) => setBody(event.target.value)}
        placeholder="Paste document text…"
        rows={6}
        style={{ ...input, resize: "vertical", lineHeight: 1.5 }}
      />
      <button onClick={ingest} disabled={disabled} style={{ ...primaryButton(disabled), marginTop: 12 }}>
        {ingesting ? "Ingesting…" : "Ingest document"}
      </button>
    </section>
  );
}
