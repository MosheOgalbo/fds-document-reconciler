import { NavLink } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { FileStack, MessagesSquare, GitCompareArrows, ListOrdered, Sparkles } from "lucide-react";
import { useDocuments } from "@/lib/documentsContext";
import { cn } from "@/lib/utils";

const navItems = [
  { to: "/", key: "nav.documents", icon: FileStack, end: true as const },
  { to: "/free-chat", key: "nav.freeChat", icon: Sparkles, end: false as const },
  { to: "/compare", key: "nav.compare", icon: GitCompareArrows, end: false as const },
  { to: "/chat", key: "nav.ask", icon: MessagesSquare, end: false as const },
  { to: "/summary", key: "nav.executiveSummary", icon: ListOrdered, end: false as const },
] as const;

export function Sidebar() {
  const { t } = useTranslation();
  const { docA, docB } = useDocuments();

  return (
    <aside className="sticky top-0 flex h-screen w-64 shrink-0 flex-col bg-ink text-paper">
      <div className="px-5 py-6">
        <div className="font-display text-xl font-semibold tracking-tight">{t("app.title")}</div>
        <div className="mt-1 text-xs text-paper/50">{t("app.subtitle")}</div>
      </div>

      <nav className="flex flex-col gap-0.5 px-3">
        {navItems.map(({ to, key, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                isActive ? "bg-white/10 text-white" : "text-paper/60 hover:bg-white/5 hover:text-paper",
              )
            }
          >
            <Icon size={16} strokeWidth={2} />
            {t(key)}
          </NavLink>
        ))}
      </nav>

      <div className="mt-auto px-5 py-5">
        <div className="text-[11px] font-medium uppercase tracking-wider text-paper/40">{t("ledger.title")}</div>
        <div className="mt-2 space-y-1.5 font-mono text-xs">
          <DocStatus label="A" doc={docA} />
          <DocStatus label="B" doc={docB} />
        </div>
      </div>
    </aside>
  );
}

function DocStatus({ label, doc }: { label: string; doc: { document_name: string; version: string } | null }) {
  const { t } = useTranslation();

  return (
    <div className="flex items-center gap-2">
      <span
        className={cn(
          "flex h-4 w-4 shrink-0 items-center justify-center rounded-sm text-[10px] font-semibold",
          doc ? "bg-brass text-white" : "bg-white/10 text-paper/40",
        )}
      >
        {label}
      </span>
      <span className={cn("truncate", doc ? "text-paper/80" : "text-paper/30")}>
        {doc ? `${doc.document_name} · ${doc.version}` : t("ledger.notLoaded")}
      </span>
    </div>
  );
}
