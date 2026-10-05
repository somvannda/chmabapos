import { useEffect, useState } from "react";
import { CalendarDays, Check, LayoutGrid, Plus, RefreshCw, Trash2, Users, X } from "lucide-react";
import { Button, Badge, formatCurrencyAmount, Modal, Field } from "../components/ui";
import { api } from "../api";
import { formatTime } from "../lib/dateFormat";
import { useCapabilities, allowsCapability } from "../lib/capabilities";
import { TicketDrawer } from "./ticketDrawer";

// Order the floor tiles turn through when tapped, so a host can move a table
// through service without a menu.
const NEXT_STATUS = { available: "occupied", occupied: "cleaning", cleaning: "available", reserved: "occupied" };
const STATUS_TONES = { available: "green", occupied: "violet", reserved: "yellow", cleaning: "neutral" };
const STATUS_LABELS = { available: "Available", occupied: "Occupied", reserved: "Reserved", cleaning: "Cleaning" };

function LiveDiningView({ token, storeId, notify, baseCurrency = "USD", onStartOrder }) {
  const [areas, setAreas] = useState([]);
  const [tables, setTables] = useState([]);
  const [tickets, setTickets] = useState({});
  const [ticketList, setTicketList] = useState([]);
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const capabilities = useCapabilities(token, storeId);
  const enabled = allowsCapability(capabilities, "tables");
  const [reservations, setReservations] = useState([]);
  const [resForm, setResForm] = useState(null);
  const [resBusy, setResBusy] = useState(false);

  const load = async () => {
    if (!storeId || capabilities === null || !enabled) return;
    setLoading(true);
    try {
      const [areaRows, tableRows, heldRows, reservationRows] = await Promise.all([api.diningAreas(token, storeId), api.diningTables(token, storeId), api.heldOrders(token, storeId), api.diningReservations(token, storeId)]);
      setAreas(Array.isArray(areaRows) ? areaRows : []);
      setTables(Array.isArray(tableRows) ? tableRows : []);
      setReservations(Array.isArray(reservationRows) ? reservationRows : []);
      // Keep the open tickets both as a per-table map (for the tile summary) and
      // as a list (for the split/merge drawer's merge targets).
      const held = Array.isArray(heldRows) ? heldRows : [];
      setTicketList(held);
      const byTable = {};
      for (const ticket of held) {
        if (ticket.table_id) byTable[ticket.table_id] = ticket;
      }
      setTickets(byTable);
      setError("");
    } catch (requestError) {
      setError(requestError.message || "Could not load the floor");
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { load(); }, [token, storeId, capabilities]);
  // Refresh on its own so the floor reflects tickets opened elsewhere (the
  // register, another host) without a manual refresh — matching the Kitchen.
  useEffect(() => {
    if (!enabled) return undefined;
    const timer = window.setInterval(load, 30000);
    return () => window.clearInterval(timer);
  }, [enabled, token, storeId]);

  const cycleStatus = async (table) => {
    const next = NEXT_STATUS[table.status] || "available";
    try {
      const updated = await api.updateDiningTable(token, storeId, table.id, { status: next });
      setTables((current) => current.map((row) => (row.id === updated.id ? updated : row)));
    } catch (requestError) {
      notify(requestError.message || "Could not update the table");
    }
  };

  const setReservationStatus = async (row, status) => {
    try {
      const updated = await api.updateReservation(token, storeId, row.id, { status });
      setReservations((current) => current.map((entry) => (entry.id === updated.id ? updated : entry)));
      await load();
    } catch (requestError) {
      notify(requestError.message || "Could not update the reservation");
    }
  };
  const removeReservation = async (row) => {
    try {
      await api.deleteReservation(token, storeId, row.id);
      setReservations((current) => current.filter((entry) => entry.id !== row.id));
    } catch (requestError) {
      notify(requestError.message || "Could not delete the reservation");
    }
  };
  const saveReservation = async () => {
    if (!resForm || !resForm.customer_name.trim()) return;
    setResBusy(true);
    try {
      const body = { kind: resForm.kind, customer_name: resForm.customer_name.trim(), phone: resForm.phone.trim() || null, party_size: Number(resForm.party_size) || 2, table_id: resForm.table_id || null, notes: resForm.notes.trim() || null };
      if (resForm.kind === "reservation" && resForm.time) body.reserved_at = new Date(resForm.time).toISOString();
      const kind = resForm.kind;
      await api.createReservation(token, storeId, body);
      setResForm(null);
      await load();
      notify(kind === "waitlist" ? "Waitlist entry added" : "Reservation added");
    } catch (requestError) {
      notify(requestError.message || "Could not save the reservation");
    } finally {
      setResBusy(false);
    }
  };

  const tableNameById = tables.reduce((acc, table) => { acc[table.id] = table.name; return acc; }, {});

  // Available table -> start an order; a table with an open ticket -> open the
  // ticket drawer (split/merge/serve); otherwise step the table through service.
  const handleTile = (table) => {
    if (table.status === "available" && onStartOrder) { onStartOrder(table.id); return; }
    const ticket = tickets[table.id];
    if (ticket) { setSelected(ticket); return; }
    cycleStatus(table);
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
        <p className="mt-1 text-sm text-[#898a95]">Your dining room at a glance. Tap an available table to open an order; tap a busy table to view, split or merge its ticket.</p>
      </div>
      <Button variant="outline" onClick={load} disabled={loading}><RefreshCw size={15} /> Refresh</Button>
    </div>
    {error && <p className="mt-5 rounded-xl border border-[#ffd7d2] bg-[#fff5f3] px-3 py-2.5 text-xs text-[#c2564b]">{error}</p>}
    {loading && tables.length === 0 ? <p className="mt-7 rounded-2xl border border-[#e9e9ef] bg-white py-16 text-center text-xs text-[#92939d]">Loading the floor...</p>
      : tables.length === 0 ? <div className="mt-7 rounded-2xl border border-[#e9e9ef] bg-white py-16 text-center"><Users size={22} className="mx-auto text-[#c9cad3]" /><p className="mt-3 text-sm font-bold text-[#565762]">No tables yet</p><p className="mt-1 text-xs text-[#92939d]">Add areas and tables in Settings &rarr; Tables to see them here.</p></div>
      : <div className="mt-7 space-y-8">{groups.map((group) => <section key={group.id}><div className="flex items-center gap-2"><h3 className="text-sm font-extrabold tracking-[-.02em]">{group.name}</h3><span className="text-[11px] text-[#a1a2ab]">{group.tables.length} table{group.tables.length === 1 ? "" : "s"}</span></div><div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">{group.tables.map((table) => <button key={table.id} type="button" onClick={() => handleTile(table)} className={`flex flex-col rounded-2xl border p-4 text-left transition ${table.status === "occupied" ? "border-[#c8c2f5] bg-[#faf9ff]" : "border-[#e9e9ef] bg-white hover:border-[#bdb9ee]"}`}><div className="flex items-start justify-between gap-2"><span className="text-sm font-extrabold text-[#34353d]">{table.name}</span><span className="flex shrink-0 items-center gap-1">{tickets[table.id]?.status === "served" && <Badge tone="green">Served</Badge>}{tickets[table.id]?.source && tickets[table.id].source !== "pos" && <Badge tone="blue">{tickets[table.id].source === "qr" ? "QR" : "Online"}</Badge>}<Badge tone={STATUS_TONES[table.status] || "neutral"}>{STATUS_LABELS[table.status] || table.status}</Badge></span></div><span className="mt-2 text-[11px] text-[#92939d]"><Users size={12} className="mr-1 inline" />{table.seats} seats</span>{tickets[table.id] && <span className="mt-1 text-[11px] font-semibold text-[#5b4bd6]">{tickets[table.id].item_count} item{tickets[table.id].item_count === 1 ? "" : "s"} · {formatCurrencyAmount(Number(tickets[table.id].total), baseCurrency)}</span>}</button>)}</div></section>)}</div>}

    <section className="mt-10">
      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
        <div>
          <h3 className="text-sm font-extrabold tracking-[-.02em]">Reservations &amp; waitlist</h3>
          <p className="mt-1 text-[11px] text-[#999aa4]">Bookings and walk-ins waiting for a table.</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => setResForm({ kind: "waitlist", customer_name: "", phone: "", party_size: "2", time: "", table_id: "", notes: "" })}><Plus size={14} /> Waitlist</Button>
          <Button size="sm" onClick={() => setResForm({ kind: "reservation", customer_name: "", phone: "", party_size: "2", time: "", table_id: "", notes: "" })}><Plus size={14} /> New reservation</Button>
        </div>
      </div>
      {reservations.length === 0
        ? <p className="mt-4 rounded-2xl border border-[#e9e9ef] bg-white py-12 text-center text-xs text-[#92939d]">Nothing booked or waiting right now.</p>
        : <div className="mt-4 overflow-hidden rounded-2xl border border-[#e9e9ef] bg-white"><div className="app-scrollbar overflow-x-auto"><table className="mobile-table w-full min-w-[720px] border-collapse text-left text-xs"><thead><tr className="border-b border-[#f0f0f3] bg-[#fcfcfd] text-[10px] font-bold uppercase tracking-wide text-[#a1a2ab]"><th className="px-4 py-3">Guest</th><th className="px-4 py-3">Type</th><th className="px-4 py-3">Party</th><th className="px-4 py-3">Time</th><th className="px-4 py-3">Table</th><th className="px-4 py-3">Status</th><th className="px-4 py-3 text-right">Actions</th></tr></thead><tbody>{reservations.map((row) => <tr key={row.id} className="border-b border-[#f5f5f7] last:border-0"><td className="px-4 py-3"><p className="font-extrabold text-[#34353d]">{row.customer_name}</p>{row.phone && <p className="text-[10px] text-[#a1a2ab]">{row.phone}</p>}</td><td className="px-4 py-3"><Badge tone={row.kind === "waitlist" ? "yellow" : "violet"}>{row.kind === "waitlist" ? "Waitlist" : "Booking"}</Badge></td><td className="px-4 py-3 text-[#5f6069]">{row.party_size}</td><td className="px-4 py-3 text-[#5f6069]">{row.reserved_at ? formatTime(row.reserved_at) : "—"}</td><td className="px-4 py-3 text-[#5f6069]">{row.table_name || "—"}</td><td className="px-4 py-3"><Badge tone={row.status === "seated" ? "green" : row.status === "cancelled" || row.status === "no_show" ? "neutral" : "violet"}>{row.status.replace("_", " ")}</Badge></td><td className="px-4 py-3"><div className="flex items-center justify-end gap-1">{row.status !== "seated" && row.status !== "cancelled" && <button type="button" onClick={() => setReservationStatus(row, "seated")} className="rounded-md px-2 py-1 text-[10px] font-bold text-[#2f7d4f] hover:bg-[#eafaf0]">Seat</button>}{row.status !== "cancelled" && <button type="button" onClick={() => setReservationStatus(row, "cancelled")} className="rounded-md px-2 py-1 text-[10px] font-bold text-[#9e7628] hover:bg-[#fff7e6]">Cancel</button>}<button type="button" onClick={() => removeReservation(row)} className="rounded-md px-2 py-1 text-[10px] font-bold text-[#c2564b] hover:bg-[#fff0ee]">Delete</button></div></td></tr>)}</tbody></table></div></div>}
    </section>

    {resForm && <Modal open onClose={() => setResForm(null)} title={resForm.kind === "waitlist" ? "Add to waitlist" : "New reservation"} description={resForm.kind === "waitlist" ? "A walk-in waiting for a table." : "Book a table for a future time."} width="max-w-[480px]" dismissOnBackdrop={false}><div className="space-y-3"><Field label="Guest name" value={resForm.customer_name} onChange={(event) => setResForm({ ...resForm, customer_name: event.target.value })} placeholder="e.g. Dara" /><div className="grid grid-cols-2 gap-3"><Field label="Phone" value={resForm.phone} onChange={(event) => setResForm({ ...resForm, phone: event.target.value })} placeholder="+855 ..." /><Field label="Party size" type="number" min="1" value={resForm.party_size} onChange={(event) => setResForm({ ...resForm, party_size: event.target.value })} /></div>{resForm.kind === "reservation" && <label className="block"><span className="mb-1.5 block text-xs font-semibold text-[#4f5059]">Time</span><input type="datetime-local" value={resForm.time} onChange={(event) => setResForm({ ...resForm, time: event.target.value })} className="h-11 w-full rounded-xl border border-[#dfdfe8] bg-white px-3.5 text-sm outline-none focus:border-[#887bf3]" /></label>}<label className="block"><span className="mb-1.5 block text-xs font-semibold text-[#4f5059]">Table (optional)</span><select value={resForm.table_id} onChange={(event) => setResForm({ ...resForm, table_id: event.target.value })} className="h-11 w-full rounded-xl border border-[#dfdfe8] px-2 text-sm outline-none focus:border-[#887bf3]"><option value="">No table</option>{tables.map((table) => <option key={table.id} value={String(table.id)}>{table.name} · {table.seats} seats</option>)}</select></label><label className="block"><span className="mb-1.5 block text-xs font-semibold text-[#4f5059]">Notes</span><input value={resForm.notes} onChange={(event) => setResForm({ ...resForm, notes: event.target.value })} placeholder="Optional" className="h-11 w-full rounded-xl border border-[#dfdfe8] px-3.5 text-sm outline-none focus:border-[#887bf3]" /></label></div><div className="mt-5 flex gap-2"><Button variant="outline" className="flex-1" onClick={() => setResForm(null)}>Cancel</Button><Button className="flex-1" onClick={saveReservation} disabled={resBusy || !resForm.customer_name.trim()}>{resBusy ? "Saving..." : resForm.kind === "waitlist" ? "Add to waitlist" : "Save reservation"}</Button></div></Modal>}

    {selected && <TicketDrawer ticket={selected} tickets={ticketList} tables={tableNameById} tableRows={tables} token={token} storeId={storeId} notify={notify} onClose={() => setSelected(null)} reload={load} />}
  </div>;
}

export { LiveDiningView };
