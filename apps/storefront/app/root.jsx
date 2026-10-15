import { isRouteErrorResponse, Links, Meta, Outlet, Scripts, ScrollRestoration, useRouteError } from "react-router";

import "./app.css";

export function loader({ request }) {
  // The page's own origin. Metadata that must be absolute - the canonical URL and
  // the Open Graph image - is built from this rather than from another configured
  // value, so it cannot drift per environment.
  return { origin: new URL(request.url).origin };
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
  return <Outlet />;
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
