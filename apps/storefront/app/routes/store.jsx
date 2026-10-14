import { isRouteErrorResponse, useLoaderData, useRouteError } from "react-router";

import { fetchStore, formatMoney } from "../lib/api";

const DAY_LABELS = { mon: "Mon", tue: "Tue", wed: "Wed", thu: "Thu", fri: "Fri", sat: "Sat", sun: "Sun" };
const SOCIAL_LABELS = { facebook: "Facebook", instagram: "Instagram", telegram: "Telegram", tiktok: "TikTok" };
const POLICY_LABELS = { returns: "Returns", delivery: "Delivery", privacy: "Privacy" };

export async function loader({ params }) {
  const store = await fetchStore(params.companySlug, params.storeSlug);
  if (!store) throw new Response("Store not found", { status: 404 });
  return { store };
}

export function meta({ data, params, error }) {
  if (!data || error) {
    return [{ title: "Store unavailable" }, { name: "robots", content: "noindex" }];
  }
  const name = data.store.store_name;
  const brand = data.store.storefront || {};
  const canonical = `/${params.companySlug}/${params.storeSlug}`;
  const image = brand.cover || brand.logo;
  return [
    { title: name },
    { name: "description", content: brand.tagline || `Browse ${name} and order on Chmaba.` },
    { tagName: "link", rel: "canonical", href: canonical },
    { property: "og:title", content: name },
    { property: "og:description", content: brand.tagline || `Browse ${name} on Chmaba.` },
    { property: "og:type", content: "website" },
    { property: "og:url", content: canonical },
    ...(image ? [{ property: "og:image", content: image }] : []),
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

function Hours({ hours }) {
  if (!hours?.length) return null;
  return (
    <dl className="mt-3 space-y-1">
      {hours.map((entry) => (
        <div key={entry.day} className="flex items-center justify-between gap-4 text-xs">
          <dt className="text-muted">{DAY_LABELS[entry.day] || entry.day}</dt>
          <dd className="font-semibold text-ink-soft">
            {entry.closed ? "Closed" : `${entry.open} – ${entry.close}`}
          </dd>
        </div>
      ))}
    </dl>
  );
}

// The merchant's own store page, on the storefront host, rendered server-side so
// it is useful before hydration and unfurls correctly when shared.
//
// Branding arrives two ways: the raw `storefront` bag (tagline, images, hours,
// policies) and the accent already resolved to design-token channels. Setting the
// two CSS variables is the entire theming step — the POS keeps the Chmaba palette
// because it never receives these overrides.
export default function Store() {
  const { store } = useLoaderData();
  const brand = store.storefront || {};
  const currency = store.currency_code || "USD";
  const socials = brand.socials || {};
  const policies = brand.policies || {};

  const groups = new Map();
  for (const item of store.items || []) {
    const key = item.category || "Menu";
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(item);
  }

  const theme = store.accent_brand
    ? { "--color-brand": store.accent_brand, ...(store.accent_soft ? { "--color-brand-soft": store.accent_soft } : {}) }
    : undefined;

  return (
    <div className="min-h-screen bg-page pb-20" style={theme}>
      {brand.cover ? (
        <div className="h-40 w-full overflow-hidden bg-surface-sunken sm:h-56">
          <img src={brand.cover} alt="" className="h-full w-full object-cover" />
        </div>
      ) : null}

      {brand.banner ? (
        <p className="bg-brand-soft px-5 py-2.5 text-center text-xs font-bold text-brand">{brand.banner}</p>
      ) : null}

      <header className="border-b border-line bg-surface px-5 py-5">
        <div className="mx-auto flex max-w-[720px] items-center gap-3">
          {brand.logo ? (
            <img src={brand.logo} alt="" className="h-12 w-12 shrink-0 rounded-xl border border-line object-cover" />
          ) : (
            <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-brand-soft text-lg font-black text-brand">
              {(store.store_name || "?").slice(0, 1).toUpperCase()}
            </span>
          )}
          <div className="min-w-0 flex-1">
            <h1 className="truncate text-xl font-extrabold tracking-[-.03em] text-ink">{store.store_name}</h1>
            {brand.tagline ? <p className="mt-0.5 truncate text-xs text-muted">{brand.tagline}</p> : null}
          </div>
          <OpenState isOpen={store.is_open} />
        </div>
      </header>

      <main className="mx-auto max-w-[720px] px-5">
        {[...groups.entries()].map(([category, items]) => (
          <section key={category} className="mt-6">
            <h2 className="text-xs font-bold uppercase tracking-wide text-muted">{category}</h2>
            <div className="mt-2 space-y-2">
              {items.map((item) => (
                <article key={item.id} className="flex items-start gap-3 rounded-xl border border-line bg-surface p-3">
                  {item.image ? (
                    <img src={item.image} alt="" className="h-14 w-14 shrink-0 rounded-lg object-cover" />
                  ) : null}
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-bold text-ink-soft">{item.name}</p>
                    {item.description ? (
                      <p className="mt-0.5 text-[11px] leading-4 text-muted">{item.description}</p>
                    ) : null}
                    <p className="mt-1 text-xs font-extrabold text-ink">{formatMoney(item.price, currency)}</p>
                  </div>
                  {item.available ? null : (
                    <span className="shrink-0 rounded-lg bg-surface-sunken px-2 py-1 text-[10px] font-bold text-muted">
                      Sold out
                    </span>
                  )}
                </article>
              ))}
            </div>
          </section>
        ))}
        {groups.size === 0 ? <p className="py-16 text-center text-sm text-muted">Nothing is available right now.</p> : null}
      </main>

      <footer className="mx-auto mt-10 max-w-[720px] px-5">
        <div className="rounded-2xl border border-line bg-surface p-4">
          <Hours hours={brand.hours} />
          {Object.keys(socials).length ? (
            <div className="mt-4 flex flex-wrap gap-2">
              {Object.entries(socials).map(([key, value]) => (
                <span key={key} className="rounded-lg bg-surface-sunken px-2.5 py-1 text-[11px] font-semibold text-ink-soft">
                  {SOCIAL_LABELS[key] || key} · {value}
                </span>
              ))}
            </div>
          ) : null}
          {Object.keys(policies).length ? (
            <div className="mt-4 space-y-2 border-t border-line pt-3">
              {Object.entries(policies).map(([key, value]) => (
                <p key={key} className="text-[11px] leading-4 text-muted">
                  <span className="font-bold text-ink-soft">{POLICY_LABELS[key] || key}</span> · {value}
                </p>
              ))}
            </div>
          ) : null}
          <p className="mt-4 border-t border-line pt-3 text-[10px] text-muted">Powered by Chmaba</p>
        </div>
      </footer>
    </div>
  );
}
