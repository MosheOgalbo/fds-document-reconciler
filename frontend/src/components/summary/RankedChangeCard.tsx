import { Badge } from "@/components/ui/badge";
import type { RankedChange } from "@/types/api";
import { cn } from "@/lib/utils";

const severityVariant: Record<RankedChange["severity"], "missing" | "diff" | "brass" | "neutral"> = {
  critical: "missing",
  high: "diff",
  medium: "brass",
  low: "neutral",
};

export function RankedChangeCard({ change }: { change: RankedChange }) {
  return (
    <div className="flex gap-4 rounded-lg border border-rule bg-paper-raised p-4">
      <div
        className={cn(
          "flex h-8 w-8 shrink-0 items-center justify-center rounded-full font-display text-sm font-semibold",
          "bg-ink text-paper",
        )}
      >
        {change.rank}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <h3 className="font-medium text-ink">{change.title}</h3>
          <Badge variant={severityVariant[change.severity]}>{change.severity}</Badge>
        </div>
        <p className="mt-1 text-sm text-ink-soft">{change.description}</p>
        <p className="mt-2 border-t border-rule pt-2 text-xs text-ink-faint">
          <span className="font-medium text-brass-dark">Why it ranks here: </span>
          {change.ranking_rationale}
        </p>
      </div>
    </div>
  );
}
