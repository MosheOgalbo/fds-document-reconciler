import * as React from "react";
import { useMutation } from "@tanstack/react-query";
import { Send, Loader2 } from "lucide-react";
import { ChatMessage } from "@/components/chat/ChatMessage";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useDocuments, getSessionId } from "@/lib/documentsContext";
import { query, ApiError } from "@/lib/api";
import type { ChatMessage as ChatMessageType } from "@/types/api";

type Scope = "A" | "B" | "cross";

export function ChatPanel() {
  const { docA, docB } = useDocuments();
  const [scope, setScope] = React.useState<Scope>(docA && docB ? "cross" : docA ? "A" : "B");
  const [input, setInput] = React.useState("");
  const [messages, setMessages] = React.useState<ChatMessageType[]>([]);
  const scrollRef = React.useRef<HTMLDivElement>(null);

  const documentIds =
    scope === "cross"
      ? [docA?.document_id, docB?.document_id].filter((id): id is string => Boolean(id))
      : scope === "A"
        ? [docA?.document_id].filter((id): id is string => Boolean(id))
        : [docB?.document_id].filter((id): id is string => Boolean(id));

  const mutation = useMutation({
    mutationFn: (text: string) =>
      query({ session_id: getSessionId(), query: text, document_ids: documentIds }),
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
          content: error instanceof ApiError ? `Error: ${error.message}` : "Something went wrong.",
          createdAt: Date.now(),
        },
      ]);
    },
  });

  React.useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, mutation.isPending]);

  const handleSend = () => {
    const text = input.trim();
    if (!text || documentIds.length === 0) return;
    setMessages((prev) => [
      ...prev,
      { id: crypto.randomUUID(), role: "user", content: text, createdAt: Date.now() },
    ]);
    setInput("");
    mutation.mutate(text);
  };

  return (
    <div className="flex h-[calc(100vh-8rem)] flex-col rounded-lg border border-rule bg-paper-raised">
      <div className="flex items-center justify-between border-b border-rule px-5 py-3">
        <Tabs value={scope} onValueChange={(v) => setScope(v as Scope)}>
          <TabsList>
            <TabsTrigger value="A" disabled={!docA}>Document A</TabsTrigger>
            <TabsTrigger value="B" disabled={!docB}>Document B</TabsTrigger>
            <TabsTrigger value="cross" disabled={!docA || !docB}>Cross-document</TabsTrigger>
          </TabsList>
        </Tabs>
        <span className="font-mono text-[11px] text-ink-faint">{documentIds.length} doc(s) in scope</span>
      </div>

      <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto scrollbar-thin px-5 py-5">
        {messages.length === 0 && (
          <p className="pt-12 text-center text-sm text-ink-faint">
            Ask a question about {scope === "cross" ? "both documents" : `Document ${scope}`}, or
            ask to compare them / summarize changes — those render as structured cards right here
            in the conversation. Answers
            are grounded strictly in retrieved content, with citations.
          </p>
        )}
        {messages.map((m) => (
          <ChatMessage key={m.id} message={m} />
        ))}
        {mutation.isPending && (
          <div className="flex items-center gap-2 text-sm text-ink-faint">
            <Loader2 size={14} className="animate-spin" /> Retrieving and reasoning…
          </div>
        )}
      </div>

      <div className="flex items-end gap-2 border-t border-rule p-4">
        <Textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSend();
            }
          }}
          placeholder={documentIds.length === 0 ? "Load a document for this scope first…" : "Ask a question…"}
          disabled={documentIds.length === 0}
          rows={2}
        />
        <Button
          variant="brass"
          size="icon"
          onClick={handleSend}
          disabled={!input.trim() || documentIds.length === 0 || mutation.isPending}
        >
          <Send size={16} />
        </Button>
      </div>
    </div>
  );
}
