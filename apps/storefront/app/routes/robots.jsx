// Robots policy for the storefront host.
//
// Store pages and the directory are the entire point of this origin, so they are
// open to crawlers. The API and the media handler are not content and should not
// be crawled as pages, which is what the disallow rules are for.
export function loader() {
  const body = [
    "User-agent: *",
    "Allow: /",
    "Disallow: /api/",
    "Disallow: /media/",
    "",
  ].join("\n");
  return new Response(body, {
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
}
