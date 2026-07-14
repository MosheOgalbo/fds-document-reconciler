import { Link } from "react-router-dom";
import { useTranslation, Trans } from "react-i18next";
import { ArrowRight, CheckCircle2, Circle } from "lucide-react";
import { DocumentUploadCard } from "@/components/ingest/DocumentUploadCard";
import { useDocuments } from "@/lib/documentsContext";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function IngestPage() {
  const { t } = useTranslation();
  const { docA, docB, setDocument } = useDocuments();
  const bothReady = Boolean(docA && docB);

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-2xl font-semibold">{t("ingest.title")}</h1>
        <p className="mt-1 max-w-3xl text-sm text-ink-soft">
          <Trans i18nKey="ingest.description" components={{ strong: <strong /> }} />
        </p>
      </header>

      <div className="grid grid-cols-1 gap-3 rounded-lg border border-rule bg-white p-4 sm:grid-cols-2">
        <DocStep label="A" ready={Boolean(docA)} name={docA?.fileName} />
        <DocStep label="B" ready={Boolean(docB)} name={docB?.fileName} />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <DocumentUploadCard label="A" />
        <DocumentUploadCard label="B" />
      </div>

      {(docA || docB) && !bothReady && (
        <p className="text-sm text-diff">{t("ingest.ingestSecondDoc")}</p>
      )}

      {bothReady && (
        <div className="flex flex-col gap-4 rounded-lg border border-match/30 bg-match-soft px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-2">
            <CheckCircle2 className="mt-0.5 shrink-0 text-match" size={18} />
            <div>
              <p className="text-sm font-medium text-ink">{t("ingest.bothReady")}</p>
              <p className="mt-0.5 text-xs text-ink-soft">
                A: {docA?.fileName} · B: {docB?.fileName}
              </p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link to="/compare">
              <Button variant="brass" size="sm">
                {t("common.compare")} <ArrowRight size={14} />
              </Button>
            </Link>
            <Link to="/chat">
              <Button variant="outline" size="sm">
                {t("ingest.askQuestion")}
              </Button>
            </Link>
            <Link to="/summary">
              <Button variant="outline" size="sm">
                {t("ingest.executiveSummary")}
              </Button>
            </Link>
          </div>
        </div>
      )}

      {(docA || docB) && (
        <div className="text-end">
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setDocument("A", null);
              setDocument("B", null);
            }}
          >
            {t("ingest.clearLoaded")}
          </Button>
        </div>
      )}
    </div>
  );
}

function DocStep({ label, ready, name }: { label: string; ready: boolean; name?: string }) {
  const { t } = useTranslation();

  return (
    <div className={cn("flex items-center gap-3 rounded-md px-3 py-2", ready ? "bg-match-soft" : "bg-paper")}>
      {ready ? <CheckCircle2 className="text-match" size={18} /> : <Circle className="text-ink-faint" size={18} />}
      <div className="min-w-0">
        <div className="text-sm font-medium text-ink">{t("common.document", { label })}</div>
        <div className="truncate text-xs text-ink-soft">{ready ? name : t("ingest.waitingForUpload")}</div>
      </div>
    </div>
  );
}
