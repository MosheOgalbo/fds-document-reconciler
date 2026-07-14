import { useMutation } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { GitCompareArrows, RefreshCw, Loader2 } from "lucide-react";
import { useDocuments, getSessionId } from "@/lib/documentsContext";
import { query, ApiError } from "@/lib/api";
import { ComparisonView } from "@/components/comparison/ComparisonView";
import { DocumentsRequiredNotice } from "@/components/layout/DocumentsRequiredNotice";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";

export function ComparePage() {
  const { t } = useTranslation();
  const { docA, docB, documentIds } = useDocuments();
  const ready = Boolean(docA && docB);

  const mutation = useMutation({
    mutationFn: () =>
      query({
        session_id: getSessionId(),
        query: t("compare.query"),
        document_ids: documentIds,
      }),
  });

  const hasResults = Boolean(mutation.data?.comparison);
  const runComparison = () => mutation.mutate();

  if (!ready) {
    return <DocumentsRequiredNotice messageKey="compare.docsRequired" />;
  }

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">{t("compare.title")}</h1>
          <p className="mt-1 text-sm text-ink-soft">
            {docA?.document_name} ({docA?.version}) {t("common.vs")} {docB?.document_name} ({docB?.version})
          </p>
        </div>
        {hasResults && (
          <Button variant="outline" size="sm" onClick={runComparison} disabled={mutation.isPending}>
            {mutation.isPending ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
            {t("common.reRun")}
          </Button>
        )}
      </header>

      {!hasResults && !mutation.isPending && !mutation.isError && (
        <div className="flex flex-col items-center justify-center gap-4 rounded-lg border border-dashed border-rule px-6 py-16 text-center">
          <GitCompareArrows className="text-ink-faint" size={32} />
          <p className="max-w-md text-sm text-ink-soft">{t("compare.emptyPrompt")}</p>
          <Button variant="brass" size="sm" onClick={runComparison}>
            <GitCompareArrows size={14} /> {t("compare.runComparison")}
          </Button>
        </div>
      )}

      {mutation.isPending && (
        <div className="flex items-center gap-3 rounded-lg border border-rule bg-paper-raised px-5 py-8 text-sm text-ink-soft">
          <Spinner /> {t("compare.loading")}
        </div>
      )}

      {mutation.isError && (
        <div className="space-y-3">
          <p className="rounded-md border border-missing/30 bg-missing-soft px-4 py-3 text-sm text-missing">
            {mutation.error instanceof ApiError ? mutation.error.message : t("compare.failed")}
          </p>
          <Button variant="brass" size="sm" onClick={runComparison}>
            <GitCompareArrows size={14} /> {t("compare.runComparison")}
          </Button>
        </div>
      )}

      {hasResults && mutation.data?.comparison && (
        <ComparisonView report={mutation.data.comparison} />
      )}
    </div>
  );
}
