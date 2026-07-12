import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { DocumentUploadCard } from "@/components/ingest/DocumentUploadCard";
import { useDocuments } from "@/lib/documentsContext";
import { Button } from "@/components/ui/button";

export function IngestPage() {
  const { docA, docB } = useDocuments();
  const bothReady = Boolean(docA && docB);

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-2xl font-semibold">Load your documents</h1>
        <p className="mt-1 text-sm text-ink-soft">
          Ingest the older version as Document A and the newer version as Document B. Both PDF and
          DOCX are supported — headings, section hierarchy, and tables are preserved for citation
          accuracy.
        </p>
      </header>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <DocumentUploadCard label="A" defaultName="FDS_PriceBook_V0.pdf" defaultVersion="v0" />
        <DocumentUploadCard label="B" defaultName="FDS_PriceBook_V5.docx" defaultVersion="v5" />
      </div>

      {bothReady && (
        <div className="flex items-center justify-between rounded-lg border border-brass/30 bg-brass-soft px-5 py-4">
          <p className="text-sm font-medium text-ink">
            Both documents are ready. Compare them, ask questions, or generate the executive summary.
          </p>
          <div className="flex gap-2">
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
          </div>
        </div>
      )}
    </div>
  );
}
