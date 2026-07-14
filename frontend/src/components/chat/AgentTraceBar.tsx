import { useTranslation } from "react-i18next";
import { Bot } from "lucide-react";
import type { Intent } from "@/types/api";
import { cn } from "@/lib/utils";

export function AgentTraceBar({
  intent,
  agentTrace,
  className,
}: {
  intent?: Intent;
  agentTrace?: string[];
  className?: string;
}) {
  const { t } = useTranslation();

  if (!intent && (!agentTrace || agentTrace.length === 0)) return null;

  return (
    <div className={cn("flex flex-wrap items-center gap-2 text-[11px]", className)}>
      {intent && (
        <span className="rounded-full bg-brass-soft px-2 py-0.5 font-medium text-brass">
          {t(`intent.${intent}`)}
        </span>
      )}
      {agentTrace && agentTrace.length > 0 && (
        <span className="inline-flex items-center gap-1 font-mono text-ink-faint">
          <Bot size={11} />
          {agentTrace.join(" → ")}
        </span>
      )}
    </div>
  );
}
