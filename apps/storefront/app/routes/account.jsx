import { useEffect, useState } from "react";
import { Link } from "react-router";

import { fetchMyOrders, fetchShopperMe, requestShopperCode, verifyShopperCode } from "../lib/api";

const TOKEN_KEY = "chmaba.shopper_token";

export function meta() {
  // One person's orders: useful to them, not content to index.
  return [{ title: "Your orders" }, { name: "robots", content: "noindex" }];
}

// The storefront is server-rendered, so this page cannot read localStorage while
// rendering - that would produce markup the client immediately disagrees with. It
// therefore starts as the signed-out form and upgrades itself once mounted, which
// is the only way to be both SSR-correct and signed-in when a token exists.
export default function Account() {
  const [checking, setChecking] = useState(true);
  const [shopper, setShopper] = useState(null);
  const [orders, setOrders] = useState([]);
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [stage, setStage] = useState("email");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const token = window.localStorage.getItem(TOKEN_KEY);
        if (token) {
          const [me, history] = await Promise.all([fetchShopperMe(token), fetchMyOrders(token)]);
          if (active) {
            setShopper(me);
            setOrders(Array.isArray(history) ? history : []);
          }
        }
      } catch {
        // A revoked or expired token just means signed out. That is not an error
        // worth showing someone.
        window.localStorage.removeItem(TOKEN_KEY);
      } finally {
        if (active) setChecking(false);
      }
    })();
    return () => { active = false; };
  }, []);

  const sendCode = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await requestShopperCode(email.trim());
      setStage("code");
    } catch (requestError) {
      setError(requestError instanceof Response ? await requestError.text() : "Could not send the code");
    } finally {
      setBusy(false);
    }
  };

  const verify = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await verifyShopperCode(email.trim(), code.trim());
      window.localStorage.setItem(TOKEN_KEY, result.access_token);
      setShopper(result.shopper);
      const history = await fetchMyOrders(result.access_token);
      setOrders(Array.isArray(history) ? history : []);
      setCode("");
      setStage("email");
    } catch (requestError) {
      // The API returns one message for every failure, so there is nothing more
      // specific to say - and saying more would help someone guess codes.
      setError(
        requestError instanceof Response && requestError.status === 400
          ? "That code is not valid."
          : "Could not sign in. Please try again."
      );
    } finally {
      setBusy(false);
    }
  };

  const signOut = () => {
    window.localStorage.removeItem(TOKEN_KEY);
    setShopper(null);
    setOrders([]);
  };

  if (checking) {
    return <main className="mx-auto max-w-[560px] px-5 py-20 text-center text-sm text-muted">Loading…</main>;
  }

  if (shopper) {
    return (
      <div className="min-h-screen bg-page px-5 py-10">
        <main className="mx-auto max-w-[640px]">
          <h1 className="text-xl font-extrabold tracking-[-.03em] text-ink">Your orders</h1>
          <p className="mt-1 text-xs text-muted">{shopper.email || "Signed in with Telegram"}</p>

          {orders.length === 0 ? (
            <p className="mt-8 rounded-2xl border border-line bg-surface p-8 text-center text-sm text-muted">
              No orders yet. Orders you place while signed in appear here.
            </p>
          ) : (
            <ul className="mt-6 space-y-2">
              {orders.map((order) => (
                <li key={order.public_token || `${order.created_at}-${order.label}`} className="rounded-xl border border-line bg-surface p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-bold text-ink-soft">{order.store_name}</p>
                      <p className="mt-0.5 text-[11px] text-muted">
                        {order.label || "Order"} · {new Date(order.created_at).toLocaleDateString()}
                      </p>
                    </div>
                    <span className="shrink-0 text-sm font-extrabold text-ink">{order.subtotal}</span>
                  </div>
                  <div className="mt-2 flex items-center gap-3">
                    <span className="rounded-lg bg-surface-sunken px-2 py-1 text-[10px] font-bold text-ink-soft">
                      {order.status}
                    </span>
                    {order.public_token ? (
                      <Link to={`/order/${order.public_token}`} className="text-[11px] font-semibold text-brand">
                        Track this order
                      </Link>
                    ) : null}
                  </div>
                </li>
              ))}
            </ul>
          )}

          <button type="button" onClick={signOut} className="mt-6 rounded-xl border border-line px-4 py-2 text-xs font-bold text-ink-soft">
            Sign out
          </button>
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-page px-5 py-12">
      <main className="mx-auto max-w-[420px]">
        <h1 className="text-xl font-extrabold tracking-[-.03em] text-ink">Your orders</h1>
        <p className="mt-1 text-sm text-muted">
          Sign in with your email and we will send you a six-digit code. No password to remember.
        </p>

        <form onSubmit={stage === "email" ? sendCode : verify} className="mt-6 space-y-3">
          <input
            type="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="you@example.com"
            disabled={stage === "code"}
            className="h-11 w-full rounded-xl border border-line bg-surface px-3.5 text-sm text-ink outline-none focus:border-brand disabled:opacity-60"
          />
          {stage === "code" ? (
            <input
              inputMode="numeric"
              autoComplete="one-time-code"
              required
              value={code}
              onChange={(event) => setCode(event.target.value)}
              placeholder="6-digit code"
              className="h-11 w-full rounded-xl border border-line bg-surface px-3.5 text-sm tracking-[.3em] text-ink outline-none focus:border-brand"
            />
          ) : null}
          {error ? <p className="text-xs font-semibold text-danger">{error}</p> : null}
          <button
            type="submit"
            disabled={busy}
            className="w-full rounded-xl bg-brand px-4 py-2.5 text-sm font-bold text-white disabled:opacity-60"
          >
            {busy ? "Working…" : stage === "email" ? "Send me a code" : "Sign in"}
          </button>
        </form>

        {stage === "code" ? (
          <button type="button" onClick={() => setStage("email")} className="mt-3 text-xs font-semibold text-brand">
            Use a different email
          </button>
        ) : null}

        <p className="mt-8 text-center text-[10px] text-muted">Powered by Chmaba</p>
      </main>
    </div>
  );
}
