import { useState } from "react";

import { fetchDocuments, postArchiveDocument, postIngest, postRestoreDocument } from "../lib/api";
import type { Doc, DocumentStatus } from "../lib/types";

export function useDocuments(setMessage: (message: string) => void) {
  const [docs, setDocs] = useState<Doc[]>([]);
  const [activeDocumentCount, setActiveDocumentCount] = useState(0);
  const [documentStatus, setDocumentStatus] = useState<DocumentStatus>("active");
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [ingesting, setIngesting] = useState(false);
  const [ingestingLocked, setIngestingLocked] = useState(false);

  async function refresh(status = documentStatus) {
    const visibleDocs = await fetchDocuments(status);
    setDocs(visibleDocs);
    if (status === "active") {
      setActiveDocumentCount(visibleDocs.length);
    } else {
      const activeDocs = await fetchDocuments("active");
      setActiveDocumentCount(activeDocs.length);
    }
  }

  async function ingest() {
    if (!title || !body || ingestingLocked) return;
    setIngestingLocked(true);
    setIngesting(true);
    setMessage("Ingesting document…");
    try {
      const response = await postIngest(title, body);
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        const detail = data.detail;
        setMessage(typeof detail === "string" ? detail : detail?.message ?? "Could not ingest document.");
        return;
      }
      setTitle("");
      setBody("");
      setMessage("Document ingested.");
      setDocumentStatus("active");
      refresh("active");
    } finally {
      setIngestingLocked(false);
      setIngesting(false);
    }
  }

  async function archiveDocument(documentId: number) {
    const response = await postArchiveDocument(documentId);
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      setMessage(data.detail ?? "Could not archive document.");
      return;
    }
    setMessage("Document archived. It will no longer be used for new answers.");
    refresh("active");
  }

  async function restoreDocument(documentId: number) {
    const response = await postRestoreDocument(documentId);
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      setMessage(data.detail ?? "Could not restore document.");
      return;
    }
    setMessage("Document restored to the active corpus.");
    setDocumentStatus("active");
  }

  return {
    docs,
    activeDocumentCount,
    documentStatus,
    setDocumentStatus,
    title,
    setTitle,
    body,
    setBody,
    ingesting,
    refresh,
    ingest,
    archiveDocument,
    restoreDocument,
  };
}
