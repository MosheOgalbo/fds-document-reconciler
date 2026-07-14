import { useTranslation } from "react-i18next";
import { AlertTriangle, ShieldCheck } from "lucide-react";
import { CitationBadge } from "@/components/chat/CitationBadge";
import { InlineComparisonCard } from "@/components/chat/InlineComparisonCard";
import { InlineSummaryCard } from "@/components/chat/InlineSummaryCard";
import type { ChatMessage as ChatMessageType } from "@/types/api";
import { cn } from "@/lib/utils";

export function ChatMessage({ message }: { message: ChatMessageType }) {
  const { t } = useTranslation();
  const isUser = message.role === "user";

  return (
    <div className={cn("flex", isUser ? "justify-end" : "justify-start")}>
      <div className={cn("max-w-[85%] space-y-2", isUser && "flex flex-col items-end")}>
        {!isUser && message.comparison && <InlineComparisonCard report={message.comparison} />}
        {!isUser && message.executiveSummary && <InlineSummaryCard summary={message.executiveSummary} />}

        {(!message.comparison && !message.executiveSummary) || isUser ? (
          <div
            className={cn(
              "rounded-lg px-4 py-2.5 text-sm leading-relaxed",
              isUser ? "bg-ink text-paper" : "border border-rule bg-white text-ink",
            )}
          >
            {message.content}
          </div>
        ) : null}

        {!isUser && message.isGrounded === false && (
          <div className="flex items-center gap-1.5 text-xs text-diff">
            <AlertTriangle size={13} /> {t("chat.lowConfidence")}
          </div>
        )}
        {!isUser && message.isGrounded === true && message.citations && message.citations.length > 0 && (
          <div className="flex items-center gap-1.5 text-xs text-match">
            <ShieldCheck size={13} /> {t("chat.grounded")}
          </div>
        )}

        {!isUser && message.citations && message.citations.length > 0 && (
          <div className="grid gap-1.5 sm:grid-cols-2">
            {message.citations.map((c, i) => (
              <CitationBadge key={i} citation={c} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
