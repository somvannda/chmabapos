import { useEffect, useState } from "react";
import { Link, redirect, useLoaderData, useParams, useSearchParams } from "react-router";

import { fetchStore, formatMoney } from "../lib/api";
import { canonicalRedirect } from "../lib/address";
import { cartKey } from "../lib/cart";
import { useCart } from "../lib/useCart";
import { addModifiersToLineKey, modifierDelta, selectionComplete } from "../lib/modifiers";

// The product page: everything a card deliberately leaves out.
//
// Cards are summaries - image, name, price, a way to add - because a shelf of full
// specifications is unreadable. Choosing between options, reading the description and
// checking a spec belong here, on one product, with the store's own switches deciding
// how much of it is published at all (Settings -> Store page).

/** One entry per thing that can be ordered: each variant, or the product itself. */
export function orderableOptions(item) {
  const variants = Array.isArray(item.variants) ? item.variants : [];
  if (variants.length) {
    return variants.map((variant) => ({
      key: `${item.id}:${variant.id}`,
      label: variant.name,
      price: Number(variant.price),
      available: variant.available,
    }));
  }
  return [{ key: item.id, label: null, price: Number(item.price), available: item.available }];
}

export async function loader({ params }) {
  const store = await fetchStore(params.companySlug, params.storeSlug);
  if (!store) throw new Response("Store not found", { status: 404 });
  // Same rename rule as the store page: a retired slug resolves, then the
  // visitor is sent to the canonical address with the product still in the path.
  const canonical = canonicalRedirect(store, params, { productId: params.productId });
  if (canonical) throw redirect(canonical, 301);
  const item = (store.items || []).find((row) => String(row.id) === String(params.productId));
  // A product that is gone, or was never published, is a 404 rather than an empty page.
  if (!item) throw new Response("Product not found", { status: 404 });
  return { store, item };
}

