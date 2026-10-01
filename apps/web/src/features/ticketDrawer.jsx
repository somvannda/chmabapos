import { useState } from "react";
import { Button, Dropdown, Modal } from "../components/ui";
import { api } from "../api";

// Shared split / merge / serve drawer for an open ticket (a held order), used by
// both the Floor and the Kitchen board. `tickets` is the full list of open
// tickets (for the merge target), `tables` maps id -> name, `tableRows` is the
// destination-table list, and `reload` refreshes the parent after a change.
function TicketDrawer({ ticket, tickets = [], tables = {}, tableRows = [], token, storeId, notify, onClose, reload }) {
  const [splitQty, setSplitQty] = useState({});
  const [splitTable, setSplitTable] = useState("");
  const [mergeInto, setMergeInto] = useState("");
  const [busy, setBusy] = useState(false);

  const ticketName = (row) => (row.table_id ? (tables[row.table_id] || "Table") : (row.label || "Held order"));
  const setQty = (productId, value) => setSplitQty((current) => ({ ...current, [productId]: value }));
  const selectedCount = ticket.items.filter((item) => Number(splitQty[item.product_id]) > 0).length;
  const mergeTargets = tickets.filter((row) => row.id !== ticket.id);

  const settle = async (work, message) => {
    setBusy(true);
    try {
      await work();
      await reload();
      onClose();
      notify?.(message);
    } catch (requestError) {
      notify?.(requestError.message || "Could not update the ticket");
    } finally {
      setBusy(false);
    }
  };

  const doSplit = () => {
    const picked = ticket.items
      .filter((item) => Number(splitQty[item.product_id]) > 0)
      .map((item) => ({ product_id: item.product_id, quantity: Number(splitQty[item.product_id]) }));
    if (!picked.length) return undefined;
    return settle(() => api.splitHeldOrder(token, storeId, ticket.id, { items: picked, table_id: splitTable || null }), "Ticket split");
  };
  const doMerge = () => {
    if (!mergeInto) return undefined;
    return settle(() => api.mergeHeldOrder(token, storeId, ticket.id, { into_id: mergeInto }), "Tickets merged");
  };
  const doSetStatus = (status) => settle(() => api.updateHeldOrder(token, storeId, ticket.id, { status }), status === "served" ? "Ticket marked served" : "Ticket reopened");

  return <Modal open onClose={onClose} title={ticketName(ticket)} description="Split this ticket, or merge it into another." width="max-w-[560px]" dismissOnBackdrop={false}>
    <div className="space-y-2">{ticket.items.map((item) => <div key={item.product_id} className="flex items-center justify-between gap-3 rounded-lg border border-[#e9e9ef] px-3 py-2 text-xs"><span className="min-w-0 flex-1 truncate font-semibold text-[#4d4e57]">{item.product_name}</span><span className="shrink-0 text-[#92939d]">&times;{item.quantity}</span><input type="number" min="0" max={item.quantity} value={splitQty[item.product_id] ?? ""} onChange={(event) => setQty(item.product_id, event.target.value)} placeholder="0" className="h-9 w-16 shrink-0 rounded-lg border border-[#dfdfe8] px-2 text-xs outline-none focus:border-[#887bf3]" /></div>)}</div>
    <div className="mt-4 flex items-center gap-2 border-t border-[#f0f0f3] pt-4"><div className="min-w-0 flex-1"><Dropdown value={splitTable} onChange={setSplitTable} options={[{ value: "", label: "Split to no table" }, ...tableRows.map((table) => ({ value: String(table.id), label: table.name }))]} /></div><Button onClick={doSplit} disabled={busy || selectedCount === 0}>Split {selectedCount > 0 ? `(${selectedCount})` : ""}</Button></div>
    <div className="mt-4 flex items-center gap-2 border-t border-[#f0f0f3] pt-4"><div className="min-w-0 flex-1"><Dropdown value={mergeInto} onChange={setMergeInto} options={mergeTargets.map((row) => ({ value: String(row.id), label: `${ticketName(row)} · ${row.item_count} item(s)` }))} placeholder={mergeTargets.length ? "Merge into..." : "No other tickets"} /></div><Button variant="outline" onClick={doMerge} disabled={busy || !mergeInto}>Merge</Button></div>
    <div className="mt-4 flex items-center justify-end border-t border-[#f0f0f3] pt-4">{ticket.status === "served" ? <Button variant="outline" onClick={() => doSetStatus("open")} disabled={busy}>Reopen ticket</Button> : <Button variant="outline" onClick={() => doSetStatus("served")} disabled={busy}>Mark served</Button>}</div>
  </Modal>;
}

export { TicketDrawer };
