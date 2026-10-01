import { useEffect, useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import { CheckCircle2, Clock3, Monitor, Printer, QrCode, ScanLine, Store } from "lucide-react";
import { Logo, formatCurrencyAmount } from "../components/ui";
import { DISPLAY_STATUS, subscribeToDisplay } from "../lib/customerDisplay";

const EMPTY_SNAPSHOT = { items: [], currency: "USD", itemCount: 0, total: 0 };

function AmountRow({ label, text, value, currency, strong = false }) {
  return (
    <div className={`flex items-center justify-between ${strong ? "text-2xl font-extrabold tracking-[-.04em] text-[#17181c]" : "text-base font-semibold text-[#6b6c76]"}`}>
      <span>{label}</span>
      <span>{text ?? formatCurrencyAmount(value, currency)}</span>
    </div>
  );
}

function StoreIdentity({ brand, fallbackName }) {
  const name = brand?.name || fallbackName || "";
  return (
    <div className="mb-6 flex items-center gap-4">
      {brand?.logo ? (
        <img src={brand.logo} alt={name ? `${name} logo` : "Store logo"} className="h-16 w-auto max-w-[220px] shrink-0 object-contain" />
      ) : (
        <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl bg-[#f0efff] text-[#6957f5]">
          <Store size={30} />
        </div>
      )}
      <div className="min-w-0">
        {name && <p className="truncate text-2xl font-extrabold tracking-[-.04em] text-[#202128]">{name}</p>}
        {brand?.address && <p className="truncate text-sm text-[#92939d]">{brand.address}</p>}
      </div>
    </div>
  );
}

function ItemsPanel({ snapshot }) {
  const currency = snapshot.currency;
  if (snapshot.items.length === 0) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center text-center">
        <div className="flex h-20 w-20 items-center justify-center rounded-[26px] bg-[#f0efff] text-[#8a7df0]">
          <ScanLine size={34} />
        </div>
        <p className="mt-5 text-2xl font-extrabold tracking-[-.03em] text-[#202128]">Ready when you are</p>
        <p className="mt-2 text-base text-[#92939d]">Items for this sale will appear here.</p>
      </div>
    );
  }
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="app-scrollbar min-h-0 flex-1 overflow-y-auto pr-1">
        <ul className="space-y-1">
          {snapshot.items.map((line) => (
            <li key={line.key} className="flex items-center gap-4 rounded-2xl px-4 py-3 odd:bg-[#fafafd]">
              <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-[#f0efff] text-lg font-extrabold text-[#5b4be3]">
                {line.quantity}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-xl font-bold text-[#24252c]">{line.name}</span>
                <span className="block text-sm text-[#92939d]">{formatCurrencyAmount(line.unitPrice, currency)} each</span>
              </span>
              <span className="shrink-0 text-xl font-extrabold tracking-[-.03em] text-[#202128]">
                {formatCurrencyAmount(line.lineTotal, currency)}
              </span>
            </li>
          ))}
        </ul>
      </div>
      <div className="mt-4 space-y-2 border-t border-[#eeeeF2] pt-4">
        {snapshot.discount > 0 && (
          <AmountRow label="Discount" text={`-${formatCurrencyAmount(snapshot.discount, currency)}`} />
        )}
        {snapshot.tax > 0 && <AmountRow label={snapshot.taxLabel} value={snapshot.tax} currency={currency} />}
        {snapshot.tip > 0 && <AmountRow label="Tip" value={snapshot.tip} currency={currency} />}
        <div className="border-t border-[#eeeeF2] pt-3">
          <AmountRow label="Total" value={snapshot.total} currency={currency} strong />
        </div>
      </div>
    </div>
  );
}

function PaymentPanel({ snapshot }) {
  const payment = snapshot.payment || {};
  const currency = payment.currency || snapshot.currency;
  const amount = payment.amount ?? snapshot.total;
  return (
    <div className="flex flex-1 flex-col items-center justify-center text-center">
      <div className="flex items-center gap-2 text-[#465142]">
        <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-[#ed2939] text-[10px] font-extrabold text-white">KH</span>
        <span className="text-base font-extrabold">KHQR</span>
      </div>
      <p className="mt-3 text-3xl font-extrabold tracking-[-.04em] text-[#202128]">{formatCurrencyAmount(amount, currency)}</p>
      <p className="mt-1 text-base text-[#858690]">Scan with any Bakong-enabled banking app</p>
      <div className="mt-6 rounded-3xl border-[10px] border-white bg-white p-3 shadow-[0_18px_50px_rgba(20,21,28,.14)]">
        {payment.qrString ? (
          <QRCodeSVG value={payment.qrString} size={264} includeMargin level="M" />
        ) : (
          <div className="flex h-[264px] w-[264px] items-center justify-center text-[#c9cad3]">
            <QrCode size={72} />
          </div>
        )}
      </div>
      <p className="mt-5 flex items-center gap-2 text-sm font-semibold text-[#92939d]">
        <Clock3 size={15} /> Waiting for payment…
      </p>
    </div>
  );
}

function PaidPanel({ snapshot }) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center text-center">
      <div className="flex h-24 w-24 items-center justify-center rounded-full bg-[#edf9e4] text-[#5c9c39]">
        <CheckCircle2 size={52} />
      </div>
      <p className="mt-6 text-4xl font-extrabold tracking-[-.05em] text-[#202128]">Thank you!</p>
      <p className="mt-2 text-lg text-[#858690]">Payment received</p>
      {snapshot.total > 0 && (
        <p className="mt-4 text-3xl font-extrabold tracking-[-.04em] text-[#5c9c39]">
          {formatCurrencyAmount(snapshot.total, snapshot.currency)}
        </p>
      )}
      {snapshot.receiptPrinting && (
        <p className="mt-7 flex items-center gap-2 rounded-full bg-[#f3f2ff] px-4 py-2 text-base font-bold text-[#5b4be3]">
          <Printer size={18} /> Receipt is printing…
        </p>
      )}
    </div>
  );
}