export function meta({ data, params, error, matches }) {
  if (!data || error) {
    return [{ title: "Product unavailable" }, { name: "robots", content: "noindex" }];
  }
  const { store, item } = data;
  // Absolute, because crawlers and unfurlers ignore a relative canonical or image.
  const origin = matches?.find((match) => match?.id === "root")?.data?.origin || "";
  const absolute = (value) => {
    if (!value) return "";
    if (/^https?:\/\//i.test(value)) return value;
    return origin ? `${origin}${value.startsWith("/") ? "" : "/"}${value}` : value;
  };
  const title = `${item.name} · ${store.store_name}`;
  const url = absolute(`/${params.companySlug}/${params.storeSlug}/product/${params.productId}`);
  const currency = store.currency_code || "USD";
  const options = orderableOptions(item);
  const prices = options.map((option) => option.price);
  return [
    { title },
    ...(item.description ? [{ name: "description", content: item.description.slice(0, 300) }] : []),
    { tag: "link", rel: "canonical", href: url },
    { property: "og:title", content: title },
    { property: "og:type", content: "product" },
    { property: "og:url", content: url },
    ...(item.image ? [{ property: "og:image", content: absolute(item.image) }] : []),
    {
      "script:ld+json": {
        "@context": "https://schema.org",
        "@type": "Product",
        name: item.name,
        ...(item.image ? { image: absolute(item.image) } : {}),
        ...(item.description ? { description: item.description } : {}),
        ...(item.sku ? { sku: item.sku } : {}),
        ...(item.brand ? { brand: { "@type": "Brand", name: item.brand } } : {}),
        offers: {
          "@type": "Offer",
          price: Math.min(...prices),
          priceCurrency: currency,
          availability: options.some((option) => option.available)
            ? "https://schema.org/InStock"
            : "https://schema.org/OutOfStock",
        },
      },
    },
  ];
}

function Spec({ label, value }) {
  return (
    <div className="flex items-start justify-between gap-6 border-b border-line py-2 last:border-0">
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="text-xs font-semibold text-ink-soft">{value}</dd>
    </div>
  );
}

export default function Product() {
  const { store, item } = useLoaderData();
  const { companySlug, storeSlug } = useParams();
  const brand = store.storefront || {};
  // Which optional fields this store publishes. Absent means none, which is the
  // API's default too.
  const display = brand.display || {};
  const currency = store.currency_code || "USD";
  const options = orderableOptions(item);
  const { cart, setQuantity } = useCart(cartKey(companySlug, storeSlug));
  // Disabled until React is listening, for the same reason as the store page: the markup
  // is server-rendered, so a press before hydration would otherwise vanish silently.
  const [ready, setReady] = useState(false);
  useEffect(() => setReady(true), []);
  // A card that names an option should land on that option - otherwise start on the
  // first one that can actually be bought, so the price shown is one a shopper can pay.
  const [searchParams] = useSearchParams();
  const [picked, setPicked] = useState(() => {
    const wanted = searchParams.get("option");
    if (options.some((option) => option.key === wanted)) return wanted;
    return (options.find((option) => option.available) || options[0]).key;
  });
  const chosen = options.find((option) => option.key === picked) || options[0];
  const storeHref = `/${companySlug}/${storeSlug}`;

  // The product's own add-on groups. Each choice is applied to the line, so the
  // price shown and the line added both reflect it; the API is still the one that
  // prices the order when it is submitted.
  const modifierGroups = Array.isArray(item.modifier_groups) ? item.modifier_groups : [];
  const [selectedByGroup, setSelectedByGroup] = useState({});
  const toggleModifier = (group, name) => {
    setSelectedByGroup((current) => {
      const selected = current[group.id] || [];
      const max = Math.max(1, Number(group.max_select) || 1);
      if (selected.includes(name)) return { ...current, [group.id]: selected.filter((entry) => entry !== name) };
      // A single-select group replaces its choice; a multi-select fills to its cap.
      const next = max === 1 ? [name] : selected.length >= max ? selected : [...selected, name];
      return { ...current, [group.id]: next };
    });
  };
  const selectedNames = modifierGroups.flatMap((group) => selectedByGroup[group.id] || []);
  const unitPrice = chosen.price + modifierDelta(modifierGroups, selectedNames);
  const complete = selectionComplete(modifierGroups, selectedByGroup);
  // The cart line carries the selection in its key, so two selections of the same
  // product are two lines - and only names travel, never prices.
  const lineKey = addModifiersToLineKey(chosen.key, selectedNames);

  return (
    <div className="min-h-screen bg-page pb-24">
      <div className="mx-auto max-w-[900px] px-4 sm:px-5">
        <nav className="py-4">
          <Link to={storeHref} className="text-xs font-semibold text-muted transition hover:text-brand">
            ← {store.store_name}
          </Link>
        </nav>

        <div className="grid gap-6 sm:grid-cols-2">
          <div className="overflow-hidden rounded-2xl border border-line bg-surface">
            {item.image ? (
              <img src={item.image} alt="" className="aspect-square w-full object-cover" />
            ) : (
              <span className="flex aspect-square w-full items-center justify-center bg-surface-sunken text-3xl font-black text-muted">
                {item.name.slice(0, 1).toUpperCase()}
              </span>
            )}
          </div>

          <div>
            <h1 className="text-xl font-extrabold tracking-[-.03em] text-ink">{item.name}</h1>
            {brand.tagline ? <p className="mt-1 text-xs text-muted">{brand.tagline}</p> : null}
            <p className="mt-3 text-lg font-extrabold text-ink">{formatMoney(unitPrice, currency)}</p>

            {item.description ? (
              <p className="mt-3 whitespace-pre-line text-xs leading-5 text-ink-soft">{item.description}</p>
            ) : null}

            {/* Options first: until one is chosen, the price above is only "from". */}
            {options.length > 1 ? (
              <div className="mt-4">
                <p className="text-[10px] font-bold uppercase tracking-wide text-muted">
                  Choose an option{options.length > 1 ? ` (${options.length})` : ""}
                </p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {options.map((option) => (
                    <button
                      key={option.key}
                      type="button"
                      disabled={!option.available}
                      onClick={() => setPicked(option.key)}
                      className={`rounded-lg px-3 py-1.5 text-[11px] font-bold transition disabled:opacity-40 ${
                        option.key === chosen.key ? "bg-brand text-white" : "bg-surface-sunken text-ink-soft"
                      }`}
                    >
                      {option.label || "Standard"}
                    </button>
                  ))}
                </div>
              </div>
            ) : null}

            {/* The shop's own add-on groups, chosen before the line is added. */}
            {modifierGroups.length ? (
              <div className="mt-4 space-y-4">
                {modifierGroups.map((group) => {
                  const selected = selectedByGroup[group.id] || [];
                  const max = Math.max(1, Number(group.max_select) || 1);
                  const single = max === 1;
                  const atCap = selected.length >= max;
                  return (
                    <div key={group.id}>
                      <p className="text-[10px] font-bold uppercase tracking-wide text-muted">
                        {group.name}
                        {group.is_required ? <span className="ml-1 text-brand">Required</span> : null}
                        <span className="ml-1 font-normal">· choose {single ? "1" : `up to ${max}`}</span>
                      </p>
                      <div className="mt-2 flex flex-wrap gap-2">
                        {(group.modifiers || []).map((modifier) => {
                          const isOn = selected.includes(String(modifier.name));
                          return (
                            <button
                              key={modifier.id}
                              type="button"
                              aria-pressed={isOn}
                              disabled={!isOn && !single && atCap}
                              onClick={() => toggleModifier(group, String(modifier.name))}
                              className={`rounded-lg px-3 py-1.5 text-[11px] font-bold transition disabled:opacity-40 ${
                                isOn ? "bg-brand text-white" : "bg-surface-sunken text-ink-soft"
                              }`}
                            >
                              {modifier.name}
                              {Number(modifier.price_delta) ? <span className="ml-1 font-semibold">+{formatMoney(Number(modifier.price_delta), currency)}</span> : null}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : null}

            <div className="mt-5">
              {!chosen.available ? (
                <p className="rounded-xl bg-surface-sunken px-4 py-3 text-xs font-bold text-muted">Sold out</p>
              ) : brand.accept_orders === false ? (
                <p className="rounded-xl border border-line bg-surface px-4 py-3 text-xs font-semibold text-ink-soft">
                  This store is not taking orders right now.
                </p>
              ) : (
                <div>
                  <div className="flex items-center gap-3">
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        aria-label={`Remove one ${item.name}`}
                        onClick={() => setQuantity(lineKey, -1)}
                        disabled={!ready || !cart[lineKey]}
                        className="flex h-9 w-9 items-center justify-center rounded-lg bg-surface-sunken text-ink-soft disabled:opacity-40"
                      >
                        −
                      </button>
                      <span className="w-6 text-center text-sm font-bold text-ink">{cart[lineKey] || 0}</span>
                      <button
                        type="button"
                        aria-label={`Add one ${item.name}`}
                        onClick={() => setQuantity(lineKey, 1)}
                        disabled={!ready || !complete}
                        className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand text-white disabled:opacity-40"
                      >
                        +
                      </button>
                    </div>
                    <Link to={storeHref} className="text-xs font-semibold text-brand">View the cart</Link>
                  </div>
                  {!complete ? <p className="mt-2 text-[11px] font-semibold text-muted">Choose the required options above.</p> : null}
                </div>
              )}
            </div>
          </div>
        </div>

        {/*
          Only what the store switched on. Before this the page had no way to tell a
          shop that publishes its specs from one that does not, so each row is gated.
        */}
        {(display.sku || display.brand || display.unit || display.barcode || display.attributes || (display.serials && item.serials?.length)) ? (
          <section className="mt-8 rounded-2xl border border-line bg-surface p-4 sm:p-5">
            <h2 className="text-xs font-extrabold text-ink">Details</h2>
            <dl className="mt-2">
              {display.sku && item.sku ? <Spec label="SKU" value={item.sku} /> : null}
              {display.brand && item.brand ? <Spec label="Brand" value={item.brand} /> : null}
              {display.unit && item.unit ? <Spec label="Unit" value={item.unit} /> : null}
              {display.barcode && item.barcode ? <Spec label="Barcode" value={item.barcode} /> : null}
              {display.attributes && item.attributes
                ? Object.entries(item.attributes).map(([key, value]) => <Spec key={key} label={key} value={String(value)} />)
                : null}
            </dl>
            {display.serials && item.serials?.length ? (
              <div className="mt-4 border-t border-line pt-3">
                <p className="text-[10px] font-bold uppercase tracking-wide text-muted">
                  In stock ({item.serials.length})
                </p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {item.serials.map((masked) => (
                    <span key={masked} className="rounded-lg bg-surface-sunken px-2.5 py-1 font-mono text-[11px] font-semibold text-ink-soft">
                      {masked}
                    </span>
                  ))}
                </div>
                <p className="mt-2 text-[10px] text-muted">
                  Masked: the middle of each serial is hidden. Quote the visible part to check a unit against its box.
                </p>
              </div>
            ) : null}
          </section>
        ) : null}
      </div>
    </div>
  );
}
