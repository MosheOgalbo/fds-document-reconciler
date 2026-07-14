import { useMutation } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { ListOrdered, RefreshCw, Loader2 } from "lucide-react";
import { useDocuments, getSessionId } from "@/lib/documentsContext";
import { query, ApiError } from "@/lib/api";
import { ExecutiveSummaryView } from "@/components/summary/ExecutiveSummaryView";
import { DocumentsRequiredNotice } from "@/components/layout/DocumentsRequiredNotice";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";

export function SummaryPage() {
  const { t } = useTranslation();
  const { docA, docB, documentIds } = useDocuments();
  const ready = Boolean(docA && docB);

  const mutation = useMutation({
    mutationFn: () =>
      query({
        session_id: getSessionId(),
        query: t("summary.query"),
        document_ids: documentIds,
      }),
  });

  const hasResults = Boolean(mutation.data?.executive_summary);
  const runSummary = () => mutation.mutate();

  if (!ready) {
    return <DocumentsRequiredNotice messageKey="summary.docsRequired" />;
  }

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">{t("summary.title")}</h1>
          <p className="mt-1 text-sm text-ink-soft">{t("summary.subtitle")}</p>
        </div>
        {hasResults && (
          <Button variant="outline" size="sm" onClick={runSummary} disabled={mutation.isPending}>
            {mutation.isPending ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
            {t("common.reRun")}
          </Button>
        )}
      </header>

      {!hasResults && !mutation.isPending && !mutation.isError && (
        <div className="flex flex-col items-center justify-center gap-4 rounded-lg border border-dashed border-rule px-6 py-16 text-center">
          <ListOrdered className="text-ink-faint" size={32} />
          <p className="max-w-md text-sm text-ink-soft">{t("summary.emptyPrompt")}</p>
          <Button variant="brass" size="sm" onClick={runSummary}>
            <ListOrdered size={14} /> {t("summary.runSummary")}
          </Button>
        </div>
      )}

      {mutation.isPending && (
        <div className="flex items-center gap-3 rounded-lg border border-rule bg-paper-raised px-5 py-8 text-sm text-ink-soft">
          <Spinner /> {t("summary.loading")}
        </div>
      )}

      {mutation.isError && (
        <div className="space-y-3">
          <p className="rounded-md border border-missing/30 bg-missing-soft px-4 py-3 text-sm text-missing">
            {mutation.error instanceof ApiError ? mutation.error.message : t("summary.failed")}
          </p>
          <Button variant="brass" size="sm" onClick={runSummary}>
            <ListOrdered size={14} /> {t("summary.runSummary")}
          </Button>
        </div>
      )}

      {hasResults && mutation.data?.executive_summary && (
        <ExecutiveSummaryView summary={mutation.data.executive_summary} />
      )}
    </div>
  );
}
