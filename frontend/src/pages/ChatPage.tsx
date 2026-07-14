import { useTranslation } from "react-i18next";
import { useDocuments } from "@/lib/documentsContext";
import { ChatPanel } from "@/components/chat/ChatPanel";
import { DocumentsRequiredNotice } from "@/components/layout/DocumentsRequiredNotice";

export function ChatPage() {
  const { t } = useTranslation();
  const { docA, docB } = useDocuments();

  if (!docA && !docB) {
    return <DocumentsRequiredNotice messageKey="chat.docsRequired" />;
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">{t("chat.title")}</h1>
        <p className="mt-1 text-sm text-ink-soft">{t("chat.description")}</p>
      </header>
      <ChatPanel />
    </div>
  );
}
