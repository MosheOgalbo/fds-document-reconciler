import * as React from "react";
import { useTranslation } from "react-i18next";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ReconciliationBar } from "@/components/comparison/ReconciliationBar";
import { MissingCard, DiffCard, MatchCard } from "@/components/comparison/ComparisonCards";
import type { ComparisonReport } from "@/types/api";

export function ComparisonView({ report }: { report: ComparisonReport }) {
  const { t } = useTranslation();
  const [tab, setTab] = React.useState<"diff" | "missing" | "match">("diff");

  const counts = {
    diff: report.diff.length,
    missing: report.missing.length,
    match: report.match.length,
  };

  return (
    <div className="space-y-6">
      <div className="rounded-lg border border-rule bg-paper-raised p-5">
        <ReconciliationBar report={report} />
      </div>

      <Tabs value={tab} onValueChange={(v) => setTab(v as typeof tab)}>
        <TabsList>
          <TabsTrigger value="diff">
            {t("status.diff")} ({counts.diff})
          </TabsTrigger>
          <TabsTrigger value="missing">
            {t("status.missing")} ({counts.missing})
          </TabsTrigger>
          <TabsTrigger value="match">
            {t("status.match")} ({counts.match})
          </TabsTrigger>
        </TabsList>
      </Tabs>

      <div className="space-y-3">
        {tab === "diff" &&
          (report.diff.length ? (
            report.diff.map((item, i) => <DiffCard key={i} item={item} />)
          ) : (
            <EmptyState text={t("compare.emptyDiff")} />
          ))}
        {tab === "missing" &&
          (report.missing.length ? (
            report.missing.map((item, i) => <MissingCard key={i} item={item} />)
          ) : (
            <EmptyState text={t("compare.emptyMissing")} />
          ))}
        {tab === "match" &&
          (report.match.length ? (
            report.match.map((item, i) => <MatchCard key={i} item={item} />)
          ) : (
            <EmptyState text={t("compare.emptyMatch")} />
          ))}
      </div>
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return (
    <p className="rounded-md border border-dashed border-rule px-4 py-8 text-center text-sm text-ink-faint">
      {text}
    </p>
  );
}
