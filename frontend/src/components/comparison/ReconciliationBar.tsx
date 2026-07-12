import type { ComparisonReport } from "@/types/api";

export function ReconciliationBar({ report }: { report: ComparisonReport }) {
  const matchCount = report.match.length;
  const diffCount = report.diff.length;
  const missingCount = report.missing.length;
  const total = matchCount + diffCount + missingCount || 1;

  const segments = [
    { label: "Match", count: matchCount, color: "bg-match" },
    { label: "Diff", count: diffCount, color: "bg-diff" },
    { label: "Missing", count: missingCount, color: "bg-missing" },
  ];

  return (
    <div>
      <div className="flex h-3 w-full overflow-hidden rounded-full bg-ink/5">
        {segments.map(
          (s) =>
            s.count > 0 && (
              <div
                key={s.label}
                className={s.color}
                style={{ width: `${(s.count / total) * 100}%` }}
                title={`${s.label}: ${s.count}`}
              />
            ),
        )}
      </div>
      <div className="mt-3 flex items-center gap-6 font-mono text-xs text-ink-soft">
        {segments.map((s) => (
          <div key={s.label} className="flex items-center gap-1.5">
            <span className={`h-2 w-2 rounded-full ${s.color}`} />
            {s.label} <span className="text-ink">{s.count}</span>
          </div>
        ))}
        <div className="ml-auto text-ink-faint">{total} items reconciled</div>
      </div>
    </div>
  );
}
