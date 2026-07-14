import { Link } from "react-router-dom";
import { useTranslation, Trans } from "react-i18next";
import { FileStack } from "lucide-react";
import { FreeChatPanel } from "@/components/chat/FreeChatPanel";
import { useDocuments } from "@/lib/documentsContext";
import { Button } from "@/components/ui/button";

export function FreeChatPage() {
  const { t } = useTranslation();
  const { docA, docB } = useDocuments();
  const hasDocs = Boolean(docA || docB);

  return (
    <div className="flex h-[calc(100vh-3rem)] flex-col gap-4">
      <header className="shrink-0">
        <h1 className="text-2xl font-semibold">{t("freeChat.title")}</h1>
        <p className="mt-1 text-sm text-ink-soft">{t("freeChat.description")}</p>
      </header>

      {!hasDocs ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-4 rounded-xl border border-dashed border-rule bg-paper-raised/50 px-6 text-center">
          <p className="max-w-md text-sm text-ink-soft">
            <Trans i18nKey="freeChat.emptyNoDocs" components={{ code: <code className="font-mono text-xs" /> }} />
          </p>
          <Link to="/">
            <Button variant="brass" size="sm">
              <FileStack size={14} /> {t("freeChat.loadDocuments")}
            </Button>
          </Link>
        </div>
      ) : (
        <FreeChatPanel />
      )}
    </div>
  );
}
