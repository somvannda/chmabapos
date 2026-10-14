import { index, route } from "@react-router/dev/routes";

// A store lives at the canonical public address /<company-slug>/<store-slug>,
// matching the URL the POS hands a merchant in Settings. Slugs are validated
// server-side against reserved words, which is why the store route can claim
// the two-segment shape without a blocklist here.
export default [index("routes/home.jsx"), route(":companySlug/:storeSlug", "routes/store.jsx")];
