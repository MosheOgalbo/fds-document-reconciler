import { Link } from "react-router-dom";
import { FileStack } from "lucide-react";
import { FreeChatPanel } from "@/components/chat/FreeChatPanel";
import { useDocuments } from "@/lib/documentsContext";
import { Button } from "@/components/ui/button";

export function FreeChatPage() {
  const { docA, docB } = useDocuments();
  const hasDocs = Boolean(docA || docB);

  return (
    <div className="flex h-[calc(100vh-3.5rem)] flex-col gap-4">
      <header className="shrink-0">
        <h1 className="text-2xl font-semibold">Free Chat</h1>
        <p className="mt-1 text-sm text-ink-soft">
          One conversational surface for single-doc questions, cross-document analysis, structured
          comparison, and executive summaries — coordinated by the backend agent graph.
        </p>
      </header>

      {!hasDocs ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-4 rounded-xl border border-dashed border-rule bg-paper-raised/50 px-6 text-center">
          <p className="max-w-md text-sm text-ink-soft">
            Upload Document A and Document B first. Free chat sends all loaded documents to{" "}
            <code className="font-mono text-xs">POST /api/v1/query</code>; the Router Agent
            classifies your intent and runs the matching workflow.
          </p>
          <Link to="/">
            <Button variant="brass" size="sm">
              <FileStack size={14} /> Load documents
            </Button>
          </Link>
        </div>
      ) : (
        <FreeChatPanel />
      )}
    </div>
  );
}
