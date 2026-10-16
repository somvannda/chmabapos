import { redirect } from "react-router";

// The storefront host root has no content of its own: the directory lives at
// /stores and a store lives at /<company>/<store>.
//
// A visitor who lands on the bare host wants to browse, so send them straight to
// the directory. The placeholder this replaces told them to "open a store with the
// link its owner shared", which is useless to the one person most likely to be
// here - somebody arriving without a link.
//
// A redirect rather than rendering the directory at "/" so there is one canonical
// address for it and no duplicate content.
export function loader() {
  return redirect("/stores");
}

export function meta() {
  // Never seen: the redirect resolves before anything renders. Declared only so
  // the route module is complete.
  return [{ title: "Stores · Chmaba" }];
}

export default function Home() {
  return null;
}
