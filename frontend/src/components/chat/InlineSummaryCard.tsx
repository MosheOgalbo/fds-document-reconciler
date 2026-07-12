import { Link } from "react-router-dom";
import { ArrowUpRight } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { ExecutiveSummary } from "@/types/api";

const severityVariant: Record<string, "missing" | "diff" | "brass" | "neutral"> = {
  critical: "missing",
  high: "diff",
  medium: "brass",
  low: "neutral",
};

export function InlineSummaryCard({ summary }: { summary: ExecutiveSummary }) {
  const top = summary.top_important_changes.slice().sort((a, b) => a.rank - b.rank).slice(0, 5);

  return (
    <div className="w-full max-w-md rounded-lg border border-rule bg-white p-4">
      <div className="mb-3 flex items-center justify-between">
        <span className="font-display text-sm font-semibold text-ink">
          Top {summary.top_important_changes.length} changes
        </span>
        <Link to="/summary" className="flex items-center gap-1 text-xs text-brass hover:underline">
          Full view <ArrowUpRight size={12} />
        </Link>
      </div>

      <ol className="space-y-2">
        {top.map((c) => (
          <li key={c.rank} className="flex items-start gap-2 text-xs">
            <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-ink text-[10px] font-semibold text-paper">
              {c.rank}
            </span>
            <div className="min-w-0">
              <div className="flex items-center gap-1.5">
                <span className="font-medium text-ink">{c.title}</span>
                <Badge variant={severityVariant[c.severity]}>{c.severity}</Badge>
              </div>
              <p className="text-ink-soft">{c.description}</p>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
