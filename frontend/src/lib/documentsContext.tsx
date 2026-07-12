import * as React from "react";
import type { IngestedDocument } from "@/types/api";

const STORAGE_KEY = "fds-reconcile:documents";

interface DocumentsContextValue {
  docA: IngestedDocument | null;
  docB: IngestedDocument | null;
  setDocument: (label: "A" | "B", doc: IngestedDocument | null) => void;
  documentIds: string[];
}

const DocumentsContext = React.createContext<DocumentsContextValue | null>(null);

function loadFromStorage(): { docA: IngestedDocument | null; docB: IngestedDocument | null } {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { docA: null, docB: null };
    return JSON.parse(raw);
  } catch {
    return { docA: null, docB: null };
  }
}

export function DocumentsProvider({ children }: { children: React.ReactNode }) {
  const [docA, setDocA] = React.useState<IngestedDocument | null>(() => loadFromStorage().docA);
  const [docB, setDocB] = React.useState<IngestedDocument | null>(() => loadFromStorage().docB);

  React.useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ docA, docB }));
  }, [docA, docB]);

  const setDocument = React.useCallback((label: "A" | "B", doc: IngestedDocument | null) => {
    if (label === "A") setDocA(doc);
    else setDocB(doc);
  }, []);

  const documentIds = [docA?.document_id, docB?.document_id].filter((id): id is string => Boolean(id));

  return (
    <DocumentsContext.Provider value={{ docA, docB, setDocument, documentIds }}>
      {children}
    </DocumentsContext.Provider>
  );
}

export function useDocuments() {
  const ctx = React.useContext(DocumentsContext);
  if (!ctx) throw new Error("useDocuments must be used within DocumentsProvider");
  return ctx;
}

export function getSessionId(): string {
  const key = "fds-reconcile:session-id";
  let id = localStorage.getItem(key);
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem(key, id);
  }
  return id;
}
