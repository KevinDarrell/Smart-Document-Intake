import type { ActiveAskRequest, AskJob, Doc, DocumentStatus } from "./types";

export const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

export async function fetchDocuments(status: DocumentStatus) {
  const response = await fetch(`${BACKEND}/documents?status=${status}`);
  return (await response.json()) as Doc[];
}

export async function postIngest(title: string, body: string) {
  return fetch(`${BACKEND}/ingest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, body }),
  });
}

export async function postArchiveDocument(documentId: number) {
  return fetch(`${BACKEND}/documents/${documentId}`, { method: "DELETE" });
}

export async function postRestoreDocument(documentId: number) {
  return fetch(`${BACKEND}/documents/${documentId}/restore`, { method: "POST" });
}

export async function postAsk(request: ActiveAskRequest) {
  const response = await fetch(`${BACKEND}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  const data = await response.json();
  return { response, data } as { response: Response; data: AskJob | { detail?: string } };
}

export async function fetchAskJob(jobId: string) {
  const response = await fetch(`${BACKEND}/ask/${jobId}`);
  return response;
}

export async function postCancelAsk(jobId: string) {
  return fetch(`${BACKEND}/ask/${jobId}/cancel`, { method: "POST" });
}

export function askStreamUrl(jobId: string) {
  return `${BACKEND}/ask/${jobId}/stream`;
}
