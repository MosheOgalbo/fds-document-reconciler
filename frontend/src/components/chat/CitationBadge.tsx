import { FileText } from "lucide-react";
import type { Citation } from "@/types/api";

export function CitationBadge({ citation }: { citation: Citation }) {
  return (
    <div className="flex items-start gap-1.5 rounded border border-rule bg-white px-2.5 py-1.5 font-mono text-[11px] text-ink-soft">
      <FileText size={12} className="mt-0.5 shrink-0 text-brass" />
      <div>
        <div className="text-ink">
          {citation.document_name} <span className="text-ink-faint">v{citation.version}</span>
        </div>
        <div className="text-ink-faint">
          {citation.section} · page {citation.page_number}
        </div>
      </div>
    </div>
  );
}
