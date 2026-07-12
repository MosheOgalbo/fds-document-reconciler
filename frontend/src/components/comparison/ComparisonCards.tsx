import { Badge } from "@/components/ui/badge";
import type { DiffItem, MatchItem, MissingItem } from "@/types/api";

export function MissingCard({ item }: { item: MissingItem }) {
  return (
    <div className="rounded-md border border-missing/20 bg-missing-soft/40 p-4">
      <div className="mb-2 flex items-center justify-between">
        <Badge variant="missing">Missing</Badge>
        <span className="font-mono text-[11px] text-ink-faint">
          {item.source_file} · {item.location}
        </span>
      </div>
      <p className="text-sm text-ink">{item.text}</p>
    </div>
  );
}

export function DiffCard({ item }: { item: DiffItem }) {
  return (
    <div className="rounded-md border border-diff/20 bg-diff-soft/40 p-4">
      <div className="mb-2 flex items-center justify-between">
        <Badge variant="diff">Diff</Badge>
      </div>
      <div className="grid grid-cols-2 gap-3 text-sm">
        <div>
          <div className="mb-1 font-mono text-[11px] text-ink-faint">A · {item.sourceA}</div>
          <p className="text-ink-soft line-through decoration-missing/40">{item.docA_text}</p>
        </div>
        <div>
          <div className="mb-1 font-mono text-[11px] text-ink-faint">B · {item.sourceB}</div>
          <p className="text-ink">{item.docB_text}</p>
        </div>
      </div>
      <p className="mt-3 border-t border-diff/20 pt-2 text-xs text-ink-soft">
        <span className="font-medium text-diff">Why: </span>
        {item.reason}
      </p>
    </div>
  );
}

export function MatchCard({ item }: { item: MatchItem }) {
  return (
    <div className="rounded-md border border-match/20 bg-match-soft/40 p-4">
      <div className="mb-2 flex items-center justify-between">
        <Badge variant="match">Match</Badge>
        <span className="font-mono text-[11px] text-ink-faint">{item.source}</span>
      </div>
      <p className="text-sm text-ink-soft">{item.textA}</p>
    </div>
  );
}
