import { isRouteErrorResponse, useLoaderData, useRouteError } from "react-router";

import { fetchStore, formatMoney } from "../lib/api";

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
  const canonical = `/${params.companySlug}/${params.storeSlug}`;
  return [
    { title: name },
    { name: "description", content: `Browse ${name} and order on Chmaba.` },
    { tagName: "link", rel: "canonical", href: canonical },
    { property: "og:title", content: name },
    { property: "og:type", content: "website" },
    { property: "og:url", content: canonical },
  ];
}

export function ErrorBoundary() {
  const error = useRouteError();
  const notFound = isRouteErrorResponse(error) && error.status === 404;
  return (
    <main className="mx-auto flex min-h-screen max-w-[560px] flex-col items-center justify-center px-6 text-center">
      <h1 className="text-xl font-extrabold tracking-[-.03em]">
        {notFound ? "This store page is not available" : "Something went wrong"}
      </h1>
      <p className="mt-2 text-sm text-muted">
        {notFound ? "The link may be mistyped, or the store has not published its page yet." : "Please try again."}
      </p>
    </main>
  );
}

// Read-only menu for phase 3: the store's own page, on its own host, rendered
// server-side so it is useful before hydration and unfurls when shared. The
// cart and checkout arrive in phase 5, branding in phase 4.
export default function Store() {
  const { store } = useLoaderData();
  const currency = store.currency_code || "USD";
  const groups = new Map();
  for (const item of store.items || []) {
    const key = item.category || "Menu";
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(item);
  }

  return (
    <div className="min-h-screen bg-page pb-16">
      <header className="border-b border-line bg-surface px-5 py-5">
        <h1 className="text-xl font-extrabold tracking-[-.03em] text-ink">{store.store_name}</h1>
        {store.table_name ? <p className="mt-0.5 text-xs text-muted">{store.table_name}</p> : null}
      </header>
      <main className="mx-auto max-w-[720px] px-5">
        {[...groups.entries()].map(([category, items]) => (
          <section key={category} className="mt-6">
            <h2 className="text-xs font-bold uppercase tracking-wide text-muted">{category}</h2>
            <div className="mt-2 space-y-2">
              {items.map((item) => (
                <article key={item.id} className="flex items-start gap-3 rounded-xl border border-line bg-surface p-3">
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
    </div>
  );
}
