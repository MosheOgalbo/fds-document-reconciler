import { NavLink } from "react-router-dom";
import { FileStack, MessagesSquare, GitCompareArrows, ListOrdered } from "lucide-react";
import { useDocuments } from "@/lib/documentsContext";
import { cn } from "@/lib/utils";

const navItems = [
  { to: "/", label: "Documents", icon: FileStack, end: true },
  { to: "/compare", label: "Compare", icon: GitCompareArrows },
  { to: "/chat", label: "Ask", icon: MessagesSquare },
  { to: "/summary", label: "Executive Summary", icon: ListOrdered },
];

export function Sidebar() {
  const { docA, docB } = useDocuments();

  return (
    <aside className="flex h-screen w-64 shrink-0 flex-col bg-ink text-paper">
      <div className="px-5 py-6">
        <div className="font-display text-xl font-semibold tracking-tight">Reconcile</div>
        <div className="mt-1 text-xs text-paper/50">FDS Document Reconciliation</div>
      </div>

      <nav className="flex flex-col gap-0.5 px-3">
        {navItems.map(({ to, label, icon: Icon, end }) => (
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
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="mt-auto px-5 py-5">
        <div className="text-[11px] font-medium uppercase tracking-wider text-paper/40">Ledger</div>
        <div className="mt-2 space-y-1.5 font-mono text-xs">
          <DocStatus label="A" doc={docA} />
          <DocStatus label="B" doc={docB} />
        </div>
      </div>
    </aside>
  );
}

function DocStatus({ label, doc }: { label: string; doc: { document_name: string; version: string } | null }) {
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
        {doc ? `${doc.document_name} · ${doc.version}` : "not loaded"}
      </span>
    </div>
  );
}
