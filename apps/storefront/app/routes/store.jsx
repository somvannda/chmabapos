import { useEffect, useMemo, useState } from "react";
import { Link, isRouteErrorResponse, useLoaderData, useParams, useRouteError } from "react-router";

import { QRCodeSVG } from "qrcode.react";

import { fetchOrderPayment, fetchStore, formatMoney, submitStoreOrder } from "../lib/api";
import { cartKey } from "../lib/cart";
import { useCart } from "../lib/useCart";
import { MailIcon, PhoneIcon, PinIcon, SocialIcon } from "../components/Icons";
import StoreChat from "../components/StoreChat";
import { socialHref } from "../lib/social";

const SCHEMA_DAYS = { mon: "Monday", tue: "Tuesday", wed: "Wednesday", thu: "Thursday", fri: "Friday", sat: "Saturday", sun: "Sunday" };
const SOCIAL_LABELS = { facebook: "Facebook", instagram: "Instagram", telegram: "Telegram", tiktok: "TikTok" };
const POLICY_LABELS = { returns: "Returns", delivery: "Delivery", privacy: "Privacy" };

export async function loader({ params }) {
  const store = await fetchStore(params.companySlug, params.storeSlug);
  if (!store) throw new Response("Store not found", { status: 404 });
  return { store };
}

