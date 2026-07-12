import * as React from "react";
import { useMutation } from "@tanstack/react-query";
import { RefreshCw, Loader2 } from "lucide-react";
import { useDocuments, getSessionId } from "@/lib/documentsContext";
import { query, ApiError } from "@/lib/api";
import { ComparisonView } from "@/components/comparison/ComparisonView";
import { DocumentsRequiredNotice } from "@/components/layout/DocumentsRequiredNotice";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";

export function ComparePage() {
  const { docA, docB, documentIds } = useDocuments();
  const ready = Boolean(docA && docB);

  const mutation = useMutation({
    mutationFn: () =>
      query({
        session_id: getSessionId(),
        query: "Compare the two documents in full: what matches, what changed, and what is missing.",
        document_ids: documentIds,
      }),
  });

  const hasRun = mutation.isSuccess || mutation.isPending || mutation.isError;

  React.useEffect(() => {
    if (ready && !hasRun) mutation.mutate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready]);

  if (!ready) {
    return <DocumentsRequiredNotice message="Load both Document A and Document B to run a comparison." />;
  }

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Comparison</h1>
          <p className="mt-1 text-sm text-ink-soft">
            {docA?.document_name} ({docA?.version}) vs {docB?.document_name} ({docB?.version})
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => mutation.mutate()} disabled={mutation.isPending}>
          {mutation.isPending ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
          Re-run
        </Button>
      </header>

      {mutation.isPending && (
        <div className="flex items-center gap-3 rounded-lg border border-rule bg-paper-raised px-5 py-8 text-sm text-ink-soft">
          <Spinner /> Reading both documents and reconciling section by section — this can take a moment.
        </div>
      )}

      {mutation.isError && (
        <p className="rounded-md border border-missing/30 bg-missing-soft px-4 py-3 text-sm text-missing">
          {mutation.error instanceof ApiError ? mutation.error.message : "Comparison failed."}
        </p>
      )}

      {mutation.data?.comparison && <ComparisonView report={mutation.data.comparison} />}
    </div>
  );
}
