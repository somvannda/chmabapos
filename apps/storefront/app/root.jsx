import { isRouteErrorResponse, Links, Meta, Outlet, Scripts, ScrollRestoration, useRouteError } from "react-router";

import "./app.css";

import { originFrom } from "./lib/origin";
import { ChmabaFooter, ChmabaHeader } from "../../../packages/ui/chrome.jsx";

// The storefront renders inside the same chrome as chmaba.com, using the shared
// component in packages/ui rather than a copy, so the two hosts cannot drift apart.
// What differs here is deliberate: the nav goes back to the marketing sections, and
// the main button is the shopper's own orders - a shopper buying a bag of coffee is
// not being sold a point-of-sale workspace.
const CHMABA_URL = "https://chmaba.com";

const STOREFRONT_NAV = [
  { label: "Stores", href: "/stores" },
  { label: "Sell on Chmaba", href: CHMABA_URL, external: true },
];

const STOREFRONT_FOOTER_LINKS = [
  { label: "Privacy", href: `${CHMABA_URL}/privacy` },
  { label: "Terms", href: `${CHMABA_URL}/terms` },
  { label: "Contact", href: `${CHMABA_URL}/contact` },
  { label: "Refund policy", href: `${CHMABA_URL}/refund-policy` },
];

export function loader({ request }) {
  // The page's own origin, taken from the edge rather than from the internal
  // request, so an https visitor never gets http metadata. See lib/origin.js.
  return { origin: originFrom(request) };
}

export function Layout({ children }) {
  return (
    <html lang="en">
      <head>
        <meta charSet="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
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
  return (
    <div className="flex min-h-screen flex-col bg-page">
      <ChmabaHeader homeHref={CHMABA_URL} nav={STOREFRONT_NAV} cta={{ label: "Your orders", href: "/account" }} />
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
