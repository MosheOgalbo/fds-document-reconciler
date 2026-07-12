import { useLocation } from "react-router-dom";
import { Outlet } from "react-router-dom";
import { Sidebar } from "@/components/layout/Sidebar";
import { ConfigurationBanner } from "@/components/layout/ConfigurationBanner";

import { cn } from "@/lib/utils";

export function AppShell() {
  const location = useLocation();
  const isFreeChat = location.pathname === "/free-chat";

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex min-h-screen flex-1 flex-col overflow-hidden">
        <ConfigurationBanner />
        <div
          className={cn(
            "mx-auto flex w-full flex-1 flex-col",
            isFreeChat ? "max-w-4xl px-5 py-5" : "max-w-5xl overflow-y-auto px-8 py-10",
          )}
        >
          <Outlet />
        </div>
      </main>
    </div>
  );
}
