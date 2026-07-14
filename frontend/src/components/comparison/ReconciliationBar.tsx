import { useTranslation } from "react-i18next";
import type { ComparisonReport } from "@/types/api";

export function ReconciliationBar({ report }: { report: ComparisonReport }) {
  const { t } = useTranslation();
  const matchCount = report.match.length;
  const diffCount = report.diff.length;
  const missingCount = report.missing.length;
  const total = matchCount + diffCount + missingCount || 1;

  const segments = [
    { key: "match" as const, count: matchCount, color: "bg-match" },
    { key: "diff" as const, count: diffCount, color: "bg-diff" },
    { key: "missing" as const, count: missingCount, color: "bg-missing" },
  ];

  return (
    <div>
      <div className="flex h-3 w-full overflow-hidden rounded-full bg-ink/5">
        {segments.map(
          (s) =>
            s.count > 0 && (
              <div
                key={s.key}
                className={s.color}
                style={{ width: `${(s.count / total) * 100}%` }}
                title={`${t(`status.${s.key}`)}: ${s.count}`}
              />
            ),
        )}
      </div>
      <div className="mt-3 flex items-center gap-6 font-mono text-xs text-ink-soft">
        {segments.map((s) => (
          <div key={s.key} className="flex items-center gap-1.5">
            <span className={`h-2 w-2 rounded-full ${s.color}`} />
            {t(`status.${s.key}`)} <span className="text-ink">{s.count}</span>
          </div>
        ))}
        <div className="ms-auto text-ink-faint">{t("status.itemsReconciled", { count: total })}</div>
      </div>
    </div>
  );
}
