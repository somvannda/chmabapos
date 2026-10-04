import { useEffect, useMemo, useState } from "react";
import { Minus, Plus, ShoppingBag, Check, Loader2, ExternalLink } from "lucide-react";
import { QRCodeSVG } from "qrcode.react";
import { api } from "../api";
import { Button, formatCurrencyAmount } from "../components/ui";

// Public, unauthenticated customer ordering page. Reached from the store's public
// link or a table QR code; the order is submitted to the existing ticket engine.
// When the store requires online payment, the page shows a KHQR and waits for it.
export function PublicOrderView({ storeToken }) {
  const [menu, setMenu] = useState(null);
  const [cart, setCart] = useState({});
  const [note, setNote] = useState("");
  const [customerName, setCustomerName] = useState("");
  const [customerEmail, setCustomerEmail] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [confirmed, setConfirmed] = useState(null);
  const [payOrder, setPayOrder] = useState(null);
  const [payChecking, setPayChecking] = useState(false);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const data = await api.publicMenu(storeToken);
        if (active) setMenu(data);
      } catch (requestError) {
        if (active) setError(requestError.message || "This menu is not available");
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => { active = false; };
  }, [storeToken]);

  // Poll a pending online payment until it settles, so the customer sees the
  // confirmation without having to do anything.
  useEffect(() => {
    if (!payOrder) return undefined;
    let active = true;
    const check = async () => {
      try {
        const status = await api.publicOrderPayment(storeToken, payOrder.id);
        if (active && status.paid) {
          setConfirmed({ ...payOrder, payment_status: "paid", paid: true });
          setPayOrder(null);
        }
      } catch { /* keep waiting; transient errors are fine */ }
    };
    const timer = window.setInterval(check, 3000);
    check();
    return () => { active = false; window.clearInterval(timer); };
  }, [payOrder, storeToken]);

  const byCategory = useMemo(() => {
    const groups = new Map();
    for (const item of (menu?.items || []).filter((item) => item.available)) {
      const key = item.category || "Menu";
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(item);
    }
    return [...groups.entries()];
  }, [menu]);
  const currency = menu?.currency_code || "USD";
  const priceOf = (id) => Number((menu?.items || []).find((item) => item.id === id)?.price || 0);
  const lines = Object.entries(cart).filter(([, qty]) => qty > 0);
  const total = lines.reduce((sum, [id, qty]) => sum + priceOf(id) * qty, 0);
  const setQty = (id, delta) => setCart((current) => {
    const next = { ...current, [id]: Math.max(0, (current[id] || 0) + delta) };
    if (next[id] === 0) delete next[id];
    return next;
  });
  const submit = async () => {
    if (!lines.length) return;
    setBusy(true);
    setError("");
    try {
      const order = await api.publicSubmitOrder(storeToken, { items: lines.map(([id, qty]) => ({ product_id: id, quantity: qty })), customer_note: note.trim() || null, customer_name: customerName.trim() || null, customer_email: customerEmail.trim() || null });
      setCart({});
      setNote("");
      setCustomerName("");
      setCustomerEmail("");
      if (order.payment_status === "pending" && (order.payment_qr_string || order.payment_checkout_url)) setPayOrder(order);
      else setConfirmed(order);
    } catch (requestError) {
      setError(requestError.message || "Could not place the order");
    } finally {
      setBusy(false);
    }
  };
  const checkPayment = async () => {
    if (!payOrder) return;
    setPayChecking(true);
    setError("");
    try {
      const status = await api.publicOrderPayment(storeToken, payOrder.id);
      if (status.paid) {
        setConfirmed({ ...payOrder, payment_status: "paid", paid: true });
        setPayOrder(null);
      }
    } catch (requestError) {
      setError(requestError.message || "Could not check the payment");
    } finally {
      setPayChecking(false);
    }
  };

  if (loading) return <div className="flex min-h-screen items-center justify-center bg-[#fafafd] text-sm text-[#92939d]">Loading menu...</div>;
  if (!menu) return <div className="flex min-h-screen items-center justify-center bg-[#fafafd] p-6 text-center text-sm text-[#c2564b]">{error || "This menu is not available"}</div>;

  if (payOrder) return <div className="flex min-h-screen items-center justify-center bg-[#fafafd] p-6"><div className="w-full max-w-[400px] rounded-2xl border border-[#e9e9ef] bg-white p-8 text-center"><h1 className="text-xl font-extrabold">Scan to pay</h1><p className="mt-2 text-sm text-[#777883]">Your order{menu.table_name ? ` · ${menu.table_name}` : ""} is held until payment is confirmed.</p><div className="mx-auto mt-5 flex h-[200px] w-[200px] items-center justify-center rounded-xl border-[7px] border-white bg-white p-3 shadow-sm">{payOrder.payment_qr_string ? <QRCodeSVG value={payOrder.payment_qr_string} size={178} /> : null}</div><p className="mt-4 text-2xl font-extrabold tracking-[-.03em]">{formatCurrencyAmount(Number(payOrder.total || 0), currency)}</p>{payOrder.payment_checkout_url ? <a href={payOrder.payment_checkout_url} target="_blank" rel="noreferrer" className="mt-3 inline-flex items-center gap-1.5 text-xs font-bold text-[#6957f5] hover:underline">Open checkout <ExternalLink size={13} /></a> : null}<p className="mt-5 flex items-center justify-center gap-2 text-xs text-[#92939d]"><Loader2 size={13} className="animate-spin" /> Waiting for payment...</p>{error && <p className="mt-3 text-xs text-[#c2564b]">{error}</p>}<div className="mt-5 flex flex-col gap-2"><Button onClick={checkPayment} disabled={payChecking}>{payChecking ? "Checking..." : "I have paid"}</Button><Button variant="outline" onClick={() => { setPayOrder(null); setError(""); }}>Cancel</Button></div></div></div>;

  if (confirmed) return <div className="flex min-h-screen items-center justify-center bg-[#fafafd] p-6"><div className="w-full max-w-[460px] rounded-2xl border border-[#dfe8d7] bg-white p-8 text-center"><div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-[#f0fbf0] text-[#4f9b3a]"><Check size={22} /></div><h1 className="mt-4 text-xl font-extrabold">Order placed</h1><p className="mt-2 text-sm text-[#777883]">Your order is with the kitchen{menu.table_name ? ` · ${menu.table_name}` : ""}.</p><p className="mt-1 text-sm font-bold">{formatCurrencyAmount(Number(confirmed.total || confirmed.subtotal || 0), currency)}</p><p className="mt-4 text-xs text-[#92939d]">{confirmed.payment_status === "paid" ? "Payment received. Thank you!" : "Please pay at the counter."}</p><Button className="mt-6" onClick={() => setConfirmed(null)}>Order more</Button></div></div>;

  return <div className="min-h-screen bg-[#fafafd] pb-40">
    <header className="border-b border-[#ececf2] bg-white px-5 py-4"><h1 className="text-lg font-extrabold tracking-[-.03em]">{menu.store_name || "Menu"}</h1>{menu.table_name ? <p className="mt-0.5 text-xs text-[#92939d]">{menu.table_name}</p> : null}</header>
    <main className="mx-auto max-w-[720px] p-5">
      {byCategory.map(([category, categoryItems]) => <section key={category} className="mt-5"><h2 className="text-xs font-bold uppercase tracking-wide text-[#a1a2ab]">{category}</h2><div className="mt-2 space-y-2">{categoryItems.map((item) => <div key={item.id} className="flex items-center gap-3 rounded-xl border border-[#ececf2] bg-white p-3"><div className="min-w-0 flex-1"><p className="truncate text-sm font-bold text-[#34353d]">{item.name}</p>{item.description ? <p className="mt-0.5 text-[11px] leading-4 text-[#92939d]">{item.description}</p> : null}<p className="mt-1 text-xs font-extrabold">{formatCurrencyAmount(Number(item.price), currency)}</p></div><div className="flex shrink-0 items-center gap-2"><button type="button" aria-label={`Remove ${item.name}`} onClick={() => setQty(item.id, -1)} disabled={!cart[item.id]} className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#f3f3f6] text-[#72737d] disabled:opacity-40"><Minus size={14} /></button><span className="w-6 text-center text-sm font-bold">{cart[item.id] || 0}</span><button type="button" aria-label={`Add ${item.name}`} onClick={() => setQty(item.id, 1)} className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#6957f5] text-white"><Plus size={14} /></button></div></div>)}</div></section>)}
      {byCategory.length === 0 && <p className="py-16 text-center text-sm text-[#92939d]">Nothing is available right now.</p>}
    </main>
    <div className="fixed inset-x-0 bottom-0 border-t border-[#ececf2] bg-white p-4"><div className="mx-auto max-w-[720px]"><div className="mb-2 flex flex-col gap-2 sm:flex-row"><input value={customerName} onChange={(event) => setCustomerName(event.target.value)} placeholder="Your name (optional)" className="h-9 flex-1 rounded-xl border border-[#dfdfe8] px-3 text-xs outline-none focus:border-[#887bf3]" /><input type="email" value={customerEmail} onChange={(event) => setCustomerEmail(event.target.value)} placeholder="Email me a copy (optional)" className="h-9 flex-1 rounded-xl border border-[#dfdfe8] px-3 text-xs outline-none focus:border-[#887bf3]" /></div><textarea value={note} onChange={(event) => setNote(event.target.value)} rows={2} placeholder="Note for the kitchen (optional)" className="w-full rounded-xl border border-[#dfdfe8] px-3 py-2 text-xs outline-none focus:border-[#887bf3]" />{error && <p className="mt-2 text-xs text-[#c2564b]">{error}</p>}<div className="mt-3 flex items-center justify-between"><span className="text-sm font-extrabold">{formatCurrencyAmount(total, currency)}</span><Button onClick={submit} disabled={busy || !lines.length}><ShoppingBag size={15} /> {busy ? "Placing..." : menu.require_online_payment ? "Place order & pay" : "Place order"}</Button></div></div></div>
  </div>;
}