function WaitingPanel() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center text-center">
      <div className="flex h-20 w-20 items-center justify-center rounded-[26px] bg-[#f0efff] text-[#8a7df0]">
        <Monitor size={34} />
      </div>
      <p className="mt-5 text-2xl font-extrabold tracking-[-.03em] text-[#202128]">Waiting for the register…</p>
      <p className="mt-2 max-w-[380px] text-base text-[#92939d]">
        Open this window from the POS — tap <span className="font-semibold text-[#5a5b64]">Open customer display</span> — so it can show the order and the payment QR.
      </p>
    </div>
  );
}

function CustomerDisplayView() {
  const [snapshot, setSnapshot] = useState(null);
  const [brand, setBrand] = useState(null);

  useEffect(() => subscribeToDisplay(setSnapshot, setBrand), []);

  const [showWaiting, setShowWaiting] = useState(false);
  useEffect(() => {
    if (snapshot || brand) { setShowWaiting(false); return undefined; }
    const handle = window.setTimeout(() => setShowWaiting(true), 1200);
    return () => window.clearTimeout(handle);
  }, [snapshot, brand]);

  const current = snapshot || EMPTY_SNAPSHOT;
  const status = snapshot?.status || DISPLAY_STATUS.IDLE;
  const isPaid = status === DISPLAY_STATUS.PAID;
  const isPayment = status === DISPLAY_STATUS.PAYMENT && Boolean(snapshot?.payment);

  return (
    <div className="flex min-h-screen flex-col bg-[#fafafd] text-[#17181c]">
      <header className="flex items-center justify-between gap-4 border-b border-[#eaeaef] bg-white px-6 py-5 sm:px-8">
        <Logo />
        <p className="text-xs text-[#92939d]">Customer display</p>
      </header>

      <main className="mx-auto flex w-full max-w-[1200px] flex-1 flex-col px-6 py-6 sm:px-8 sm:py-8">
        {showWaiting && !snapshot && !brand ? (
          <div className="flex flex-1 items-center justify-center rounded-3xl border border-[#e9e9ef] bg-white p-8 shadow-[0_14px_40px_rgba(28,31,42,.05)]">
            <WaitingPanel />
          </div>
        ) : (
        <>
        <StoreIdentity brand={brand} fallbackName={current.storeName} />

        <div className="grid min-h-0 flex-1 gap-6 lg:grid-cols-[1.35fr_1fr]">
          <section className="flex min-h-0 flex-col rounded-3xl border border-[#e9e9ef] bg-white p-6 shadow-[0_14px_40px_rgba(28,31,42,.05)]">
            <div className="mb-4 flex items-center justify-between gap-3">
              <h2 className="text-lg font-extrabold tracking-[-.03em]">Your order</h2>
              {current.itemCount > 0 && (
                <span className="rounded-full bg-[#f0efff] px-3 py-1 text-xs font-bold text-[#5b4be3]">
                  {current.itemCount} item{current.itemCount === 1 ? "" : "s"}
                </span>
              )}
            </div>
            <ItemsPanel snapshot={current} />
          </section>

          <section className="flex min-h-0 flex-col items-center justify-center rounded-3xl border border-[#e9e9ef] bg-white p-6 shadow-[0_14px_40px_rgba(28,31,42,.05)]">
            {isPaid ? (
              <PaidPanel snapshot={current} />
            ) : isPayment ? (
              <PaymentPanel snapshot={current} />
            ) : (
              <div className="text-center">
                <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-3xl bg-[#f0efff] text-[#8a7df0]">
                  <QrCode size={38} />
                </div>
                <p className="mt-5 text-xl font-extrabold tracking-[-.03em]">Pay here</p>
                <p className="mt-2 max-w-[240px] text-sm text-[#92939d]">
                  The QR code appears when the cashier starts the payment.
                </p>
              </div>
            )}
          </section>
        </div>
        </>
        )}
      </main>

      <footer className="px-6 pb-6 text-center text-sm text-[#a1a2ab] sm:px-8">
        Thank you for shopping with us · សូមអរគុណ
      </footer>
    </div>
  );
}

export { CustomerDisplayView };
