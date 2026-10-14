import { fetchDirectory } from "../lib/api";

// A sitemap for the storefront host.
//
// Only listed, published stores appear, so the sitemap never advertises a page a
// merchant has deliberately kept out of the directory - which is also what keeps
// it consistent with robots.txt and the directory itself.
//
// Sitemaps require absolute URLs, so they are built from the request's own origin
// rather than a configured host. That keeps it correct on the storefront domain,
// on a preview host, and on localhost without any extra configuration.

const PAGE_SIZE = 60; // the API's maximum
const MAX_PAGES = 20; // a deliberately bounded crawl; 1200 stores

export async function loader({ request }) {
  const origin = new URL(request.url).origin;
  // "/" is deliberately excluded: it is a thin placeholder marked noindex, and a
  // URL that is noindex must not be *submitted* in a sitemap - that is a reported
  // Search Console error, not a harmless redundancy. The directory is the real
  // entry point.
  const paths = ["/stores"];

  let offset = 0;
  for (let page = 0; page < MAX_PAGES; page += 1) {
    const { stores, total } = await fetchDirectory({ limit: PAGE_SIZE, offset });
    for (const store of stores || []) {
      paths.push(`/${store.company_slug}/${store.store_slug}`);
    }
    offset += (stores || []).length;
    // Stop when the directory is exhausted, or if a page comes back empty - which
    // would otherwise loop until the cap.
    if (!stores?.length || offset >= total) break;
  }

  const entries = paths
    .map((path) => `  <url><loc>${origin}${path}</loc></url>`)
    .join("\n");
  const body = `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${entries}\n</urlset>\n`;

  return new Response(body, {
    headers: {
      "Content-Type": "application/xml; charset=utf-8",
    },
  });
}
