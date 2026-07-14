import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { FileStack } from "lucide-react";
import { Button } from "@/components/ui/button";

export function DocumentsRequiredNotice({ messageKey }: { messageKey: string }) {
  const { t } = useTranslation();

  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-rule px-6 py-16 text-center">
      <FileStack className="text-ink-faint" size={28} />
      <p className="max-w-sm text-sm text-ink-soft">{t(messageKey)}</p>
      <Link to="/">
        <Button variant="brass" size="sm">
          {t("common.goToDocuments")}
        </Button>
      </Link>
    </div>
  );
}
