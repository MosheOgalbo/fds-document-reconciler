import * as React from "react";
import { useMutation } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Send, Loader2, Sparkles } from "lucide-react";
import { ChatMessage } from "@/components/chat/ChatMessage";
import { AgentTraceBar } from "@/components/chat/AgentTraceBar";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { useDocuments, getFreeChatSessionId } from "@/lib/documentsContext";
import { query, ApiError } from "@/lib/api";
import type { ChatMessage as ChatMessageType } from "@/types/api";

const STARTER_KEYS = [
  "freeChat.starters.phaseA",
  "freeChat.starters.naUplift",
  "freeChat.starters.compare",
  "freeChat.starters.top10",
  "freeChat.starters.threePhase",
] as const;

export function FreeChatPanel() {
  const { t } = useTranslation();
  const { docA, docB, documentIds } = useDocuments();
  const [input, setInput] = React.useState("");
  const [messages, setMessages] = React.useState<ChatMessageType[]>([]);
  const scrollRef = React.useRef<HTMLDivElement>(null);

  const mutation = useMutation({
    mutationFn: (text: string) =>
      query({
        session_id: getFreeChatSessionId(),
        query: text,
        document_ids: documentIds,
      }),
    onSuccess: (result) => {
      setMessages((prev) => [
        ...prev,
        {
          id: result.request_id,
          role: "assistant",
          content: result.answer,
          intent: result.intent,
          citations: result.citations,
          comparison: result.comparison,
          executiveSummary: result.executive_summary,
          isGrounded: result.is_grounded,
          warnings: result.warnings,
          agentTrace: result.agent_trace,
          createdAt: Date.now(),
        },
      ]);
    },
    onError: (error) => {
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: error instanceof ApiError ? error.message : t("chat.somethingWrong"),
          createdAt: Date.now(),
        },
      ]);
    },
  });

  React.useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, mutation.isPending]);

  const sendMessage = (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || documentIds.length === 0 || mutation.isPending) return;
    setMessages((prev) => [
      ...prev,
      { id: crypto.randomUUID(), role: "user", content: trimmed, createdAt: Date.now() },
    ]);
    setInput("");
    mutation.mutate(trimmed);
  };

  const loadedDocs = [docA, docB].filter(Boolean);

  return (
    <div className="flex min-h-0 flex-1 flex-col rounded-xl border border-rule bg-paper-raised shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-rule px-5 py-3">
        <div>
          <div className="flex items-center gap-2">
            <Sparkles size={16} className="text-brass" />
            <span className="font-display text-sm font-semibold text-ink">{t("freeChat.panelTitle")}</span>
          </div>
          <p className="mt-0.5 text-xs text-ink-soft">{t("freeChat.panelSubtitle")}</p>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {loadedDocs.length === 0 ? (
            <Badge variant="neutral">{t("freeChat.noDocsLoaded")}</Badge>
          ) : (
            loadedDocs.map((doc) => (
              <Badge key={doc!.document_id} variant="brass" className="font-mono text-[10px]">
                {doc!.label}: {doc!.version}
              </Badge>
            ))
          )}
        </div>
      </div>

      <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto scrollbar-thin px-5 py-5">
        {messages.length === 0 && (
          <div className="mx-auto max-w-xl space-y-5 pt-8 text-center">
            <p className="text-sm text-ink-soft">{t("freeChat.intro")}</p>
            {documentIds.length > 0 && (
              <div className="flex flex-wrap justify-center gap-2">
                {STARTER_KEYS.map((key) => (
                  <button
                    key={key}
                    type="button"
                    onClick={() => sendMessage(t(key))}
                    className="rounded-full border border-rule bg-white px-3 py-1.5 text-start text-xs text-ink-soft transition-colors hover:border-brass/40 hover:bg-brass-soft hover:text-ink"
                  >
                    {t(key)}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {messages.map((m) => (
          <div key={m.id} className="space-y-1.5">
            <ChatMessage message={m} />
            {m.role === "assistant" && (
              <AgentTraceBar intent={m.intent} agentTrace={m.agentTrace} className="ps-1" />
            )}
          </div>
        ))}

        {mutation.isPending && (
          <div className="flex items-center gap-2 text-sm text-ink-faint">
            <Loader2 size={14} className="animate-spin" />
            {t("freeChat.processing")}
          </div>
        )}
      </div>

      <div className="border-t border-rule p-4">
        <div className="flex items-end gap-2">
          <Textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                sendMessage(input);
              }
            }}
            placeholder={
              documentIds.length === 0 ? t("freeChat.placeholderNoDoc") : t("freeChat.placeholderAsk")
            }
            disabled={documentIds.length === 0}
            rows={2}
            className="min-h-[52px] resize-none"
          />
          <Button
            variant="brass"
            size="icon"
            onClick={() => sendMessage(input)}
            disabled={!input.trim() || documentIds.length === 0 || mutation.isPending}
            aria-label={t("common.sendMessage")}
          >
            <Send size={16} />
          </Button>
        </div>
      </div>
    </div>
  );
}
