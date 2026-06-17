import { useRef, useState } from "react";

import { askStreamUrl, fetchAskJob, postAsk, postCancelAsk } from "../lib/api";
import { forgetActiveAsk, getOrCreateActiveRequest, getStoredJobId, newIdempotencyKey, rememberJob, storeActiveRequest } from "../lib/storage";
import type { ActiveAskRequest, AskJob } from "../lib/types";
import { terminal } from "../lib/types";

export function useAskJob(activeDocumentCount: number, setMessage: (message: string) => void) {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [askJob, setAskJob] = useState<AskJob | null>(null);
  const [loading, setLoading] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);
  const submittingRef = useRef(false);

  function closeStream() {
    eventSourceRef.current?.close();
    eventSourceRef.current = null;
  }

  async function recoverMissingStream(jobId: string) {
    try {
      const response = await fetchAskJob(jobId);
      if (!response.ok) {
        forgetActiveAsk();
        setAskJob(null);
        setLoading(false);
        setMessage("Previous answer job is no longer available. You can ask again.");
        closeStream();
        return;
      }
      const job = (await response.json()) as AskJob;
      setAskJob(job);
      setAnswer(job.answer || "");
      setLoading(!terminal(job.status));
      rememberJob(job);
      if (terminal(job.status)) {
        setMessage(job.status === "completed" ? "Answer complete." : job.status === "cancelled" ? "Answer generation was stopped." : `Error: ${job.error}`);
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
    const source = new EventSource(askStreamUrl(jobId));
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
    const jobId = getStoredJobId();
    if (!jobId) return;
    try {
      const response = await fetchAskJob(jobId);
      if (!response.ok) {
        forgetActiveAsk();
        return;
      }
      const job = (await response.json()) as AskJob;
      setAskJob(job);
      setQuestion(job.question);
      setAnswer(job.answer || "");
      if (terminal(job.status)) {
        setLoading(false);
        rememberJob(job);
        setMessage(job.status === "completed" ? "Recovered completed answer." : job.status === "cancelled" ? "Recovered stopped answer. You can retry it." : `Recovered failed answer: ${job.error}`);
      } else {
        setLoading(true);
        setMessage("Recovered in-progress answer. Reconnecting…");
        connectStream(job.job_id);
      }
    } catch {
      setMessage("Could not recover the previous answer yet.");
    }
  }

  async function startAsk(request: ActiveAskRequest, clearAnswer = true) {
    submittingRef.current = true;
    setLoading(true);
    if (clearAnswer) setAnswer("");
    setMessage("Starting answer job…");
    try {
      const { response, data } = await postAsk(request);
      if (!response.ok) {
        setLoading(false);
        forgetActiveAsk();
        setMessage((data as { detail?: string }).detail ?? "Could not start answer job.");
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

  async function ask() {
    const trimmedQuestion = question.trim();
    if (!trimmedQuestion || submittingRef.current || activeDocumentCount === 0) return;
    if (loading && askJob) {
      connectStream(askJob.job_id);
      return;
    }
    await startAsk(getOrCreateActiveRequest(trimmedQuestion));
  }

  async function cancelAnswer() {
    if (!askJob || terminal(askJob.status)) return;
    const response = await postCancelAsk(askJob.job_id);
    const data = await response.json().catch(() => null);
    if (!response.ok || !data) {
      setMessage(data?.detail ?? "Could not stop generation.");
      return;
    }
    const job = data as AskJob;
    setAskJob(job);
    setAnswer(job.answer || answer);
    setLoading(false);
    rememberJob(job);
    closeStream();
    setMessage("Answer generation stopped. You can retry the question.");
  }

  async function retryAnswer() {
    const retryQuestion = askJob?.question || question.trim();
    if (!retryQuestion || submittingRef.current || activeDocumentCount === 0) return;
    const request = { question: retryQuestion, idempotency_key: newIdempotencyKey() };
    storeActiveRequest(request);
    setQuestion(retryQuestion);
    await startAsk(request);
  }

  async function copyAnswer() {
    await navigator.clipboard.writeText(answer);
    setMessage("Answer copied to clipboard.");
  }

  return {
    question,
    setQuestion,
    answer,
    askJob,
    loading,
    restoreActiveJob,
    closeStream,
    ask,
    cancelAnswer,
    retryAnswer,
    copyAnswer,
  };
}
