import { currentThemeFromDocument, nextTheme, writeStoredTheme } from "../lib/theme";

// Both icons are always rendered and CSS picks between them from the `dark` class on
// <html>. That way the server and the client produce identical markup - so there is no
// hydration mismatch, and no flash, when a shopper has already chosen dark.
//
// Drawn inline rather than pulled from an icon package: the storefront does not depend on
// one, and the rest of the shared chrome is dependency-free for the same reason.

export function ThemeToggle() {
  const toggle = () => {
    const next = nextTheme(currentThemeFromDocument());
    writeStoredTheme(next, () => window.localStorage);
    document.documentElement.classList.toggle("dark", next === "dark");
  };
  return (
    <button
      type="button"
      aria-label="Toggle dark mode"
      title="Switch between light and dark"
      onClick={toggle}
      className="relative flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-[#70717a] transition hover:bg-[#f0f0f5] hover:text-[#272831] dark:text-[#9a9aa4] dark:hover:bg-[#2a2b32] dark:hover:text-[#e4e4e8]"
    >
      <svg viewBox="0 0 24 24" aria-hidden="true" className="h-[17px] w-[17px] dark:hidden" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z" />
      </svg>
      <svg viewBox="0 0 24 24" aria-hidden="true" className="hidden h-[17px] w-[17px] dark:block" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="4" />
        <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
      </svg>
    </button>
  );
}
