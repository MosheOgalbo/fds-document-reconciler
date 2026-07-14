import { NavLink } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { navItems } from "@/components/layout/nav-items";
import { NavTooltip } from "@/components/ui/nav-tooltip";
import { useSidebar } from "@/lib/sidebarContext";
import { useDocuments } from "@/lib/documentsContext";
import { cn } from "@/lib/utils";

export function Sidebar() {
  const { t } = useTranslation();
  const { collapsed, toggleCollapsed } = useSidebar();
  const { docA, docB } = useDocuments();

  return (
    <aside
      className={cn(
        "sticky top-0 hidden h-screen shrink-0 flex-col bg-ink text-paper transition-[width] duration-200 ease-out md:flex",
        collapsed ? "w-[4.25rem]" : "w-64",
      )}
    >
      <div className={cn("flex items-start gap-2 py-5", collapsed ? "flex-col px-2" : "px-5")}>
        {!collapsed && (
          <div className="min-w-0 flex-1">
            <div className="font-display text-xl font-semibold tracking-tight">{t("app.title")}</div>
            <div className="mt-1 text-xs text-paper/50">{t("app.subtitle")}</div>
          </div>
        )}
        <button
          type="button"
          onClick={toggleCollapsed}
          aria-label={collapsed ? t("nav.expandSidebar") : t("nav.collapseSidebar")}
          title={collapsed ? t("nav.expandSidebar") : t("nav.collapseSidebar")}
          className={cn(
            "flex h-9 w-9 shrink-0 items-center justify-center rounded-md text-paper/60 transition-colors hover:bg-white/10 hover:text-paper",
            collapsed && "mx-auto",
          )}
        >
          {collapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}
        </button>
      </div>

      <nav className="flex flex-col gap-0.5 px-2" aria-label={t("nav.mainNavigation")}>
        {navItems.map(({ to, key, icon: Icon, end }) => {
          const link = (
            <NavLink
              to={to}
              end={end}
              aria-label={t(key)}
              className={({ isActive }) =>
                cn(
                  "flex items-center rounded-md py-2 text-sm font-medium transition-colors",
                  collapsed ? "justify-center px-2" : "gap-2.5 px-3",
                  isActive ? "bg-white/10 text-white" : "text-paper/60 hover:bg-white/5 hover:text-paper",
                )
              }
            >
              <Icon size={18} strokeWidth={2} aria-hidden />
              {!collapsed && <span className="truncate">{t(key)}</span>}
            </NavLink>
          );

          return (
            <div key={to}>
              {collapsed ? <NavTooltip label={t(key)}>{link}</NavTooltip> : link}
            </div>
          );
        })}
      </nav>

      <div className={cn("mt-auto py-5", collapsed ? "px-2" : "px-5")}>
        {!collapsed && (
          <div className="text-[11px] font-medium uppercase tracking-wider text-paper/40">{t("ledger.title")}</div>
        )}
        <div className={cn("space-y-1.5 font-mono text-xs", !collapsed && "mt-2")}>
          <DocStatus label="A" doc={docA} collapsed={collapsed} />
          <DocStatus label="B" doc={docB} collapsed={collapsed} />
        </div>
      </div>
    </aside>
  );
}

function DocStatus({
  label,
  doc,
  collapsed,
}: {
  label: string;
  doc: { document_name: string; version: string } | null;
  collapsed: boolean;
}) {
  const { t } = useTranslation();
  const statusText = doc ? `${doc.document_name} · ${doc.version}` : t("ledger.notLoaded");

  const badge = (
    <span
      className={cn(
        "flex h-5 w-5 shrink-0 items-center justify-center rounded-sm text-[10px] font-semibold",
        doc ? "bg-brass text-white" : "bg-white/10 text-paper/40",
      )}
    >
      {label}
    </span>
  );

  if (collapsed) {
    return (
      <NavTooltip label={`${t("common.document", { label })}: ${statusText}`}>
        <div className="flex justify-center py-0.5">{badge}</div>
      </NavTooltip>
    );
  }

  return (
    <div className="flex items-center gap-2">
      {badge}
      <span className={cn("truncate", doc ? "text-paper/80" : "text-paper/30")}>{statusText}</span>
    </div>
  );
}
