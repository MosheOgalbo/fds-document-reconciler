import { useQuery } from "@tanstack/react-query";
import { useTranslation, Trans } from "react-i18next";
import { AlertTriangle, WifiOff } from "lucide-react";
import { checkHealth } from "@/lib/api";

export function ConfigurationBanner() {
  const { t } = useTranslation();
  const { data, isError } = useQuery({
    queryKey: ["health"],
    queryFn: checkHealth,
    retry: false,
    refetchInterval: 30_000,
  });

  if (isError) {
    return (
      <div className="flex items-center gap-2 border-b border-missing/30 bg-missing-soft px-6 py-2.5 text-sm text-missing">
        <WifiOff size={15} className="shrink-0" />
        <span>
          <Trans
            i18nKey="banner.backendUnreachable"
            components={{ code: <code className="font-mono" /> }}
          />
        </span>
      </div>
    );
  }

  if (!data) return null;

  if (!data.gemini_configured && !data.openai_configured) {
    return (
      <div className="flex items-center gap-2 border-b border-diff/30 bg-diff-soft px-6 py-2.5 text-sm text-diff">
        <AlertTriangle size={15} className="shrink-0" />
        <span>
          <Trans
            i18nKey="banner.apiKeyMissing"
            components={{
              strong: <strong />,
              code: <code className="font-mono" />,
              a: (
                <a
                  href="https://aistudio.google.com/apikey"
                  className="underline"
                  target="_blank"
                  rel="noreferrer"
                />
              ),
            }}
          />
        </span>
      </div>
    );
  }

  return null;
}
