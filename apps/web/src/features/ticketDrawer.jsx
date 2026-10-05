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
  const [transferTable, setTransferTable] = useState("");
  const [busy, setBusy] = useState(false);
  const [items, setItems] = useState(ticket.items);
  const COURSES = [{ value: "starters", label: "Starters" }, { value: "mains", label: "Mains" }, { value: "dessert", label: "Dessert" }, { value: "drinks", label: "Drinks" }];

  const saveLine = async (lineKey, seat, course) => {
    setBusy(true);
    try {
      const updated = await api.updateHeldOrderLine(token, storeId, ticket.id, { line_key: lineKey, seat: seat === "" || seat == null ? null : Number(seat), course: course || null });
      setItems(updated.items);
      notify?.("Line updated");
    } catch (requestError) {
      notify?.(requestError.message || "Could not update the line");
    } finally {
      setBusy(false);
    }
  };
  // Fire every unfired line in a course (or all unfired lines) and refresh in place.
  const fire = async (course) => {
    setBusy(true);
    try {
      const updated = await api.fireHeldOrder(token, storeId, ticket.id, course ? { course } : {});
      setItems(updated.items);
      notify?.(course ? `Fired ${course}` : "Fired all");
    } catch (requestError) {
      notify?.(requestError.message || "Could not fire");
    } finally {
      setBusy(false);
    }
  };
  const unfiredCourses = [...new Set(items.filter((item) => !item.fired_at && item.course).map((item) => item.course))];

  const ticketName = (row) => (row.table_id ? (tables[row.table_id] || "Table") : (row.label || "Held order"));
  const setQty = (lineKey, value) => setSplitQty((current) => ({ ...current, [lineKey]: value }));
  const selectedCount = items.filter((item) => Number(splitQty[item.line_key]) > 0).length;
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
    // A line is identified by product + variant + modifiers + seat, so send the
    // full tuple: sending the product alone cannot match a variant/modifier line.
    const picked = items
      .filter((item) => Number(splitQty[item.line_key]) > 0)
      .map((item) => ({
        product_id: item.product_id,
        variant_id: item.variant_id || null,
        quantity: Number(splitQty[item.line_key]),
        modifiers: item.modifiers || [],
        seat: item.seat ?? null,
      }));
    if (!picked.length) return undefined;
    return settle(() => api.splitHeldOrder(token, storeId, ticket.id, { items: picked, table_id: splitTable || null }), "Ticket split");
  };
  const doMerge = () => {
    if (!mergeInto) return undefined;
    return settle(() => api.mergeHeldOrder(token, storeId, ticket.id, { into_id: mergeInto }), "Tickets merged");
  };
  const doTransfer = () => {
    if (!transferTable) return undefined;
    return settle(() => api.transferHeldOrder(token, storeId, ticket.id, { table_id: transferTable }), "Ticket moved");
  };
  const doSetStatus = (status) => settle(() => api.updateHeldOrder(token, storeId, ticket.id, { status }), status === "served" ? "Ticket marked served" : "Ticket reopened");

  return <Modal open onClose={onClose} title={ticketName(ticket)} description="Split, move or merge this ticket." width="max-w-[560px]" dismissOnBackdrop={false}>
    <div className="space-y-2">{items.map((item) => <div key={item.line_key} className="flex items-center justify-between gap-3 rounded-lg border border-[#e9e9ef] px-3 py-2 text-xs"><span className="min-w-0 flex-1 truncate font-semibold text-[#4d4e57]">{item.product_name}{item.variant_name ? ` · ${item.variant_name}` : ""}{Array.isArray(item.modifiers) && item.modifiers.length ? ` · ${item.modifiers.map((modifier) => modifier.name).join(", ")}` : ""}</span><span className="shrink-0 text-[#92939d]">&times;{item.quantity}</span><input type="number" min="0" max={item.quantity} value={splitQty[item.line_key] ?? ""} onChange={(event) => setQty(item.line_key, event.target.value)} placeholder="0" className="h-9 w-16 shrink-0 rounded-lg border border-[#dfdfe8] px-2 text-xs outline-none focus:border-[#887bf3]" /></div>)}</div>
    <div className="mt-4 border-t border-[#f0f0f3] pt-4">
      <div className="mb-2 flex items-center justify-between"><p className="text-xs font-extrabold text-[#2f2f38]">Seat &amp; course</p><Button variant="outline" onClick={() => fire(null)} disabled={busy || items.every((item) => item.fired_at)}>Fire all</Button></div>
      <div className="space-y-2">{items.map((item) => <div key={`sc-${item.line_key}`} className="grid grid-cols-[minmax(0,1fr)_70px_120px_auto] items-center gap-2 rounded-lg bg-[#fafafd] px-3 py-2 text-xs"><span className="min-w-0 truncate font-semibold text-[#4d4e57]">{item.product_name}</span><input type="number" min="1" defaultValue={item.seat ?? ""} placeholder="Seat" onBlur={(event) => saveLine(item.line_key, event.target.value, item.course)} className="h-8 w-full rounded-lg border border-[#dfdfe8] px-2 text-xs outline-none focus:border-[#887bf3]" /><select value={item.course || ""} onChange={(event) => saveLine(item.line_key, item.seat, event.target.value)} className="h-8 w-full rounded-lg border border-[#dfdfe8] px-2 text-xs outline-none focus:border-[#887bf3]"><option value="">No course</option>{COURSES.map((course) => <option key={course.value} value={course.value}>{course.label}</option>)}</select><span className="w-14 text-right text-[10px] font-bold text-[#92939d]">{item.fired_at ? "Fired" : "Unfired"}</span></div>)}</div>
      {unfiredCourses.length > 0 && <div className="mt-2 flex flex-wrap gap-2">{unfiredCourses.map((course) => <Button key={course} variant="outline" onClick={() => fire(course)} disabled={busy}>Fire {course}</Button>)}</div>}
    </div>
    <div className="mt-4 flex items-center gap-2 border-t border-[#f0f0f3] pt-4"><div className="min-w-0 flex-1"><Dropdown value={splitTable} onChange={setSplitTable} options={[{ value: "", label: "Split to no table" }, ...tableRows.map((table) => ({ value: String(table.id), label: table.name }))]} /></div><Button onClick={doSplit} disabled={busy || selectedCount === 0}>Split {selectedCount > 0 ? `(${selectedCount})` : ""}</Button></div>
    <div className="mt-4 flex items-center gap-2 border-t border-[#f0f0f3] pt-4"><div className="min-w-0 flex-1"><Dropdown value={mergeInto} onChange={setMergeInto} options={mergeTargets.map((row) => ({ value: String(row.id), label: `${ticketName(row)} · ${row.item_count} item(s)` }))} placeholder={mergeTargets.length ? "Merge into..." : "No other tickets"} /></div><Button variant="outline" onClick={doMerge} disabled={busy || !mergeInto}>Merge</Button></div>
    <div className="mt-4 flex items-center gap-2 border-t border-[#f0f0f3] pt-4"><div className="min-w-0 flex-1"><Dropdown value={transferTable} onChange={setTransferTable} options={tableRows.filter((table) => table.id !== ticket.table_id).map((table) => ({ value: String(table.id), label: table.name }))} placeholder={tableRows.filter((table) => table.id !== ticket.table_id).length ? "Move to table..." : "No other tables"} /></div><Button variant="outline" onClick={doTransfer} disabled={busy || !transferTable}>Move</Button></div>
    <div className="mt-4 flex items-center justify-end border-t border-[#f0f0f3] pt-4">{ticket.status === "served" ? <Button variant="outline" onClick={() => doSetStatus("open")} disabled={busy}>Reopen ticket</Button> : <Button variant="outline" onClick={() => doSetStatus("served")} disabled={busy}>Mark served</Button>}</div>
  </Modal>;
}

export { TicketDrawer };
