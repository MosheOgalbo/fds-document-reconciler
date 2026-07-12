import { RankedChangeCard } from "@/components/summary/RankedChangeCard";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { ExecutiveSummary } from "@/types/api";

export function ExecutiveSummaryView({ summary }: { summary: ExecutiveSummary }) {
  return (
    <div className="space-y-8">
      <section>
        <h2 className="mb-3 font-display text-lg font-semibold text-ink">
          Top {summary.top_important_changes.length} Changes — Ranked by Business Importance
        </h2>
        <div className="space-y-3">
          {summary.top_important_changes
            .slice()
            .sort((a, b) => a.rank - b.rank)
            .map((change) => (
              <RankedChangeCard key={change.rank} change={change} />
            ))}
        </div>
      </section>

      <section className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <ImpactCard title="Business Impact" text={summary.business_impact} />
        <ImpactCard title="Architecture Impact" text={summary.architecture_impact} />
        <ImpactCard title="Workflow Impact" text={summary.workflow_impact} />
      </section>
    </div>
  );
}

function ImpactCard({ title, text }: { title: string; text: string }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-ink-soft">{text}</p>
      </CardContent>
    </Card>
  );
}
