import type { AskJob } from "../lib/types";
import { terminal } from "../lib/types";
import { archiveButton, card, input, muted, primaryButton, restoreButton, secondaryButton } from "../styles";
import { Sources } from "./Sources";

const SAMPLE_QUESTIONS = [
  "How many paid annual leave days do full-time employees get?",
  "What are the P1 ticket escalation rules?",
  "What security practices are required for staff accounts?",
];

type Props = {
  activeDocumentCount: number;
  question: string;
  answer: string;
  askJob: AskJob | null;
  loading: boolean;
  setQuestion: (value: string) => void;
  ask: () => void;
  cancelAnswer: () => void;
  retryAnswer: () => void;
  copyAnswer: () => void;
};

export function AskCard({
  activeDocumentCount,
  question,
  answer,
  askJob,
  loading,
  setQuestion,
  ask,
  cancelAnswer,
  retryAnswer,
  copyAnswer,
}: Props) {
  return (
    <section style={card}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "baseline", marginBottom: 14 }}>
        <div>
          <div style={{ ...muted, fontSize: 13, fontWeight: 700 }}>03 · Ask</div>
          <h2 style={{ margin: "4px 0 0", fontSize: 24 }}>Ask your documents</h2>
        </div>
        {askJob && (
          <span style={{ background: askJob.status === "failed" || askJob.status === "cancelled" ? "#fef2f2" : "#ecfdf5", color: askJob.status === "failed" || askJob.status === "cancelled" ? "#b91c1c" : "#047857", padding: "5px 9px", borderRadius: 999, fontSize: 13, fontWeight: 700 }}>
            {askJob.status}
          </span>
        )}
      </div>

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
        {SAMPLE_QUESTIONS.map((sample) => (
          <button key={sample} onClick={() => setQuestion(sample)} style={secondaryButton}>
            {sample}
          </button>
        ))}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 10 }}>
        <input
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="Ask a question about your documents…"
          style={{ ...input, marginTop: 0 }}
        />
        <button onClick={ask} disabled={loading || activeDocumentCount === 0} style={primaryButton(loading || activeDocumentCount === 0)}>
          {loading ? "Generating…" : "Ask"}
        </button>
      </div>
      {activeDocumentCount === 0 && <p style={{ ...muted, marginBottom: 0 }}>Add active documents first so answers can be grounded and cited.</p>}
      {askJob && (
        <p style={{ ...muted, fontSize: 13 }}>
          Job <code>{askJob.job_id.slice(0, 8)}</code> · persisted under an idempotency key
        </p>
      )}
      {askJob && !terminal(askJob.status) && (
        <button onClick={cancelAnswer} style={{ ...archiveButton, marginTop: 4 }}>
          Stop generating
        </button>
      )}
      {askJob && (askJob.status === "failed" || askJob.status === "cancelled") && (
        <button onClick={retryAnswer} disabled={activeDocumentCount === 0} style={{ ...restoreButton, marginTop: 4, opacity: activeDocumentCount === 0 ? 0.5 : 1 }}>
          Retry question
        </button>
      )}

      {answer && (
        <div style={{ border: "1px solid #e5e7eb", borderRadius: 14, overflow: "hidden", marginTop: 14, background: "#fbfdff" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 12px", borderBottom: "1px solid #e5e7eb" }}>
            <span style={{ ...muted, fontSize: 13, fontWeight: 700 }}>Recovered answer buffer</span>
            <button onClick={copyAnswer} style={secondaryButton}>Copy answer</button>
          </div>
          <pre style={{ margin: 0, padding: 14, whiteSpace: "pre-wrap", lineHeight: 1.65, fontFamily: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace", fontSize: 14 }}>
            {answer}
          </pre>
          {askJob && <Sources askJob={askJob} />}
        </div>
      )}
    </section>
  );
}
