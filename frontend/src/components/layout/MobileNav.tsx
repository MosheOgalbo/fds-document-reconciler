import { NavLink } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { navItems } from "@/components/layout/nav-items";
import { cn } from "@/lib/utils";

/** Bottom icon bar — mobile only. Labels exposed via aria-label for accessibility. */
export function MobileNav() {
  const { t } = useTranslation();

  return (
    <nav
      className="fixed inset-x-0 bottom-0 z-20 border-t border-rule bg-paper-raised/95 backdrop-blur-sm md:hidden"
      aria-label={t("nav.mainNavigation")}
    >
      <div className="mx-auto flex max-w-lg items-stretch justify-around px-1 pb-[env(safe-area-inset-bottom)]">
        {navItems.map(({ to, key, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            aria-label={t(key)}
            title={t(key)}
            className={({ isActive }) =>
              cn(
                "flex min-h-[3.25rem] min-w-0 flex-1 flex-col items-center justify-center gap-0.5 px-1 py-2 transition-colors",
                isActive ? "text-brass" : "text-ink-faint hover:text-ink-soft",
              )
            }
          >
            {({ isActive }) => (
              <>
                <Icon size={20} strokeWidth={isActive ? 2.25 : 2} aria-hidden />
                <span className="sr-only">{t(key)}</span>
              </>
            )}
          </NavLink>
        ))}
      </div>
    </nav>
  );
}
