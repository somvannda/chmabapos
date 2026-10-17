import { index, route } from "@react-router/dev/routes";

// A store lives at the canonical public address /<company-slug>/<store-slug>,
// matching the URL the POS hands a merchant in Settings. Slugs are validated
// server-side against reserved words, which is why the store route can claim
// the two-segment shape without a blocklist here.
export default [
  index("routes/home.jsx"),
  // Must be declared alongside the store route: `/stores` is one segment, so it
  // cannot collide with the two-segment /<company>/<store> shape.
  route("stores", "routes/stores.jsx"),
  // Declared before the store route so the static segment wins. Company slugs
  // cannot be "order" anyway - it is in the reserved list - so the two can never
  // actually collide.
  route("order/:token", "routes/orderStatus.jsx"),
  route("account", "routes/account.jsx"),
  // A crawler policy. Listed before the store route so the intent is explicit;
  // it is a literal path, not a slug, so there is no ambiguity either way.
  route("robots.txt", "routes/robots.jsx"),
  // Liveness for the container healthcheck. One literal segment, so it cannot
  // collide with the two-segment /<company>/<store> shape.
  route("healthz", "routes/healthz.jsx"),
  route("sitemap.xml", "routes/sitemap.jsx"),
  // Declared before the store route: it is the same two segments plus a literal
  // "product" and an id, so the more specific address has to be matched first.
  route(":companySlug/:storeSlug/product/:productId", "routes/product.jsx"),
  route(":companySlug/:storeSlug", "routes/store.jsx"),
];
