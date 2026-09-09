import { AlertTriangle, ArrowUpRight } from "lucide-react";
import { Modal, Button } from "../components/ui";

function MetricCard({ label, value, change, direction, tone, icon: Icon, detail }) {  const tones = { violet: "bg-[#f0efff] text-[#6957f5]", lime: "bg-[#eff9e5] text-[#67a53c]", peach: "bg-[#fff1e9] text-[#cb784d]", yellow: "bg-[#fff5dc] text-[#b18020]" };  return <div className="surface-shadow card-border rounded-2xl bg-white p-4 sm:p-5"><div className="flex items-start justify-between"><div><p className="text-xs font-semibold text-[#858690]">{label}</p><p className="mt-2 text-[25px] font-extrabold tracking-[-.055em] text-[#202128]">{value}</p></div><div className={`flex h-9 w-9 items-center justify-center rounded-xl ${tones[tone]}`}><Icon size={17} /></div></div><div className="mt-3 flex items-center justify-between gap-2"><span className={`inline-flex items-center gap-1 text-[11px] font-bold ${direction === "alert" ? "text-[#bd8624]" : "text-[#67a53c]"}`}>{direction === "up" ? <ArrowUpRight size={13} /> : <AlertTriangle size={12} />}{change}</span><span className="truncate text-[10px] text-[#a4a5ad]">{detail}</span></div></div>;}

function SmallStat({ label, value, detail, icon: Icon, tone }) {  const tones = { violet: "bg-[#f0efff] text-[#6957f5]", green: "bg-[#eff9e5] text-[#67a53c]", yellow: "bg-[#fff5dc] text-[#b18020]" };  return <div className="card-border rounded-2xl bg-white p-4"><div className="flex items-center gap-3"><div className={`flex h-9 w-9 items-center justify-center rounded-xl ${tones[tone]}`}><Icon size={17} /></div><div><p className="text-[11px] font-semibold text-[#92939d]">{label}</p><p className="mt-0.5 text-xl font-extrabold tracking-[-.05em]">{value}</p></div></div><p className="mt-3 text-[10px] text-[#9a9ba4]">{detail}</p></div>;}

function ConfirmDialog({ open, title, message, confirmLabel = "Delete", onConfirm, onCancel, danger = true }) {  return <Modal open={open} onClose={onCancel} title={title} description="This action can't be undone." width="max-w-[420px]"><p className="rounded-xl bg-[#fafafd] p-4 text-sm leading-6 text-[#4d4e57]">{message}</p><div className="mt-5 flex gap-2"><Button variant="outline" className="flex-1" onClick={onCancel}>Cancel</Button><Button variant={danger ? "danger" : "primary"} className="flex-1" onClick={onConfirm}>{confirmLabel}</Button></div></Modal>;}

export {
  MetricCard,
  SmallStat,
  ConfirmDialog,
};
