import { FileStack, MessagesSquare, GitCompareArrows, ListOrdered, Sparkles } from "lucide-react";

export const navItems = [
  { to: "/", key: "nav.documents", icon: FileStack, end: true as const },
  { to: "/free-chat", key: "nav.freeChat", icon: Sparkles, end: false as const },
  { to: "/compare", key: "nav.compare", icon: GitCompareArrows, end: false as const },
  { to: "/chat", key: "nav.ask", icon: MessagesSquare, end: false as const },
  { to: "/summary", key: "nav.executiveSummary", icon: ListOrdered, end: false as const },
] as const;
