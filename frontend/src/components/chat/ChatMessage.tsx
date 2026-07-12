import { AlertTriangle, ShieldCheck } from "lucide-react";
import { CitationBadge } from "@/components/chat/CitationBadge";
import { InlineComparisonCard } from "@/components/chat/InlineComparisonCard";
import { InlineSummaryCard } from "@/components/chat/InlineSummaryCard";
import type { ChatMessage as ChatMessageType } from "@/types/api";
import { cn } from "@/lib/utils";

export function ChatMessage({ message }: { message: ChatMessageType }) {
  const isUser = message.role === "user";

  return (
    <div className={cn("flex", isUser ? "justify-end" : "justify-start")}>
      <div className={cn("max-w-[85%] space-y-2", isUser && "flex flex-col items-end")}>
        {/* Structured task result — rendered as a styled component instead of
            flattened text when the backend returned comparison/summary data. */}
        {!isUser && message.comparison && <InlineComparisonCard report={message.comparison} />}
        {!isUser && message.executiveSummary && <InlineSummaryCard summary={message.executiveSummary} />}

        {/* Plain-text answer bubble — always shown for chat intents; shown for
            compare/summary intents only if no structured card covers it (defensive fallback). */}
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
            <AlertTriangle size={13} /> Low confidence — verify against the source
          </div>
        )}
        {!isUser && message.isGrounded === true && message.citations && message.citations.length > 0 && (
          <div className="flex items-center gap-1.5 text-xs text-match">
            <ShieldCheck size={13} /> Grounded in retrieved content
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
