import { useEffect, useState } from "react";
import { RefreshCw, Truck } from "lucide-react";
import { Button, Badge, formatCurrencyAmount } from "../components/ui";
import { api } from "../api";
import { useCapabilities, allowsCapability } from "../lib/capabilities";

// Delivery dispatch board. Lists delivery orders and lets staff assign a driver
// and advance the drop-off: not dispatched -> assigned -> out for delivery ->
// delivered (or failed).
const STATUS_TONES = { none: "neutral", pending: "yellow", assigned: "violet", out_for_delivery: "blue", delivered: "green", failed: "red" };
const STATUS_LABELS = { none: "Not dispatched", pending: "Pending", assigned: "Assigned", out_for_delivery: "Out for delivery", delivered: "Delivered", failed: "Failed" };
const NEXT = { none: "assigned", pending: "assigned", assigned: "out_for_delivery", out_for_delivery: "delivered" };
const FILTERS = [
  { value: "", label: "All" },
  { value: "pending", label: "Pending" },
  { value: "assigned", label: "Assigned" },
  { value: "out_for_delivery", label: "Out for delivery" },
  { value: "delivered", label: "Delivered" },
];

function LiveDeliveriesView({ token, storeId, notify, baseCurrency = "USD" }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState("");
  const capabilities = useCapabilities(token, storeId);
  const enabled = allowsCapability(capabilities, "tables");

  const load = async (nextFilter) => {
    if (!storeId || capabilities === null || !enabled) return;
    setLoading(true);
    try {
      const active = nextFilter === undefined ? filter : nextFilter;
      const params = active ? { status: active } : {};
      setRows(await api.deliveries(token, storeId, params));
      setError("");
    } catch (requestError) {
      setError(requestError.message || "Could not load deliveries");
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { load(); }, [token, storeId, capabilities]);
  useEffect(() => {
    if (!enabled) return undefined;
    const timer = window.setInterval(() => load(), 30000);
    return () => window.clearInterval(timer);
  }, [enabled, token, storeId]);

  const replace = (updated) => setRows((current) => current.map((entry) => (entry.id === updated.id ? updated : entry)));
  const advance = async (row) => {
    const next = NEXT[row.delivery_status] || "assigned";
    try {
      replace(await api.updateDelivery(token, storeId, row.id, { status: next }));
      notify(`Delivery ${row.order_number} → ${STATUS_LABELS[next]}`);
    } catch (requestError) {
      notify(requestError.message || "Could not update the delivery");
    }
  };
  const setFailed = async (row) => {
    try {
      replace(await api.updateDelivery(token, storeId, row.id, { status: "failed" }));
    } catch (requestError) {
      notify(requestError.message || "Could not update the delivery");
    }
  };
  const assignDriver = async (row) => {
    const driver = window.prompt("Driver name", row.driver_name || "");
    if (driver === null) return;
    const dispatch = row.delivery_status === "none" || row.delivery_status === "pending" ? "assigned" : row.delivery_status;
    try {
      replace(await api.updateDelivery(token, storeId, row.id, { driver_name: driver.trim() || null, status: dispatch }));
    } catch (requestError) {
      notify(requestError.message || "Could not assign the driver");
    }
  };
  const editAddress = async (row) => {
    const address = window.prompt("Delivery address", row.delivery_address || "");
    if (address === null) return;
    try {
      replace(await api.updateDelivery(token, storeId, row.id, { delivery_address: address.trim() || null }));
      notify("Delivery address updated");
    } catch (requestError) {
      notify(requestError.message || "Could not update the address");
    }
  };

  if (!enabled) {
    return <div className="mx-auto max-w-[1460px] p-5 lg:p-8"><div className="rounded-2xl border border-[#e9e9ef] bg-white p-12 text-center"><Truck size={22} className="mx-auto text-[#c9cad3]" /><p className="mt-3 text-sm font-bold text-[#565762]">Deliveries are off</p><p className="mt-1 text-xs text-[#92939d]">Turn on the Tables pack in Settings &rarr; Feature packs to dispatch delivery orders.</p></div></div>;
  }

  return <div className="mx-auto max-w-[1460px] p-5 lg:p-8">
    <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
      <div><h2 className="text-2xl font-extrabold tracking-[-.05em]">Deliveries</h2><p className="mt-1 text-sm text-[#898a95]">Dispatch delivery orders, assign a driver, and track the drop-off.</p></div>
      <Button variant="outline" onClick={() => load()} disabled={loading}><RefreshCw size={15} /> Refresh</Button>
    </div>
    <div className="mt-5 flex flex-wrap items-center gap-1.5">{FILTERS.map((item) => <button key={item.value} type="button" onClick={() => { setFilter(item.value); load(item.value); }} className={`rounded-lg px-3 py-2 text-xs font-bold transition ${filter === item.value ? "bg-[#17181c] text-white" : "bg-white text-[#858690] hover:bg-[#efeff4]"}`}>{item.label}</button>)}</div>
    {error && <p className="mt-5 rounded-xl border border-[#ffd7d2] bg-[#fff5f3] px-3 py-2.5 text-xs text-[#c2564b]">{error}</p>}
    {loading && rows.length === 0 ? <p className="mt-7 rounded-2xl border border-[#e9e9ef] bg-white py-16 text-center text-xs text-[#92939d]">Loading deliveries...</p>
      : rows.length === 0 ? <div className="mt-7 rounded-2xl border border-[#e9e9ef] bg-white py-16 text-center"><Truck size={22} className="mx-auto text-[#c9cad3]" /><p className="mt-3 text-sm font-bold text-[#565762]">No deliveries</p><p className="mt-1 text-xs text-[#92939d]">Delivery orders taken at the register appear here.</p></div>
        : <div className="mt-5 overflow-hidden rounded-2xl border border-[#e9e9ef] bg-white"><div className="app-scrollbar overflow-x-auto"><table className="mobile-table w-full min-w-[820px] border-collapse text-left text-xs"><thead><tr className="border-b border-[#f0f0f3] bg-[#fcfcfd] text-[10px] font-bold uppercase tracking-wide text-[#a1a2ab]"><th className="px-4 py-3">Order</th><th className="px-4 py-3">Customer</th><th className="px-4 py-3">Address</th><th className="px-4 py-3">Driver</th><th className="px-4 py-3">Total</th><th className="px-4 py-3">Status</th><th className="px-4 py-3 text-right">Actions</th></tr></thead><tbody>{rows.map((row) => <tr key={row.id} className="border-b border-[#f5f5f7] last:border-0"><td className="px-4 py-3"><p className="font-extrabold text-[#34353d]">{row.order_number}</p><p className="text-[10px] text-[#a1a2ab]">{new Date(row.created_at).toLocaleString()}</p></td><td className="px-4 py-3 text-[#5f6069]">{row.customer_name || "Walk-in"}</td><td className="px-4 py-3 text-[#5f6069]"><button type="button" onClick={() => editAddress(row)} className="block max-w-[220px] truncate text-left hover:text-[#6957f5]" title={row.delivery_address || "Set delivery address"}>{row.delivery_address || "Set address"}</button></td><td className="px-4 py-3 text-[#5f6069]">{row.driver_name || "—"}</td><td className="px-4 py-3 font-extrabold text-[#303139]">{formatCurrencyAmount(Number(row.total), baseCurrency)}</td><td className="px-4 py-3"><Badge tone={STATUS_TONES[row.delivery_status] || "neutral"}>{STATUS_LABELS[row.delivery_status] || row.delivery_status}</Badge></td><td className="px-4 py-3"><div className="flex items-center justify-end gap-1"><button type="button" onClick={() => assignDriver(row)} className="rounded-md px-2 py-1 text-[10px] font-bold text-[#6957f5] hover:bg-[#f0eefe]">{row.driver_name ? "Change driver" : "Assign"}</button>{row.delivery_status !== "delivered" && row.delivery_status !== "failed" && <button type="button" onClick={() => advance(row)} className="rounded-md px-2 py-1 text-[10px] font-bold text-[#2f7d4f] hover:bg-[#eafaf0]">{NEXT[row.delivery_status] === "delivered" ? "Mark delivered" : "Advance"}</button>}{row.delivery_status !== "delivered" && row.delivery_status !== "failed" && <button type="button" onClick={() => setFailed(row)} className="rounded-md px-2 py-1 text-[10px] font-bold text-[#c2564b] hover:bg-[#fff0ee]">Failed</button>}</div></td></tr>)}</tbody></table></div></div>}
  </div>;
}

export { LiveDeliveriesView };
