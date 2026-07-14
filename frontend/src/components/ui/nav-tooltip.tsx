import * as React from "react";
import { cn } from "@/lib/utils";

/**
 * Hover/focus tooltip for icon-only nav items. Uses logical positioning for RTL.
 */
export function NavTooltip({
  label,
  children,
  className,
}: {
  label: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("group/navtip relative flex", className)}>
      {children}
      <span
        role="tooltip"
        className={cn(
          "pointer-events-none absolute top-1/2 z-50 -translate-y-1/2 whitespace-nowrap rounded-md bg-ink px-2.5 py-1.5 text-xs font-medium text-paper shadow-card",
          "start-full ms-2 opacity-0 transition-opacity duration-150",
          "group-hover/navtip:opacity-100 group-focus-within/navtip:opacity-100",
          "max-md:hidden",
        )}
      >
        {label}
      </span>
    </div>
  );
}
