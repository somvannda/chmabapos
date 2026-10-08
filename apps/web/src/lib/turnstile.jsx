import { useEffect, useRef } from "react";

// Cloudflare Turnstile site key, injected at build time. When it is empty the
// widget is not rendered and the API skips Turnstile enforcement, so local
// development and deployments without keys keep working.
export const TURNSTILE_SITE_KEY = (import.meta.env.VITE_TURNSTILE_SITE_KEY || "").trim();

const SCRIPT_SRC = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
let scriptPromise = null;

function loadScript() {
  if (typeof window === "undefined") return Promise.reject(new Error("Turnstile needs a browser"));
  if (window.turnstile) return Promise.resolve(window.turnstile);
  if (scriptPromise) return scriptPromise;
  scriptPromise = new Promise((resolve, reject) => {
    const existing = document.querySelector(`script[src="${SCRIPT_SRC}"]`);
    if (existing) {
      existing.addEventListener("load", () => resolve(window.turnstile));
      existing.addEventListener("error", () => reject(new Error("Turnstile failed to load")));
      return;
    }
    const script = document.createElement("script");
    script.src = SCRIPT_SRC;
    script.async = true;
    script.defer = true;
    script.onload = () => resolve(window.turnstile);
    script.onerror = () => reject(new Error("Turnstile failed to load"));
    document.head.appendChild(script);
  });
  return scriptPromise;
}

/**
 * An invisible Turnstile widget. Renders nothing when no site key is set.
 *
 * ``onToken`` receives the widget token (empty string once it expires or errors).
 * ``resetSignal`` re-runs the challenge; pass the current form error so a failed
 * submit gets a fresh token without a full page reload.
 */
export function TurnstileWidget({ onToken, resetSignal = "" }) {
  const containerRef = useRef(null);
  const widgetIdRef = useRef(null);

  useEffect(() => {
    if (!TURNSTILE_SITE_KEY) return undefined;
    let cancelled = false;
    loadScript()
      .then((turnstile) => {
        if (cancelled || !turnstile || !containerRef.current) return;
        widgetIdRef.current = turnstile.render(containerRef.current, {
          sitekey: TURNSTILE_SITE_KEY,
          size: "invisible",
          callback: (token) => onToken && onToken(token),
          "expired-callback": () => onToken && onToken(""),
          "error-callback": () => onToken && onToken(""),
        });
      })
      .catch(() => onToken && onToken(""));
    return () => {
      cancelled = true;
      const turnstile = typeof window !== "undefined" ? window.turnstile : null;
      if (turnstile && widgetIdRef.current != null) {
        try {
          turnstile.remove(widgetIdRef.current);
        } catch {
          // The widget is already gone; nothing to clean up.
        }
      }
      widgetIdRef.current = null;
    };
  }, [onToken]);

  useEffect(() => {
    const turnstile = typeof window !== "undefined" ? window.turnstile : null;
    if (turnstile && widgetIdRef.current != null) {
      try {
        turnstile.reset(widgetIdRef.current);
        onToken && onToken("");
      } catch {
        // Reset is best-effort; the next render will try again.
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resetSignal]);

  if (!TURNSTILE_SITE_KEY) return null;
  return <div ref={containerRef} />;
}
