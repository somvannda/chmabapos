// Turning a store's saved social value into something a shopper can actually tap.
//
// Merchants type all three shapes - "@shop", "shop", or a whole pasted URL - so each
// network gets a prefix and the handle is tidied first. Anything unrecognised returns ""
// and the row is simply left out, rather than rendering a link that goes nowhere or
// printing the URL at the customer, which is what it used to do.

const PREFIXES = {
  telegram: "https://t.me/",
  instagram: "https://instagram.com/",
  facebook: "https://facebook.com/",
  tiktok: "https://tiktok.com/@",
};

export function socialHref(network, value) {
  const text = String(value || "").trim();
  if (!text) return "";
  // A pasted URL is already complete and is used exactly as given.
  if (/^https?:\/\//i.test(text)) return text;
  const prefix = PREFIXES[network];
  if (!prefix) return "";
  // Handles arrive with or without a leading @, and sometimes with stray slashes.
  const handle = text.replace(/^@+/, "").replace(/^\/+|\/+$/g, "").trim();
  return handle ? `${prefix}${handle}` : "";
}
