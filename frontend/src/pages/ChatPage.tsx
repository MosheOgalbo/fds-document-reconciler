import { useDocuments } from "@/lib/documentsContext";
import { ChatPanel } from "@/components/chat/ChatPanel";
import { DocumentsRequiredNotice } from "@/components/layout/DocumentsRequiredNotice";

export function ChatPage() {
  const { docA, docB } = useDocuments();

  if (!docA && !docB) {
    return <DocumentsRequiredNotice message="Load at least one document to start asking questions." />;
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">Ask</h1>
        <p className="mt-1 text-sm text-ink-soft">
          Grounded Q&amp;A — every answer is traced back to retrieved content, or the system tells you
          it doesn't know.
        </p>
      </header>
      <ChatPanel />
    </div>
  );
}
