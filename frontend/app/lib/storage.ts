import type { ActiveAskRequest, AskJob } from "./types";
import { terminal } from "./types";

export const ACTIVE_JOB_KEY = "smart-intake-active-ask-job";
export const ACTIVE_REQUEST_KEY = "smart-intake-active-ask-request";

export function newIdempotencyKey() {
  if (crypto.randomUUID) return crypto.randomUUID();
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export function rememberJob(job: AskJob | null) {
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

export function forgetActiveAsk() {
  localStorage.removeItem(ACTIVE_JOB_KEY);
  localStorage.removeItem(ACTIVE_REQUEST_KEY);
}

export function getStoredJobId() {
  return localStorage.getItem(ACTIVE_JOB_KEY);
}

export function getOrCreateActiveRequest(trimmedQuestion: string): ActiveAskRequest {
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

export function storeActiveRequest(request: ActiveAskRequest) {
  localStorage.setItem(ACTIVE_REQUEST_KEY, JSON.stringify(request));
}
