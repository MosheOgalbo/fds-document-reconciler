import { useLocation } from "react-router-dom";
import { Outlet } from "react-router-dom";
import { Sidebar } from "@/components/layout/Sidebar";
import { MobileNav } from "@/components/layout/MobileNav";
import { AppToolbar } from "@/components/layout/AppToolbar";
import { ConfigurationBanner } from "@/components/layout/ConfigurationBanner";
import { cn } from "@/lib/utils";

export function AppShell() {
  const location = useLocation();
  const isFreeChat = location.pathname === "/free-chat";

  return (
    <div className="flex min-h-screen items-stretch">
      <Sidebar />
      <main className="flex min-h-screen min-w-0 flex-1 flex-col pb-[calc(3.25rem+env(safe-area-inset-bottom))] md:pb-0">
        <AppToolbar />
        <ConfigurationBanner />
        <div
          className={cn(
            "mx-auto flex w-full flex-1 flex-col",
            isFreeChat ? "max-w-4xl px-4 py-4 sm:px-5 sm:py-5" : "max-w-5xl px-4 py-6 sm:px-6 sm:py-8 md:px-8 md:py-10",
          )}
        >
          <Outlet />
        </div>
      </main>
      <MobileNav />
    </div>
  );
}