export function meta({ data, params, error, matches }) {
  if (!data || error) {
    return [{ title: "Store unavailable" }, { name: "robots", content: "noindex" }];
  }
  const name = data.store.store_name;
  const brand = data.store.storefront || {};
  // Absolute URLs are not cosmetic here. The canonical link, og:url and og:image
  // are read by crawlers and by unfurlers on Facebook and Telegram, and **all of
  // them ignore a relative value** - so a relative image silently produces a bare
  // preview card on the exact channel these links spread through. The origin comes
  // from the root loader, so it is right in every environment without a second
  // configured host to keep in step.
  const origin = matches?.find((match) => match?.id === "root")?.data?.origin || "";
  const absolute = (value) => {
    if (!value) return "";
    if (/^https?:\/\//i.test(value)) return value;
    // A merchant who picked from the media library has a relative path.
    return origin ? `${origin}${value.startsWith("/") ? "" : "/"}${value}` : value;
  };
  const canonical = absolute(`/${params.companySlug}/${params.storeSlug}`);
  const image = absolute(brand.cover || brand.logo);
  const currency = data.store.currency_code || "USD";
  // Structured data, so the store can surface as a business with hours and a menu
  // rather than an anonymous link. Only what the page already shows is included.
  const openingHours = (brand.hours || [])
    .filter((entry) => !entry.closed)
    .map((entry) => ({
      "@type": "OpeningHoursSpecification",
      dayOfWeek: `https://schema.org/${SCHEMA_DAYS[entry.day] || entry.day}`,
      opens: entry.open,
      closes: entry.close,
    }));
  const menu = (data.store.items || []).slice(0, 100).map((item) => ({
    "@type": "Product",
    name: item.variantName ? `${item.name} — ${item.variantName}` : item.name,
    ...(item.image ? { image: item.image } : {}),
    offers: {
      "@type": "Offer",
      price: Number(item.price),
      priceCurrency: currency,
      availability: item.available ? "https://schema.org/InStock" : "https://schema.org/OutOfStock",
    },
  }));
  const structuredData = {
    "@context": "https://schema.org",
    "@type": "LocalBusiness",
    name,
    url: canonical,
    ...(brand.tagline ? { description: brand.tagline } : {}),
    ...(brand.logo ? { image: brand.logo } : {}),
    ...(data.store.address ? { address: { "@type": "PostalAddress", streetAddress: data.store.address } } : {}),
    ...(openingHours.length ? { openingHoursSpecification: openingHours } : {}),
    ...(menu.length ? { hasOfferCatalog: { "@type": "OfferCatalog", name: "Menu", itemListElement: menu } } : {}),
  };
  return [
    { title: name },
    { name: "description", content: brand.tagline || `Browse ${name} and order on Chmaba.` },
    { tagName: "link", rel: "canonical", href: canonical },
    { property: "og:title", content: name },
    { property: "og:description", content: brand.tagline || `Browse ${name} on Chmaba.` },
    { property: "og:type", content: "website" },
    { property: "og:url", content: canonical },
    ...(image ? [{ property: "og:image", content: image }] : []),
    // Rendered on the server, so a crawler sees it without running JavaScript.
    { "script:ld+json": structuredData },
  ];
}

export function ErrorBoundary() {
  const error = useRouteError();
  const notFound = isRouteErrorResponse(error) && error.status === 404;
  return (
    <main className="mx-auto flex min-h-screen max-w-[560px] flex-col items-center justify-center px-6 text-center">
      <h1 className="text-xl font-extrabold tracking-[-.03em] text-ink">
        {notFound ? "This store page is not available" : "Something went wrong"}
      </h1>
      <p className="mt-2 text-sm text-muted">
        {notFound ? "The link may be mistyped, or the store has not published its page yet." : "Please try again."}
      </p>
    </main>
  );
}

function OpenState({ isOpen }) {
  if (isOpen === null || isOpen === undefined) return null;
  return (
    <span
      className={
        isOpen
          ? "inline-flex items-center gap-1.5 rounded-full bg-success-soft px-2.5 py-1 text-[11px] font-bold text-success"
          : "inline-flex items-center gap-1.5 rounded-full bg-surface-sunken px-2.5 py-1 text-[11px] font-bold text-muted"
      }
    >
      <span className={isOpen ? "h-1.5 w-1.5 rounded-full bg-success" : "h-1.5 w-1.5 rounded-full bg-muted"} />
      {isOpen ? "Open now" : "Closed"}
    </span>
  );
}

// A product with sizes/options is ordered one variant at a time, so each variant
// becomes its own orderable entry and the cart is keyed by that line.
function orderableEntries(store) {
  const rows = [];
  for (const item of store.items || []) {
    const variants = Array.isArray(item.variants) ? item.variants : [];
    if (variants.length) {
      for (const variant of variants) {
        rows.push({
          key: `${item.id}:${variant.id}`,
          productId: item.id,
          variantId: variant.id,
          name: item.name,
          variantName: variant.name,
          description: item.description,
          image: item.image,
          price: Number(variant.price),
          available: variant.available,
          category: item.category,
        });
      }
    } else {
      rows.push({
        key: item.id,
        productId: item.id,
        variantId: null,
        name: item.name,
        variantName: null,
        description: item.description,
        image: item.image,
        price: Number(item.price),
        available: item.available,
        category: item.category,
      });
    }
  }
  return rows;
}

// The merchant's own store page: branded, server-rendered, and orderable.
//
// The accent is applied by setting two design-token custom properties, which is
// the entire theming step. Prices shown here are display only — the API reprices
// every line from the catalogue when the order is submitted.
export default function Store() {
  const { store } = useLoaderData();
  const brand = store.storefront || {};
  const currency = store.currency_code || "USD";
  const socials = brand.socials || {};
  const policies = brand.policies || {};
  const acceptOrders = brand.accept_orders !== false;

  const entries = useMemo(() => orderableEntries(store), [store]);
  const byKey = useMemo(() => Object.fromEntries(entries.map((entry) => [entry.key, entry])), [entries]);

  // The cart lives in session storage rather than here, so opening a product and coming
  // back does not empty it - and so the product page can add to the same one.
  const { companySlug, storeSlug } = useParams();
  const { cart, setQuantity, clear } = useCart(cartKey(companySlug, storeSlug));
  // The page is server-rendered, so these controls exist and look ready before React is
  // listening. Until it is, they are disabled: otherwise a press in that window does
  // nothing at all, with no feedback, which is worse than being briefly unavailable.
  const [ready, setReady] = useState(false);
  useEffect(() => setReady(true), []);
  const [cartOpen, setCartOpen] = useState(false);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [confirmed, setConfirmed] = useState(null);
  // True once the poll sees the payment settle, so the QR can be replaced in place
  // rather than the shopper having to reload to find out whether it worked.
  const [paymentSettled, setPaymentSettled] = useState(false);
  // True once the poll reports the order was closed for non-payment, so the page can say so
  // instead of leaving a shopper scanning a code for an order that no longer exists.
  const [paymentClosed, setPaymentClosed] = useState(false);
  // When the store will close the order, and how long that leaves. The deadline comes from the
  // server, so the countdown cannot drift from the one the job enforces.
  const [expiresAt, setExpiresAt] = useState(null);
  const [minutesLeft, setMinutesLeft] = useState(null);
  // The code the provider issued, taken from the first poll. The submit response does not
  // carry it, and a payment screen without a code to scan is not much of a payment screen.
  const [qrString, setQrString] = useState(null);
  // Development-only: what the payment poll is receiving, and for which order. Rendered on
  // the page so the browser can be asked rather than reasoned about - it settled three wrong
  // theories in one run. Kept behind import.meta.env.DEV so it never reaches a shopper.
  const [pollDebug, setPollDebug] = useState("not polling yet");
  useEffect(() => {
    // Only worth polling while a payment is genuinely outstanding.
    if (!confirmed || confirmed.payment_status !== "pending" || !confirmed.public_token) return undefined;
    let cancelled = false;
    const check = async () => {
      try {
        // The order's token, not the ticket's id: the sale is what the shopper is asking about.
        const state = await fetchOrderPayment(confirmed.public_token);
        if (cancelled) return;
        if (import.meta.env.DEV) {
          setPollDebug(`polled order=${String(confirmed.public_token).slice(0, 8)} -> paid=${state ? state.paid : "null"} status=${state ? state.payment_status : "-"}`);
        }
        if (!state) return;
        // The submit response carries no code, so the first poll supplies it.
        if (state.qr_string) setQrString(state.qr_string);
        // A closed or failed payment is terminal. Say so, rather than inviting a scan for an
        // order the store has already released.
        if (!state.paid && (state.payment_status === "expired" || state.payment_status === "failed")) {
          setPaymentClosed(true);
        }
        if (state.expires_at) setExpiresAt(state.expires_at);
        if (state.paid) setPaymentSettled(true);
      } catch (error) {
        // A failed poll just means "not yet" to a shopper. In development it must not be
        // invisible: a poll that never succeeds looks exactly like a payment that never
        // arrives, and this one swallowed its error for three test runs.
        if (import.meta.env.DEV) {
          setPollDebug(`poll failed: ${error && error.message ? error.message : String(error)}`);
        }
      }
    };
    const timer = window.setInterval(check, 3000);
    check();
    return () => { cancelled = true; window.clearInterval(timer); };
  }, [confirmed]);

  // Re-evaluated on a timer rather than every second: a shopper needs to know whether they
  // have minutes left, not to watch a clock tick.
  useEffect(() => {
    if (!expiresAt) return undefined;
    const tick = () => {
      const remaining = new Date(expiresAt).getTime() - Date.now();
      setMinutesLeft(remaining <= 0 ? 0 : Math.ceil(remaining / 60000));
    };
    tick();
    const timer = window.setInterval(tick, 30000);
    return () => window.clearInterval(timer);
  }, [expiresAt]);

  // What to say about the deadline. Before the first poll answers, the store's own window is
  // the best statement available; after it, the server's deadline is authoritative - so the
  // page cannot count down to a moment the job does not keep.
  const deadlineNotice = () => {
    if (expiresAt) {
      if (minutesLeft === null) return " Pay soon, or the order is closed and the items released.";
      if (minutesLeft > 0) return ` About ${minutesLeft} minute${minutesLeft === 1 ? "" : "s"} left to pay, or the order is closed and the items released.`;
      return " Time is up - the order is being closed and the items released.";
    }
    if (store.unpaid_order_expiry_minutes > 0) return ` Pay within ${store.unpaid_order_expiry_minutes} minutes, or the order is closed and the items released.`;
    return "";
  };

  const groups = new Map();
  for (const entry of entries) {
    const key = entry.category || "Menu";
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(entry);
  }

  const lines = Object.entries(cart).filter(([, quantity]) => quantity > 0);
  const count = lines.reduce((sum, [, quantity]) => sum + quantity, 0);
  const total = lines.reduce((sum, [key, quantity]) => sum + (byKey[key]?.price || 0) * quantity, 0);
  // The confirmation reads the order the API returned rather than the cart. Accepting an
  // order clears the cart, and the API's figures are the ones it actually charged: they
  // include the store's service tax, which a total summed in the browser silently omitted.
  //
  // The held order carries no image, so the menu already loaded for this page supplies it.
  const imageForItem = (item) => {
    const product = (store.items || []).find((row) => String(row.id) === String(item.product_id));
    return product?.image || null;
  };

  const submit = async () => {
    if (!lines.length) return;
    setBusy(true);
    setError("");
    try {
      const order = await submitStoreOrder(store.company_slug, store.store_slug, {
        items: lines.map(([key, quantity]) => ({
          product_id: byKey[key].productId,
          variant_id: byKey[key].variantId,
          quantity,
        })),
        customer_name: name.trim() || null,
        customer_email: email.trim() || null,
        customer_note: note.trim() || null,
      });
      clear();
      setNote("");
      setCartOpen(false);
      setConfirmed(order);
    } catch (requestError) {
      // A Response carries the API's own message, which is what the shopper needs
      // to see ("Insufficient stock for ...") rather than a generic failure.
      setError(requestError instanceof Response ? await requestError.text() : requestError.message || "Could not place the order");
    } finally {
      setBusy(false);
    }
  };

  const theme = store.accent_brand
    ? { "--color-brand": store.accent_brand, ...(store.accent_soft ? { "--color-brand-soft": store.accent_soft } : {}) }
    : undefined;

  // Money is still owed, so the order is taken but not placed. The screen must not
  // congratulate anybody, or name a total it has not been paid, until that clears.
  const awaitingPayment = Boolean(confirmed && confirmed.payment_status === "pending");

  if (confirmed) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-page px-5" style={theme}>
        <div className="w-full max-w-[460px] rounded-2xl border border-line bg-surface p-8 text-center">
          <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-soft text-xl font-black text-brand">
            ✓
          </span>
          <h1 className="mt-4 text-xl font-extrabold tracking-[-.03em] text-ink">
            {awaitingPayment && !paymentSettled ? "Pay to place your order" : "Order placed"}
          </h1>
          <p className="mt-2 text-sm text-ink-soft">
            {store.store_name}{awaitingPayment && !paymentSettled ? " will have your order as soon as you pay" : " has your order"}{confirmed.label ? ` · ${confirmed.label}` : ""}.
          </p>
          {awaitingPayment ? (
            <div className="mt-5 space-y-4 text-left">
              {/* What the money is for, and how much. A payment screen that will not say
                  what it is charging for is asking for trust it has not earned. */}
              <div className="rounded-2xl border border-line bg-surface p-4">
                <p className="text-[10px] font-bold uppercase tracking-wide text-muted">Your order</p>
                <ul className="mt-3 space-y-3">
                  {(confirmed.items || []).map((item) => {
                    const image = imageForItem(item);
                    return (
                      <li key={item.line_key} className="flex items-center gap-3">
                        {image ? (
                          <img src={image} alt="" className="h-12 w-12 shrink-0 rounded-lg bg-surface-sunken object-cover" loading="lazy" />
                        ) : (
                          <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg bg-surface-sunken text-xs font-black text-muted">
                            {(item.product_name || "?").slice(0, 1).toUpperCase()}
                          </span>
                        )}
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-xs font-bold text-ink-soft">
                            {item.product_name}
                            {item.variant_name ? ` · ${item.variant_name}` : ""}
                          </span>
                          <span className="mt-0.5 block text-[11px] text-muted">
                            {formatMoney(Number(item.unit_price), currency)} × {item.quantity}
                          </span>
                        </span>
                        <span className="shrink-0 text-xs font-semibold text-ink-soft">
                          {formatMoney(Number(item.line_total), currency)}
                        </span>
                      </li>
                    );
                  })}
                </ul>
                <div className="mt-3 space-y-1 border-t border-line pt-2 text-xs">
                  <div className="flex items-baseline justify-between">
                    <span className="text-muted">Subtotal</span>
                    <span className="font-semibold text-ink-soft">{formatMoney(Number(confirmed.subtotal || 0), currency)}</span>
                  </div>
                  {Number(confirmed.tax || 0) > 0 ? (
                    <div className="flex items-baseline justify-between">
                      <span className="text-muted">Tax</span>
                      <span className="font-semibold text-ink-soft">{formatMoney(Number(confirmed.tax), currency)}</span>
                    </div>
                  ) : null}
                  <div className="flex items-baseline justify-between pt-1">
                    <span className="font-bold text-ink">Total to pay</span>
                    <span className="text-sm font-extrabold text-ink">{formatMoney(Number(confirmed.total || 0), currency)}</span>
                  </div>
                </div>
              </div>

              <div className="rounded-2xl border border-line bg-surface p-4 text-center">
                {paymentSettled ? (
                  <>
                    <p className="text-sm font-bold text-brand">Payment received</p>
                    <p className="mt-1 text-xs text-ink-soft">Your order is placed — {store.store_name} has it.</p>
                  </>
                ) : (
                  <>
                    {!paymentClosed ? (
                      <p className="text-xs font-bold text-ink-soft">Scan to pay {formatMoney(Number(confirmed.total || 0), currency)}</p>
                    ) : null}
                    {!paymentClosed && (qrString || confirmed.payment_qr_string) ? (
                      <div className="mt-3 inline-flex rounded-xl bg-white p-3">
                        <QRCodeSVG value={qrString || confirmed.payment_qr_string} size={188} />
                      </div>
                    ) : null}
                    <p className="mt-3 text-[11px] leading-4 text-muted">
                      {paymentClosed
                        ? "This order was closed because the payment did not arrive. Nothing has been charged, and the items are no longer held for you."
                        : "Your order is placed as soon as the payment arrives. Nothing has been charged yet, and this page updates on its own."}
                      {!paymentClosed ? deadlineNotice() : ""}
                    </p>
                    {import.meta.env.DEV ? (
                      <p className="mt-3 break-all text-[10px] font-bold text-[#c2564b]">
                        dev: {pollDebug} | paying={String(confirmed.payment_checkout_url || "").split("/").pop()}
                      </p>
                    ) : null}
                    {confirmed.payment_checkout_url ? (
                      <a
                        href={confirmed.payment_checkout_url}
                        target="_blank"
                        rel="noreferrer"
                        className="mt-3 inline-block text-[11px] font-semibold text-brand"
                      >
                        Open the payment page instead
                      </a>
                    ) : null}
                  </>
                )}
              </div>
            </div>
          ) : (
            <p className="mt-4 text-xs text-muted">Please pay at the counter when you collect.</p>
          )}
          <button
            type="button"
            onClick={() => { setConfirmed(null); setPaymentSettled(false); setQrString(null); }}
            className="mt-6 block w-full rounded-xl border border-line px-4 py-2.5 text-sm font-bold text-ink-soft"
          >
            Order more
          </button>
          {confirmed.public_token ? (
            <a
              href={`/order/${confirmed.public_token}`}
              className="mt-3 block text-xs font-semibold text-brand"
            >
              Follow this order
            </a>
          ) : null}
        </div>

        {/* Kept on the confirmation screen too: "where is my order?" is the moment
            a shopper most wants to ask something, and the thread is the same one. */}
        <StoreChat companySlug={companySlug} storeSlug={storeSlug} storeName={store.store_name} />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-page pb-36" style={theme}>
      {brand.cover ? (
        // 820x312 is Facebook's cover ratio: a merchant who crops to that shape gets the
        // whole picture instead of a thin slice. Capped in height so it does not become a
        // wall of image on a wide screen; object-cover crops the remainder.
        <div className="aspect-[820/312] max-h-[400px] w-full overflow-hidden bg-surface-sunken">
          <img src={brand.cover} alt="" className="h-full w-full object-cover" />
        </div>
      ) : null}

      <div className="mx-auto max-w-[720px] px-5">
        {/* Identity, address and contacts in one card under the cover: what a shopper
            needs to decide to call or walk in, instead of scattered between the old
            header and a footer. Overlaps the cover when there is one. */}
        {/* Positioned so its own background paints above the cover. An <img> is replaced
            inline content, and inline content paints after the background of a
            non-positioned block - which is why the photograph used to come through the
            top of this card and swallow the logo and store name. */}
        <section className={`relative z-10 rounded-2xl border border-line bg-surface p-4 shadow-[0_12px_36px_rgba(28,31,42,.10)] sm:p-5 ${brand.cover ? "-mt-12" : "mt-5"}`}>
          <div className="flex items-start gap-3">
            {brand.logo ? (
              <img src={brand.logo} alt="" className="h-16 w-16 shrink-0 rounded-2xl border border-line object-cover" />
            ) : (
              <span className="flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl bg-brand-soft text-xl font-black text-brand">
                {(store.store_name || "?").slice(0, 1).toUpperCase()}
              </span>
            )}
            <div className="min-w-0 flex-1">
              <h1 className="truncate text-xl font-extrabold tracking-[-.03em] text-ink">{store.store_name}</h1>
              {brand.tagline ? <p className="mt-0.5 text-xs text-muted">{brand.tagline}</p> : null}
            </div>
            <OpenState isOpen={store.is_open} />
          </div>
          {store.address || store.phone || Object.keys(socials).length ? (
            <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2 border-t border-line pt-3 text-xs text-muted">
              {store.address ? (
                <span className="inline-flex items-center gap-1.5"><PinIcon />{store.address}</span>
              ) : null}
              {store.phone ? (
                <a href={`tel:${store.phone}`} className="inline-flex items-center gap-1.5 font-semibold text-ink-soft transition hover:text-brand"><PhoneIcon />{store.phone}</a>
              ) : null}
              {store.email ? (
                <a href={`mailto:${store.email}`} className="inline-flex items-center gap-1.5 font-semibold text-ink-soft transition hover:text-brand"><MailIcon />{store.email}</a>
              ) : null}
              {Object.entries(socials).map(([key, value]) => {
                const href = socialHref(key, value);
                const label = SOCIAL_LABELS[key] || key;
                // No usable link means no icon: a mark that goes nowhere is worse than
                // nothing, and the old version printed the raw handle at the customer.
                if (!href) return null;
                return (
                  <a
                    key={key}
                    href={href}
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label={label}
                    title={`${label}: ${value}`}
                    className="flex h-8 w-8 items-center justify-center rounded-lg bg-surface-sunken text-ink-soft transition hover:bg-brand hover:text-white"
                  >
                    <SocialIcon network={key} />
                  </a>
                );
              })}
            </div>
          ) : null}
        </section>
      </div>

      {brand.banner ? (
        <p className="mx-auto mt-4 max-w-[720px] rounded-xl bg-brand-soft px-4 py-2.5 text-center text-xs font-bold text-brand">{brand.banner}</p>
      ) : null}

      <main className="mx-auto max-w-[1240px] px-4 sm:px-5">
        {acceptOrders ? null : (
          <p className="mt-5 rounded-xl border border-line bg-surface px-4 py-3 text-xs font-semibold text-ink-soft">
            This store is not accepting orders right now. You can still browse the menu.
          </p>
        )}
        {[...groups.entries()].map(([category, items]) => (
          <section key={category} className="mt-6">
            <h2 className="text-xs font-bold uppercase tracking-wide text-muted">{category}</h2>
            <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
              {items.map((item) => (
                <article key={item.key} className="flex h-full flex-col rounded-2xl border border-line bg-surface p-3 shadow-[0_6px_20px_rgba(28,31,42,.04)]">
                  {/* Picture and name open the product; not the whole card, because the
                      card also holds the add controls - a button inside a link is invalid
                      and behaves unpredictably on touch. The option travels too, so a card
                      naming "Silver" does not land on "Rose gold". */}
                  <Link to={`product/${item.productId}?option=${encodeURIComponent(item.key)}`} className="transition hover:opacity-90">
                    {item.image ? (
                      <img src={item.image} alt="" className="mb-3 aspect-square w-full rounded-xl object-cover" loading="lazy" />
                    ) : (
                      <span className="mb-3 flex aspect-square w-full items-center justify-center rounded-xl bg-surface-sunken text-muted">{item.name.slice(0, 1).toUpperCase()}</span>
                    )}
                  </Link>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-bold text-ink-soft">
                      <Link to={`product/${item.productId}?option=${encodeURIComponent(item.key)}`} className="transition hover:text-brand">{item.name}</Link>
                      {item.variantName ? <span className="font-semibold text-muted"> · {item.variantName}</span> : null}
                    </p>
                    {item.description ? (
                      <p className="mt-0.5 text-[11px] leading-4 text-muted">{item.description}</p>
                    ) : null}
                    <p className="mt-1 text-xs font-extrabold text-ink">{formatMoney(item.price, currency)}</p>
                  </div>
                  {!item.available ? (
                    <span className="shrink-0 rounded-lg bg-surface-sunken px-2 py-1 text-[10px] font-bold text-muted">
                      Sold out
                    </span>
                  ) : acceptOrders ? (
                    <div className="flex shrink-0 items-center gap-2">
                      <button
                        type="button"
                        aria-label={`Remove one ${item.name}`}
                        onClick={() => setQuantity(item.key, -1)}
                        disabled={!ready || !cart[item.key]}
                        className="flex h-8 w-8 items-center justify-center rounded-lg bg-surface-sunken text-ink-soft disabled:opacity-40"
                      >
                        −
                      </button>
                      <span className="w-5 text-center text-sm font-bold text-ink">{cart[item.key] || 0}</span>
                      <button
                        type="button"
                        aria-label={`Add one ${item.name}`}
                        onClick={() => setQuantity(item.key, 1)}
                        disabled={!ready}
                        className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand text-white"
                      >
                        +
                      </button>
                    </div>
                  ) : null}
                </article>
              ))}
            </div>
          </section>
        ))}
        {groups.size === 0 ? <p className="py-16 text-center text-sm text-muted">Nothing is available right now.</p> : null}
      </main>

      {Object.keys(policies).length ? (
        <footer className="mx-auto mt-10 max-w-[720px] px-5">
          <div className="rounded-2xl border border-line bg-surface p-4">
            <div className="space-y-2">
              {Object.entries(policies).map(([key, value]) => (
                <p key={key} className="text-[11px] leading-4 text-muted">
                  <span className="font-bold text-ink-soft">{POLICY_LABELS[key] || key}</span> · {value}
                </p>
              ))}
            </div>
          </div>
        </footer>
      ) : null}

      {count > 0 ? (
        <div className="fixed inset-x-0 bottom-0 border-t border-line bg-surface p-4 shadow-[0_-8px_24px_rgba(0,0,0,.06)]">
          <div className="mx-auto max-w-[720px]">
            {cartOpen ? (
              <div className="mb-3 max-h-[52vh] overflow-y-auto">
                {lines.map(([key, quantity]) => (
                  <div key={key} className="flex items-center gap-3 border-b border-line py-2 last:border-0">
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-xs font-bold text-ink-soft">
                        {byKey[key]?.name}
                        {byKey[key]?.variantName ? ` · ${byKey[key].variantName}` : ""}
                      </p>
                      <p className="text-[11px] text-muted">{formatMoney(byKey[key]?.price || 0, currency)} each</p>
                    </div>
                    <button type="button" onClick={() => setQuantity(key, -1)} className="h-7 w-7 rounded-lg bg-surface-sunken text-ink-soft">−</button>
                    <span className="w-5 text-center text-xs font-bold text-ink">{quantity}</span>
                    <button type="button" onClick={() => setQuantity(key, 1)} className="h-7 w-7 rounded-lg bg-brand text-white">+</button>
                  </div>
                ))}
                <div className="mt-3 grid gap-2 sm:grid-cols-2">
                  <input value={name} onChange={(event) => setName(event.target.value)} placeholder="Your name (optional)" className="h-10 rounded-xl border border-line bg-surface px-3 text-xs text-ink outline-none" />
                  <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="Email me a copy (optional)" className="h-10 rounded-xl border border-line bg-surface px-3 text-xs text-ink outline-none" />
                </div>
                <textarea value={note} onChange={(event) => setNote(event.target.value)} rows={2} placeholder="Note for the store (optional)" className="mt-2 w-full rounded-xl border border-line bg-surface px-3 py-2 text-xs text-ink outline-none" />
                {error ? <p className="mt-2 text-xs font-semibold text-danger">{error}</p> : null}
              </div>
            ) : error ? (
              <p className="mb-2 text-xs font-semibold text-danger">{error}</p>
            ) : null}
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-[11px] text-muted">{count} item{count === 1 ? "" : "s"}</p>
                <p className="text-sm font-extrabold text-ink">{formatMoney(total, currency)}</p>
              </div>
              {cartOpen ? (
                <button
                  type="button"
                  onClick={submit}
                  disabled={busy}
                  className="rounded-xl bg-brand px-5 py-2.5 text-sm font-bold text-white disabled:opacity-60"
                >
                  {busy ? "Placing..." : "Place order"}
                </button>
              ) : (
                <button
                  type="button"
                  onClick={() => setCartOpen(true)}
                  className="rounded-xl bg-brand px-5 py-2.5 text-sm font-bold text-white"
                >
                  View cart
                </button>
              )}
            </div>
          </div>
        </div>
      ) : null}

      <StoreChat companySlug={companySlug} storeSlug={storeSlug} storeName={store.store_name} />
    </div>
  );
}
