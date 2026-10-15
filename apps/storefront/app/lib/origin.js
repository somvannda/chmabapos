// The page's own public origin.
//
// The SSR process is reached by nginx over plain HTTP, so `request.url` reports
// `http://` even though the visitor is on `https://`. Building metadata from it
// therefore produces http canonical links, an http `og:url`, and an http
// `og:image` - and Facebook blocks an http image, while an http canonical is
// simply wrong. The edge sets `X-Forwarded-Proto`, so that decides the scheme,
// with the request's own protocol as the fallback for a direct call.
//
// Kept in one place because the store page, the sitemap and anything added later
// all need the identical answer.
export function originFrom(request) {
  const url = new URL(request.url);
  const forwardedProto = (request.headers.get("x-forwarded-proto") || "").split(",")[0].trim();
  const proto = forwardedProto || url.protocol.replace(":", "");
  const host = request.headers.get("host") || url.host;
  return `${proto}://${host}`;
}
