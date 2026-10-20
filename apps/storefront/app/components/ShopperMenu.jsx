// The storefront's own account entry. It lives in the shared header's `actions`
// slot so it renders on every storefront page, and reads the shopper token in the
// browser rather than in the server render - the header is shared with hosts that
// have no shopper accounts at all.

import { useEffect, useRef, useState } from "react";
import { fetchShopperMe, logoutShopper } from "../lib/api";

const TOKEN_KEY = "chmaba.shopper_token";
const CHANGED_EVENT = "chmaba:shopper-changed";

export { TOKEN_KEY, CHANGED_EVENT };

function UserIcon({ className = "h-4 w-4" }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      <circle cx="12" cy="8" r="4" />
      <path d="M4.5 21a7.5 7.5 0 0 1 15 0" />
    </svg>
  );
}

function ChevronIcon({ className = "h-3.5 w-3.5" }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      <path d="m6 9 6 6 6-6" />
    </svg>
  );
}

export default function ShopperMenu() {
  const [shopper, setShopper] = useState(null);
  const [ready, setReady] = useState(false);
  const [open, setOpen] = useState(false);
  const boxRef = useRef(null);

  useEffect(() => {
    let active = true;
    const sync = async () => {
      const token = window.localStorage.getItem(TOKEN_KEY);
      if (!token) {
        if (active) { setShopper(null); setReady(true); }
        return;
      }
      try {
        const me = await fetchShopperMe(token);
        if (active) setShopper(me || null);
      } catch {
        // An expired or revoked token should not make every page load retry it.
        window.localStorage.removeItem(TOKEN_KEY);
        if (active) setShopper(null);
      } finally {
        if (active) setReady(true);
      }
    };
    sync();
    window.addEventListener(CHANGED_EVENT, sync);
    window.addEventListener("storage", sync);
    return () => {
      active = false;
      window.removeEventListener(CHANGED_EVENT, sync);
      window.removeEventListener("storage", sync);
    };
  }, []);

  useEffect(() => {
    if (!open) return undefined;
    const dismiss = (event) => { if (!boxRef.current?.contains(event.target)) setOpen(false); };
    const escape = (event) => { if (event.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", dismiss);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("mousedown", dismiss);
      document.removeEventListener("keydown", escape);
    };
  }, [open]);

  const signOut = async () => {
    const token = window.localStorage.getItem(TOKEN_KEY);
    window.localStorage.removeItem(TOKEN_KEY);
    setShopper(null);
    setOpen(false);
    window.dispatchEvent(new Event(CHANGED_EVENT));
    if (token) logoutShopper(token).catch(() => {});
  };

  // Avoid a layout jump between the server render and the first client read.
  if (!ready) return <span aria-hidden="true" className="h-9 w-9" />;

  if (!shopper) {
    return (
      <a
        href="/account?mode=signin"
        aria-label="Sign in"
        className="inline-flex h-9 items-center gap-1.5 rounded-lg px-2 text-xs font-bold text-ink-soft transition hover:bg-surface-sunken"
      >
        <UserIcon />
        <span className="hidden sm:inline">Sign in</span>
      </a>
    );
  }

  const name = (shopper.full_name || "").trim();
  const label = name || shopper.email || shopper.phone || "Your account";
  const initial = label.slice(0, 1).toUpperCase();

  return (
    <div ref={boxRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={`Account menu for ${label}`}
        className="flex h-9 max-w-full items-center gap-2 rounded-lg px-2 text-xs font-bold text-ink-soft transition hover:bg-surface-sunken"
        title={label}
      >
        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-brand text-[11px] font-extrabold text-white">
          {initial}
        </span>
        <span className="hidden max-w-[260px] truncate sm:inline">{label}</span>
        <ChevronIcon className={`hidden h-3.5 w-3.5 shrink-0 text-muted transition-transform duration-150 sm:block ${open ? "rotate-180" : ""}`} />
      </button>

      {open ? (
        <div role="menu" className="absolute right-0 z-50 mt-2 w-60 overflow-hidden rounded-xl border border-line bg-surface shadow-[0_16px_40px_rgba(28,31,42,.18)]">
          <div className="border-b border-line px-3 py-2.5">
            <p className="truncate text-sm font-extrabold text-ink">{name || "Your account"}</p>
            <p className="truncate text-[11px] text-muted">{shopper.email || shopper.phone || "Signed in"}</p>
          </div>
          <a href="/account" role="menuitem" className="block px-3 py-2 text-xs font-semibold text-ink-soft transition hover:bg-surface-sunken">
            Your orders
          </a>
          <a href="/account?tab=messages" role="menuitem" className="block px-3 py-2 text-xs font-semibold text-ink-soft transition hover:bg-surface-sunken">
            Messages
          </a>
          <a href="/account?tab=profile" role="menuitem" className="block px-3 py-2 text-xs font-semibold text-ink-soft transition hover:bg-surface-sunken">
            Profile
          </a>
          <button
            type="button"
            role="menuitem"
            onClick={signOut}
            className="block w-full border-t border-line px-3 py-2 text-left text-xs font-semibold text-danger transition hover:bg-surface-sunken"
          >
            Sign out
          </button>
        </div>
      ) : null}
    </div>
  );
}
