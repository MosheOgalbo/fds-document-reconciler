import * as React from "react";
import { useMutation } from "@tanstack/react-query";
import { Send, Loader2, Sparkles } from "lucide-react";
import { ChatMessage } from "@/components/chat/ChatMessage";
import { AgentTraceBar } from "@/components/chat/AgentTraceBar";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { useDocuments, getFreeChatSessionId } from "@/lib/documentsContext";
import { query, ApiError } from "@/lib/api";
import type { ChatMessage as ChatMessageType } from "@/types/api";

const STARTER_PROMPTS = [
  "What is Phase A in the newer document?",
  "What changed in the NA uplift rules between versions?",
  "Compare both documents — what matches, changed, or is missing?",
  "Give me the top 10 most important changes as an executive summary.",
  "Explain the three-phase transformation strategy in plain language.",
];

export function FreeChatPanel() {
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
          content: error instanceof ApiError ? error.message : "Something went wrong.",
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
            <span className="font-display text-sm font-semibold text-ink">Free chat</span>
          </div>
          <p className="mt-0.5 text-xs text-ink-soft">
            Ask anything — the Router Agent picks the workflow (chat, compare, or summary).
          </p>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {loadedDocs.length === 0 ? (
            <Badge variant="neutral">No documents loaded</Badge>
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
            <p className="text-sm text-ink-soft">
              Natural-language Q&amp;A over your ingested FDS documents. The backend LangGraph
              pipeline routes each question to the right agents — retrieval, comparison, summary,
              validation, and citations — with conversation memory across turns.
            </p>
            {documentIds.length > 0 && (
              <div className="flex flex-wrap justify-center gap-2">
                {STARTER_PROMPTS.map((prompt) => (
                  <button
                    key={prompt}
                    type="button"
                    onClick={() => sendMessage(prompt)}
                    className="rounded-full border border-rule bg-white px-3 py-1.5 text-left text-xs text-ink-soft transition-colors hover:border-brass/40 hover:bg-brass-soft hover:text-ink"
                  >
                    {prompt}
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
              <AgentTraceBar intent={m.intent} agentTrace={m.agentTrace} className="pl-1" />
            )}
          </div>
        ))}

        {mutation.isPending && (
          <div className="flex items-center gap-2 text-sm text-ink-faint">
            <Loader2 size={14} className="animate-spin" />
            Router → Retrieval → Agents…
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
              documentIds.length === 0
                ? "Load documents on the Documents page first…"
                : "Ask freely about your documents…"
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
            aria-label="Send message"
          >
            <Send size={16} />
          </Button>
        </div>
      </div>
    </div>
  );
}
