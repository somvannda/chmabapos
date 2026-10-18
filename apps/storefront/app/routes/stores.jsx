import { Form, Link, useLoaderData, useSearchParams } from "react-router";

import { fetchDirectory } from "../lib/api";

const PAGE_SIZE = 24;

export async function loader({ request }) {
  const url = new URL(request.url);
  const q = url.searchParams.get("q") || "";
  const vertical = url.searchParams.get("vertical") || "";
  const offset = Math.max(0, Number(url.searchParams.get("offset") || 0) || 0);
  const directory = await fetchDirectory({ q, vertical, limit: PAGE_SIZE, offset });
  return { q, vertical, offset, pageSize: PAGE_SIZE, ...directory };
}

export function meta({ data }) {
  const q = data?.q;
  return [
    { title: q ? `Stores matching “${q}” · Chmaba` : "Stores · Chmaba" },
    {
      name: "description",
      content: "Browse local stores on Chmaba and order directly from each shop.",
    },
  ];
}

function OpenState({ isOpen, compact }) {
  if (isOpen === null || isOpen === undefined) return null;
  const tone = isOpen ? "bg-success-soft text-success" : "bg-surface-sunken text-muted";
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 font-bold ${tone} ${compact ? "text-[10px]" : "text-[11px]"}`}>
      <span className={isOpen ? "h-1.5 w-1.5 rounded-full bg-success" : "h-1.5 w-1.5 rounded-full bg-muted"} />
      {isOpen ? "Open now" : "Closed"}
    </span>
  );
}

function StoreCard({ store }) {
  const cover = store.cover || "";
  const logo = store.logo || "";
  const initial = (store.store_name || "?").slice(0, 1).toUpperCase();
  // A store with no cover used to get a blank tinted band, which reads as a broken
  // image. The band now carries the logo, or the initial when there is no logo, and
  // the row below drops its avatar so the mark is not shown twice.
  return (
    <Link
      to={`/${store.company_slug}/${store.store_slug}`}
      target="_blank"
      rel="noopener noreferrer"
      className="group overflow-hidden rounded-2xl border border-line bg-surface transition hover:border-brand"
    >
      <div className="flex h-28 w-full items-center justify-center overflow-hidden bg-brand-soft">
        {cover ? (
          <img src={cover} alt="" className="h-full w-full object-cover" loading="lazy" />
        ) : logo ? (
          <img src={logo} alt="" className="h-14 w-14 rounded-2xl border border-line bg-surface object-cover shadow-sm" loading="lazy" />
        ) : (
          <span className="text-2xl font-black text-brand">{initial}</span>
        )}
      </div>
      <div className="p-3.5">
        <div className="flex items-center gap-2.5">
          {cover ? (
            logo ? (
              <img src={logo} alt="" className="-mt-8 h-10 w-10 shrink-0 rounded-xl border border-line bg-surface object-cover" loading="lazy" />
            ) : (
              <span className="-mt-8 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-line bg-brand text-sm font-black text-white">{initial}</span>
            )
          ) : null}
          <p className="min-w-0 flex-1 truncate text-sm font-extrabold text-ink">{store.store_name}</p>
        </div>
        {store.tagline ? <p className="mt-1.5 line-clamp-2 text-[11px] leading-4 text-muted">{store.tagline}</p> : null}
        {store.address ? <p className="mt-1.5 truncate text-[11px] text-muted">{store.address}</p> : null}
        {store.banner ? <p className="mt-2 truncate text-[10px] font-bold text-brand">{store.banner}</p> : null}
        <div className="mt-2.5">
          <OpenState isOpen={store.is_open} compact />
        </div>
      </div>
    </Link>
  );
}

export default function Stores() {
  // Defaulted rather than trusted: the loader spreads what the API said, and a route that
  // cannot be reached must render an empty directory instead of throwing on `.length`.
  const { stores = [], total = 0, verticals = [], unavailable = false, q, vertical, offset, pageSize } = useLoaderData();
  const [searchParams] = useSearchParams();
  const hasPrevious = offset > 0;
  const hasNext = offset + stores.length < total;

  // Filters reset paging, since offset 48 of the old result set is meaningless
  // under a new one.
  const filterHref = (nextVertical) => {
    const params = new URLSearchParams();
    if (q) params.set("q", q);
    if (nextVertical) params.set("vertical", nextVertical);
    const qs = params.toString();
    return qs ? `/stores?${qs}` : "/stores";
  };

  const chipClass = (active) =>
    active
      ? "rounded-full bg-brand px-3 py-1.5 text-[11px] font-bold text-white"
      : "rounded-full border border-line px-3 py-1.5 text-[11px] font-semibold text-ink-soft";

  const pageHref = (nextOffset) => {
    const params = new URLSearchParams(searchParams);
    params.set("offset", String(nextOffset));
    return `/stores?${params.toString()}`;
  };

  return (
    <div className="min-h-screen bg-page pb-16">
      <header className="border-b border-line bg-surface px-5 py-6">
        <div className="mx-auto max-w-[1000px]">
          <h1 className="text-2xl font-extrabold tracking-[-.04em] text-ink">Stores</h1>
          <p className="mt-1 text-sm text-muted">Order directly from a local shop.</p>
          {/* A plain GET form, so search works before hydration and in a plain link. */}
          <Form method="get" action="/stores" className="mt-4 flex gap-2">
            <input
              type="search"
              name="q"
              defaultValue={q}
              placeholder="Search stores"
              className="h-10 min-w-0 flex-1 rounded-xl border border-line bg-surface px-3.5 text-sm text-ink outline-none focus:border-brand"
            />
            <button type="submit" className="rounded-xl bg-brand px-4 text-sm font-bold text-white">
              Search
            </button>
          </Form>
          {/* Chips come from the API's facet, so a new business type appears here
              without a front-end change - and picking one still shows the others. */}
          {verticals.length > 1 ? (
            <div className="mt-3 flex flex-wrap gap-2">
              <Link to={filterHref("")} className={chipClass(!vertical)}>
                All
              </Link>
              {verticals.map((value) => (
                <Link key={value} to={filterHref(value)} className={chipClass(vertical === value)}>
                  {value.charAt(0).toUpperCase() + value.slice(1)}
                </Link>
              ))}
            </div>
          ) : null}
        </div>
      </header>

      <main className="mx-auto max-w-[1000px] px-5">
        <p className="mt-5 text-xs text-muted">
          {unavailable ? "Directory unavailable" : total === 0 ? "No stores found" : `${total} store${total === 1 ? "" : "s"}`}
          {q ? ` matching “${q}”` : ""}
        </p>

        {stores.length === 0 ? (
          <div className="mt-6 rounded-2xl border border-line bg-surface p-10 text-center">
            <p className="text-sm font-bold text-ink-soft">
              {unavailable
                ? "The store directory is temporarily unavailable."
                : q
                  ? "No stores match that search."
                  : "No stores are listed yet."}
            </p>
            {unavailable ? (
              <p className="mt-2 text-xs text-muted">Please try again in a moment.</p>
            ) : null}
            {q && !unavailable ? (
              <Link to="/stores" className="mt-2 inline-block text-xs font-bold text-brand">
                Clear search
              </Link>
            ) : null}
          </div>
        ) : (
          <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {stores.map((store) => (
              <StoreCard key={`${store.company_slug}/${store.store_slug}`} store={store} />
            ))}
          </div>
        )}

        {(hasPrevious || hasNext) && (
          <nav className="mt-8 flex items-center justify-between">
            {hasPrevious ? (
              <Link to={pageHref(Math.max(0, offset - pageSize))} className="rounded-xl border border-line px-4 py-2 text-xs font-bold text-ink-soft">
                Previous
              </Link>
            ) : (
              <span />
            )}
            {hasNext ? (
              <Link to={pageHref(offset + pageSize)} className="rounded-xl border border-line px-4 py-2 text-xs font-bold text-ink-soft">
                Next
              </Link>
            ) : (
              <span />
            )}
          </nav>
        )}
      </main>
    </div>
  );
}
