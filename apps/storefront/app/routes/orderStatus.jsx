import { isRouteErrorResponse, useLoaderData, useRouteError } from "react-router";

import { fetchOrderStatus, formatMoney } from "../lib/api";

// A customer's own order, reached from the confirmation screen or from a link
// they were sent. The token in the URL is the entire authorisation, which is why
// the page shows only what that token unlocks.
export async function loader({ params }) {
  const order = await fetchOrderStatus(params.token);
  if (!order) throw new Response("Order not found", { status: 404 });
  return { order };
}

export function meta() {
  // Nothing here should be indexed: it is one customer's order.
  return [{ title: "Your order" }, { name: "robots", content: "noindex" }];
}

export function ErrorBoundary() {
  const error = useRouteError();
  const notFound = isRouteErrorResponse(error) && error.status === 404;
  return (
    <main className="mx-auto flex min-h-screen max-w-[560px] flex-col items-center justify-center px-6 text-center">
      <h1 className="text-xl font-extrabold tracking-[-.03em] text-ink">
        {notFound ? "We can't find that order" : "Something went wrong"}
      </h1>
      <p className="mt-2 text-sm text-muted">
        {notFound
          ? "Check the link is complete, or ask the store for an update."
          : "Please try again in a moment."}
      </p>
    </main>
  );
}

const STATUS_COPY = {
  open: { label: "Order received", detail: "The store has your order." },
  fired: { label: "Being prepared", detail: "Your order is on its way to the kitchen." },
  ready: { label: "Ready", detail: "Your order is ready for collection." },
  paid: { label: "Completed", detail: "This order is closed. Thank you!" },
  cancelled: { label: "Cancelled", detail: "This order was cancelled by the store." },
};

export default function OrderStatus() {
  const { order } = useLoaderData();
  const known = STATUS_COPY[order.status] || { label: order.status, detail: "" };
  const paid = order.payment_status === "paid";

  return (
    <div className="min-h-screen bg-page px-5 py-12">
      <main className="mx-auto max-w-[460px]">
        <div className="rounded-2xl border border-line bg-surface p-7 text-center">
          <p className="text-[10px] font-bold uppercase tracking-wide text-muted">{order.store_name}</p>
          <h1 className="mt-2 text-xl font-extrabold tracking-[-.03em] text-ink">{known.label}</h1>
          {known.detail ? <p className="mt-1.5 text-sm text-ink-soft">{known.detail}</p> : null}

          <dl className="mt-6 space-y-2 border-t border-line pt-4 text-left">
            {order.label ? (
              <div className="flex items-center justify-between gap-4 text-xs">
                <dt className="text-muted">Reference</dt>
                <dd className="font-semibold text-ink-soft">{order.label}</dd>
              </div>
            ) : null}
            <div className="flex items-center justify-between gap-4 text-xs">
              <dt className="text-muted">Total</dt>
              <dd className="font-semibold text-ink-soft">{formatMoney(order.total, order.currency_code)}</dd>
            </div>
            <div className="flex items-center justify-between gap-4 text-xs">
              <dt className="text-muted">Payment</dt>
              <dd className="font-semibold text-ink-soft">
                {paid ? "Paid" : order.payment_status === "pending" ? "Awaiting payment" : "Pay on collection"}
              </dd>
            </div>
          </dl>

          {/* A status page is only useful if it can be re-checked; a manual reload
              is honest about that without pretending to be live. */}
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="mt-6 w-full rounded-xl bg-brand px-4 py-2.5 text-sm font-bold text-white"
          >
            Refresh status
          </button>
        </div>
        <p className="mt-4 text-center text-[10px] text-muted">Powered by Chmaba</p>
      </main>
    </div>
  );
}
