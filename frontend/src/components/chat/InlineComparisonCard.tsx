import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ArrowUpRight } from "lucide-react";
import { ReconciliationBar } from "@/components/comparison/ReconciliationBar";
import { Badge } from "@/components/ui/badge";
import type { ComparisonReport } from "@/types/api";

export function InlineComparisonCard({ report }: { report: ComparisonReport }) {
  const { t } = useTranslation();

  return (
    <div className="w-full max-w-md rounded-lg border border-rule bg-white p-4">
      <div className="mb-3 flex items-center justify-between">
        <span className="font-display text-sm font-semibold text-ink">{t("compare.comparisonResult")}</span>
        <Link to="/compare" className="flex items-center gap-1 text-xs text-brass hover:underline">
          {t("common.fullView")} <ArrowUpRight size={12} />
        </Link>
      </div>

      <ReconciliationBar report={report} />

      {(report.diff.length > 0 || report.missing.length > 0) && (
        <ul className="mt-4 space-y-2 border-t border-rule pt-3">
          {report.diff.slice(0, 2).map((d, i) => (
            <li key={`d-${i}`} className="text-xs">
              <Badge variant="diff" className="mb-1">
                {t("status.diff")}
              </Badge>
              <p className="text-ink-soft">{d.reason}</p>
            </li>
          ))}
          {report.missing.slice(0, 1).map((m, i) => (
            <li key={`m-${i}`} className="text-xs">
              <Badge variant="missing" className="mb-1">
                {t("status.missing")}
              </Badge>
              <p className="text-ink-soft">{m.text}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
