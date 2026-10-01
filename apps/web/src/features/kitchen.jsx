import { useEffect, useState } from "react";
import { ChefHat, RefreshCw } from "lucide-react";
import { Button, Badge } from "../components/ui";
import { api } from "../api";
import { useCapabilities, allowsCapability } from "../lib/capabilities";

// Human-friendly age of an open ticket, so the kitchen can spot the oldest
// orders. Re-evaluated on each refresh.
function ageLabel(createdAt) {
  const created = new Date(createdAt).getTime();
  if (!created) return "";
  const minutes = Math.max(0, Math.floor((Date.now() - created) / 60000));
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min`;
  return `${Math.floor(minutes / 60)}h ${minutes % 60}m`;
}

function LiveKitchenView({ token, storeId }) {
  const [tickets, setTickets] = useState([]);
  const [tables, setTables] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const capabilities = useCapabilities(token, storeId);
  const enabled = allowsCapability(capabilities, "tables");

  const load = async () => {
    if (!storeId) return;
    setLoading(true);
    try {
      const [heldRows, tableRows] = await Promise.all([api.heldOrders(token, storeId), api.diningTables(token, storeId)]);
      setTickets(Array.isArray(heldRows) ? heldRows : []);
      const byId = {};
      for (const table of Array.isArray(tableRows) ? tableRows : []) byId[table.id] = table.name;
      setTables(byId);
      setError("");
    } catch (requestError) {
      setError(requestError.message || "Could not load the kitchen board");
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { load(); }, [token, storeId]);
  // Refresh on its own so the kitchen sees new tickets without touching the screen.
  useEffect(() => {
    if (!enabled) return undefined;
    const timer = window.setInterval(load, 30000);
    return () => window.clearInterval(timer);
  }, [enabled, token, storeId]);

  if (!enabled) {
    return <div className="mx-auto max-w-[1460px] p-5 lg:p-8"><div className="rounded-2xl border border-[#e9e9ef] bg-white p-12 text-center"><ChefHat size={22} className="mx-auto text-[#c9cad3]" /><p className="mt-3 text-sm font-bold text-[#565762]">The kitchen display is off</p><p className="mt-1 text-xs text-[#92939d]">Turn on the Tables pack in Settings &rarr; Feature packs to use it.</p></div></div>;
  }

  return <div className="mx-auto max-w-[1460px] p-5 lg:p-8">
    <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
      <div>
        <h2 className="text-2xl font-extrabold tracking-[-.05em]">Kitchen</h2>
        <p className="mt-1 text-sm text-[#898a95]">Open tickets, newest first. Refreshes on its own every 30 seconds.</p>
      </div>
      <Button variant="outline" onClick={load} disabled={loading}><RefreshCw size={15} /> Refresh</Button>
    </div>
    {error && <p className="mt-5 rounded-xl border border-[#ffd7d2] bg-[#fff5f3] px-3 py-2.5 text-xs text-[#c2564b]">{error}</p>}
    {tickets.length === 0
      ? <div className="mt-7 rounded-2xl border border-[#e9e9ef] bg-white py-16 text-center"><ChefHat size={22} className="mx-auto text-[#c9cad3]" /><p className="mt-3 text-sm font-bold text-[#565762]">No open tickets</p><p className="mt-1 text-xs text-[#92939d]">Open a table from the Floor or hold an order to send it here.</p></div>
      : <div className="mt-7 grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">{tickets.map((ticket) => <div key={ticket.id} className="flex flex-col rounded-2xl border border-[#e9e9ef] bg-white p-4"><div className="flex items-start justify-between gap-2"><span className="text-sm font-extrabold text-[#34353d]">{ticket.table_id ? (tables[ticket.table_id] || "Table") : (ticket.label || "Held order")}</span><Badge tone="violet">{ageLabel(ticket.created_at)}</Badge></div><div className="mt-3 space-y-1.5 border-t border-[#f0f0f3] pt-3">{ticket.items.map((item, index) => <div key={`${ticket.id}-${index}`} className="flex items-baseline justify-between gap-3 text-xs"><span className="min-w-0 truncate font-semibold text-[#4d4e57]">{item.product_name}</span><span className="shrink-0 font-extrabold text-[#303139]">&times;{item.quantity}</span></div>)}</div><div className="mt-3 border-t border-[#f0f0f3] pt-2 text-[11px] text-[#92939d]">{ticket.item_count} item{ticket.item_count === 1 ? "" : "s"}</div></div>)}</div>}
  </div>;
}

export { LiveKitchenView };
