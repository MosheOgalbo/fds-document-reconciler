import { Link } from "react-router-dom";
import { ArrowUpRight } from "lucide-react";
import { ReconciliationBar } from "@/components/comparison/ReconciliationBar";
import { Badge } from "@/components/ui/badge";
import type { ComparisonReport } from "@/types/api";

export function InlineComparisonCard({ report }: { report: ComparisonReport }) {
  const highlights = [...report.diff.slice(0, 2), ...report.missing.slice(0, 1)];

  return (
    <div className="w-full max-w-md rounded-lg border border-rule bg-white p-4">
      <div className="mb-3 flex items-center justify-between">
        <span className="font-display text-sm font-semibold text-ink">Comparison result</span>
        <Link to="/compare" className="flex items-center gap-1 text-xs text-brass hover:underline">
          Full view <ArrowUpRight size={12} />
        </Link>
      </div>

      <ReconciliationBar report={report} />

      {highlights.length > 0 && (
        <ul className="mt-4 space-y-2 border-t border-rule pt-3">
          {report.diff.slice(0, 2).map((d, i) => (
            <li key={`d-${i}`} className="text-xs">
              <Badge variant="diff" className="mb-1">
                Diff
              </Badge>
              <p className="text-ink-soft">{d.reason}</p>
            </li>
          ))}
          {report.missing.slice(0, 1).map((m, i) => (
            <li key={`m-${i}`} className="text-xs">
              <Badge variant="missing" className="mb-1">
                Missing
              </Badge>
              <p className="text-ink-soft">{m.text}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
