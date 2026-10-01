import { useEffect, useState } from "react";
import { LayoutGrid, RefreshCw, Users } from "lucide-react";
import { Button, Badge, formatCurrencyAmount } from "../components/ui";
import { api } from "../api";
import { useCapabilities, allowsCapability } from "../lib/capabilities";

// Order the floor tiles turn through when tapped, so a host can move a table
// through service without a menu.
const NEXT_STATUS = { available: "occupied", occupied: "cleaning", cleaning: "available", reserved: "occupied" };
const STATUS_TONES = { available: "green", occupied: "violet", reserved: "yellow", cleaning: "neutral" };
const STATUS_LABELS = { available: "Available", occupied: "Occupied", reserved: "Reserved", cleaning: "Cleaning" };

function LiveDiningView({ token, storeId, notify, baseCurrency = "USD", onStartOrder }) {
  const [areas, setAreas] = useState([]);
  const [tables, setTables] = useState([]);
  const [tickets, setTickets] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const capabilities = useCapabilities(token, storeId);
  const enabled = allowsCapability(capabilities, "tables");

  const load = async () => {
    if (!storeId) return;
    setLoading(true);
    try {
      const [areaRows, tableRows, heldRows] = await Promise.all([api.diningAreas(token, storeId), api.diningTables(token, storeId), api.heldOrders(token, storeId)]);
      setAreas(Array.isArray(areaRows) ? areaRows : []);
      setTables(Array.isArray(tableRows) ? tableRows : []);
      // Map the open ticket (held order) to its table so a busy tile can show
      // what is on it without opening the register.
      const byTable = {};
      for (const held of Array.isArray(heldRows) ? heldRows : []) {
        if (held.table_id) byTable[held.table_id] = held;
      }
      setTickets(byTable);
      setError("");
    } catch (requestError) {
      setError(requestError.message || "Could not load the floor");
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { load(); }, [token, storeId]);

  const cycleStatus = async (table) => {
    const next = NEXT_STATUS[table.status] || "available";
    try {
      const updated = await api.updateDiningTable(token, storeId, table.id, { status: next });
      setTables((current) => current.map((row) => (row.id === updated.id ? updated : row)));
    } catch (requestError) {
      notify(requestError.message || "Could not update the table");
    }
  };

  const groups = [
    { id: "main", name: "Main", tables: tables.filter((table) => !table.area_id) },
    ...areas.map((area) => ({ id: area.id, name: area.name, tables: tables.filter((table) => table.area_id === area.id) })),
  ].filter((group) => group.tables.length > 0 || group.id !== "main");

  if (!enabled) {
    return <div className="mx-auto max-w-[1460px] p-5 lg:p-8"><div className="rounded-2xl border border-[#e9e9ef] bg-white p-12 text-center"><LayoutGrid size={22} className="mx-auto text-[#c9cad3]" /><p className="mt-3 text-sm font-bold text-[#565762]">The floor view is off</p><p className="mt-1 text-xs text-[#92939d]">Turn on the Tables pack in Settings &rarr; Feature packs, then add tables to use the dining floor.</p></div></div>;
  }

  return <div className="mx-auto max-w-[1460px] p-5 lg:p-8">
    <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
      <div>
        <h2 className="text-2xl font-extrabold tracking-[-.05em]">Floor</h2>
        <p className="mt-1 text-sm text-[#898a95]">Your dining room at a glance. Tap an available table to open an order; tap a busy table to move it through service.</p>
      </div>
      <Button variant="outline" onClick={load} disabled={loading}><RefreshCw size={15} /> Refresh</Button>
    </div>
    {error && <p className="mt-5 rounded-xl border border-[#ffd7d2] bg-[#fff5f3] px-3 py-2.5 text-xs text-[#c2564b]">{error}</p>}
    {loading && tables.length === 0 ? <p className="mt-7 rounded-2xl border border-[#e9e9ef] bg-white py-16 text-center text-xs text-[#92939d]">Loading the floor...</p>
      : tables.length === 0 ? <div className="mt-7 rounded-2xl border border-[#e9e9ef] bg-white py-16 text-center"><Users size={22} className="mx-auto text-[#c9cad3]" /><p className="mt-3 text-sm font-bold text-[#565762]">No tables yet</p><p className="mt-1 text-xs text-[#92939d]">Add areas and tables in Settings &rarr; Tables to see them here.</p></div>
      : <div className="mt-7 space-y-8">{groups.map((group) => <section key={group.id}><div className="flex items-center gap-2"><h3 className="text-sm font-extrabold tracking-[-.02em]">{group.name}</h3><span className="text-[11px] text-[#a1a2ab]">{group.tables.length} table{group.tables.length === 1 ? "" : "s"}</span></div><div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">{group.tables.map((table) => <button key={table.id} type="button" onClick={() => (table.status === "available" && onStartOrder ? onStartOrder(table.id) : cycleStatus(table))} className={`flex flex-col rounded-2xl border p-4 text-left transition ${table.status === "occupied" ? "border-[#c8c2f5] bg-[#faf9ff]" : "border-[#e9e9ef] bg-white hover:border-[#bdb9ee]"}`}><div className="flex items-start justify-between gap-2"><span className="text-sm font-extrabold text-[#34353d]">{table.name}</span><Badge tone={STATUS_TONES[table.status] || "neutral"}>{STATUS_LABELS[table.status] || table.status}</Badge></div><span className="mt-2 text-[11px] text-[#92939d]"><Users size={12} className="mr-1 inline" />{table.seats} seats</span>{tickets[table.id] && <span className="mt-1 text-[11px] font-semibold text-[#5b4bd6]">{tickets[table.id].item_count} item{tickets[table.id].item_count === 1 ? "" : "s"} · {formatCurrencyAmount(Number(tickets[table.id].total), baseCurrency)}</span>}</button>)}</div></section>)}</div>}
  </div>;
}

export { LiveDiningView };
