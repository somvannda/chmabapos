// Robots policy for the storefront host.
//
// Store pages and the directory are the entire point of this origin, so they are
// open to crawlers. The API and the media handler are not content and should not
// be crawled as pages, which is what the disallow rules are for.
export function loader({ request }) {
  // The Sitemap directive must be an absolute URL; a relative one is ignored.
  // Built from the request's own origin so it is correct on any host.
  const origin = new URL(request.url).origin;
  const body = [
    "User-agent: *",
    "Allow: /",
    "Disallow: /api/",
    "Disallow: /media/",
    `Sitemap: ${origin}/sitemap.xml`,
    "",
  ].join("\n");
  return new Response(body, {
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
}
