import * as React from "react";
import { useMutation } from "@tanstack/react-query";
import { RefreshCw, Loader2 } from "lucide-react";
import { useDocuments, getSessionId } from "@/lib/documentsContext";
import { query, ApiError } from "@/lib/api";
import { ExecutiveSummaryView } from "@/components/summary/ExecutiveSummaryView";
import { DocumentsRequiredNotice } from "@/components/layout/DocumentsRequiredNotice";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";

export function SummaryPage() {
  const { docA, docB, documentIds } = useDocuments();
  const ready = Boolean(docA && docB);

  const mutation = useMutation({
    mutationFn: () =>
      query({
        session_id: getSessionId(),
        query: "Give me the executive summary of the top most important changes between versions.",
        document_ids: documentIds,
      }),
  });

  const hasRun = mutation.isSuccess || mutation.isPending || mutation.isError;

  React.useEffect(() => {
    if (ready && !hasRun) mutation.mutate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready]);

  if (!ready) {
    return <DocumentsRequiredNotice message="Load both Document A and Document B to generate an executive summary." />;
  }

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Executive Summary</h1>
          <p className="mt-1 text-sm text-ink-soft">Ranked by semantic importance, not document order.</p>
        </div>
        <Button variant="outline" size="sm" onClick={() => mutation.mutate()} disabled={mutation.isPending}>
          {mutation.isPending ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
          Re-run
        </Button>
      </header>

      {mutation.isPending && (
        <div className="flex items-center gap-3 rounded-lg border border-rule bg-paper-raised px-5 py-8 text-sm text-ink-soft">
          <Spinner /> Ranking changes by business, architecture, and workflow impact…
        </div>
      )}

      {mutation.isError && (
        <p className="rounded-md border border-missing/30 bg-missing-soft px-4 py-3 text-sm text-missing">
          {mutation.error instanceof ApiError ? mutation.error.message : "Summary generation failed."}
        </p>
      )}

      {mutation.data?.executive_summary && <ExecutiveSummaryView summary={mutation.data.executive_summary} />}
    </div>
  );
}
