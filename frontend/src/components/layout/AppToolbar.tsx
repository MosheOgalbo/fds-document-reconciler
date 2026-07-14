import { useTranslation } from "react-i18next";
import { useSidebar } from "@/lib/sidebarContext";
import { PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { LanguageSwitcher } from "@/components/layout/LanguageSwitcher";

export function AppToolbar() {
  const { t } = useTranslation();
  const { collapsed, toggleCollapsed } = useSidebar();

  return (
    <header className="sticky top-0 z-10 flex h-12 shrink-0 items-center justify-between gap-3 border-b border-rule bg-paper-raised/95 px-4 backdrop-blur-sm sm:px-5">
      <button
        type="button"
        onClick={toggleCollapsed}
        aria-label={collapsed ? t("nav.expandSidebar") : t("nav.collapseSidebar")}
        title={collapsed ? t("nav.expandSidebar") : t("nav.collapseSidebar")}
        className="hidden h-9 w-9 items-center justify-center rounded-md text-ink-soft transition-colors hover:bg-paper hover:text-ink md:inline-flex"
      >
        {collapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}
      </button>
      <div className="font-display text-base font-semibold text-ink md:hidden">{t("app.title")}</div>
      <LanguageSwitcher className="ms-auto md:ms-0" />
    </header>
  );
}
