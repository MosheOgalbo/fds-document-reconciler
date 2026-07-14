import { Languages } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { AppLocale } from "@/i18n";
import { cn } from "@/lib/utils";

export function LanguageSwitcher({ className }: { className?: string }) {
  const { i18n, t } = useTranslation();
  const current = (i18n.language?.startsWith("he") ? "he" : "en") as AppLocale;

  const setLocale = (locale: AppLocale) => {
    if (locale !== current) void i18n.changeLanguage(locale);
  };

  return (
    <div
      className={cn("inline-flex items-center gap-2", className)}
      role="group"
      aria-label={t("toolbar.language")}
    >
      <Languages size={15} className="shrink-0 text-ink-faint" aria-hidden />
      <div className="inline-flex rounded-md border border-rule bg-paper p-0.5 shadow-sm">
        {(["en", "he"] as const).map((locale) => (
          <button
            key={locale}
            type="button"
            onClick={() => setLocale(locale)}
            aria-pressed={current === locale}
            className={cn(
              "rounded px-2.5 py-1 text-xs font-medium transition-colors",
              current === locale
                ? "bg-ink text-paper shadow-sm"
                : "text-ink-soft hover:bg-brass-soft/60 hover:text-ink",
            )}
          >
            {locale === "en" ? "EN" : "עב"}
          </button>
        ))}
      </div>
    </div>
  );
}
