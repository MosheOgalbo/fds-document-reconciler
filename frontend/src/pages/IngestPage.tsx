import { Link } from "react-router-dom";
import { ArrowRight, CheckCircle2, Circle } from "lucide-react";
import { DocumentUploadCard } from "@/components/ingest/DocumentUploadCard";
import { useDocuments } from "@/lib/documentsContext";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function IngestPage() {
  const { docA, docB, setDocument } = useDocuments();
  const bothReady = Boolean(docA && docB);

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-2xl font-semibold">Load your documents</h1>
        <p className="mt-1 max-w-3xl text-sm text-ink-soft">
          Upload <strong>Document A</strong> (older version, e.g. PDF) and <strong>Document B</strong> (newer
          version, e.g. DOCX). Each file is parsed, chunked, embedded, and indexed for the agents. You must
          ingest both before Compare, Ask, or Executive Summary will work.
        </p>
      </header>

      <div className="grid grid-cols-1 gap-3 rounded-lg border border-rule bg-white p-4 sm:grid-cols-2">
        <DocStep label="A" ready={Boolean(docA)} name={docA?.fileName} />
        <DocStep label="B" ready={Boolean(docB)} name={docB?.fileName} />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <DocumentUploadCard label="A" defaultName="FDS_PriceBook_V0.pdf" defaultVersion="v0" />
        <DocumentUploadCard label="B" defaultName="FDS_PriceBook_V5.docx" defaultVersion="v5" />
      </div>

      {(docA || docB) && !bothReady && (
        <p className="text-sm text-diff">
          Ingest the second document to unlock Compare, Ask, and Executive Summary.
        </p>
      )}

      {bothReady && (
        <div className="flex flex-col gap-4 rounded-lg border border-match/30 bg-match-soft px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-2">
            <CheckCircle2 className="mt-0.5 shrink-0 text-match" size={18} />
            <div>
              <p className="text-sm font-medium text-ink">Both documents are ready for the agents.</p>
              <p className="mt-0.5 text-xs text-ink-soft">
                A: {docA?.fileName} · B: {docB?.fileName}
              </p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link to="/compare">
              <Button variant="brass" size="sm">
                Compare <ArrowRight size={14} />
              </Button>
            </Link>
            <Link to="/chat">
              <Button variant="outline" size="sm">
                Ask a question
              </Button>
            </Link>
            <Link to="/summary">
              <Button variant="outline" size="sm">
                Executive summary
              </Button>
            </Link>
          </div>
        </div>
      )}

      {(docA || docB) && (
        <div className="text-right">
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setDocument("A", null);
              setDocument("B", null);
            }}
          >
            Clear loaded documents
          </Button>
        </div>
      )}
    </div>
  );
}

function DocStep({ label, ready, name }: { label: string; ready: boolean; name?: string }) {
  return (
    <div className={cn("flex items-center gap-3 rounded-md px-3 py-2", ready ? "bg-match-soft" : "bg-paper")}>
      {ready ? <CheckCircle2 className="text-match" size={18} /> : <Circle className="text-ink-faint" size={18} />}
      <div className="min-w-0">
        <div className="text-sm font-medium text-ink">Document {label}</div>
        <div className="truncate text-xs text-ink-soft">{ready ? name : "Waiting for upload…"}</div>
      </div>
    </div>
  );
}
