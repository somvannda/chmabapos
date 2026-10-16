import { isRouteErrorResponse, Links, Meta, Outlet, Scripts, ScrollRestoration, useLoaderData, useRouteError } from "react-router";

import "./app.css";

import { originFrom } from "./lib/origin";
import { ChmabaFooter, ChmabaHeader } from "../../../packages/ui/chrome.jsx";
import { fetchCategories } from "./lib/api";
import { categoryHref, categoryLabel } from "./lib/categories";
import { THEME_BOOTSTRAP } from "./lib/theme";
import { ThemeToggle } from "./components/ThemeToggle";

// The storefront renders inside the same chrome as chmaba.com, using the shared
// component in packages/ui rather than a copy, so the two hosts cannot drift apart.
// What differs here is deliberate: the nav goes back to the marketing sections, and
// the main button is the shopper's own orders - a shopper buying a bag of coffee is
// not being sold a point-of-sale workspace.
const CHMABA_URL = "https://chmaba.com";

const STOREFRONT_NAV = [
  { label: "Home", href: CHMABA_URL },
  { label: "Categories", type: "categories" },
  { label: "Stores", href: "/stores" },
  // A merchant CTA, so it points at the plans rather than the top of the homepage.
  { label: "Sell on Chmaba", href: `${CHMABA_URL}/#plans`, external: true },
];

const STOREFRONT_FOOTER_LINKS = [
  { label: "Privacy", href: `${CHMABA_URL}/privacy` },
  { label: "Terms", href: `${CHMABA_URL}/terms` },
  { label: "Contact", href: `${CHMABA_URL}/contact` },
  { label: "Refund policy", href: `${CHMABA_URL}/refund-policy` },
];

// The Categories menu sits in the chrome of every page, so it loads with the root rather
// than per route. A failure here must not take a page down with it - the menu simply
// hides, and the directory keeps its own filter chips.
async function safeCategories() {
  try {
    return await fetchCategories();
  } catch {
    return [];
  }
}

export async function loader({ request }) {
  // The page's own origin, taken from the edge rather than from the internal
  // request, so an https visitor never gets http metadata. See lib/origin.js.
  return { origin: originFrom(request), categories: await safeCategories() };
}

export function Layout({ children }) {
  return (
    <html lang="en">
      <head>
        <meta charSet="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        {/* Runs before anything paints, so a shopper who chose dark never sees a white
            flash on the way in. */}
        <script dangerouslySetInnerHTML={{ __html: THEME_BOOTSTRAP }} />
        <Meta />
        <Links />
      </head>
      <body>
        {children}
        <ScrollRestoration />
        <Scripts />
      </body>
    </html>
  );
}

export default function App() {
  const { categories = [] } = useLoaderData();
  return (
    <div className="flex min-h-screen flex-col bg-page">
      <ChmabaHeader
        homeHref={CHMABA_URL}
        nav={STOREFRONT_NAV}
        categories={categories.map((value) => ({ label: categoryLabel(value), href: categoryHref(value) }))}
        actions={<ThemeToggle />}
        cta={{ label: "Your orders", href: "/account" }}
      />
      <div className="flex-1">
        <Outlet />
      </div>
      <ChmabaFooter homeHref={CHMABA_URL} links={STOREFRONT_FOOTER_LINKS} />
    </div>
  );
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
        {notFound
          ? "The link may be mistyped, or the store has not published its page yet."
          : "Please try again in a moment."}
      </p>
    </main>
  );
}
