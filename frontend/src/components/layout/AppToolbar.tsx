import { LanguageSwitcher } from "@/components/layout/LanguageSwitcher";

export function AppToolbar() {
  return (
    <header className="sticky top-0 z-10 flex h-12 shrink-0 items-center border-b border-rule bg-paper-raised/95 px-5 backdrop-blur-sm">
      <LanguageSwitcher />
    </header>
  );
}
