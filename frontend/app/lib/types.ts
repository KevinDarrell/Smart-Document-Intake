export type Doc = { id: number; title: string; summary: string | null; active: number };
export type DocumentStatus = "active" | "archived";
export type AskStatus = "queued" | "running" | "completed" | "failed" | "cancelled";
export type Citation = { doc_id: number; title: string | null; valid: boolean; snippet: string | null };

export type AskJob = {
  job_id: string;
  idempotency_key: string;
  question: string;
  status: AskStatus;
  answer: string;
  error: string | null;
  citations: Citation[];
  citation_warning: string | null;
};

export type ActiveAskRequest = { question: string; idempotency_key: string };

export function terminal(status: AskStatus) {
  return status === "completed" || status === "failed" || status === "cancelled";
}
