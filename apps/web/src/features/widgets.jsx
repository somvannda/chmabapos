import { AlertTriangle, ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";
import { Modal, Button } from "../components/ui";

function MetricCard({ label, value, change, direction, tone, icon: Icon, detail, onClick }) {
  const tones = { violet: "bg-[#f0efff] text-[#6957f5]", lime: "bg-[#eff9e5] text-[#67a53c]", peach: "bg-[#fff1e9] text-[#cb784d]", yellow: "bg-[#fff5dc] text-[#b18020]" };
  const trends = {
    up: { className: "text-[#67a53c]", TrendIcon: ArrowUpRight },
    down: { className: "text-[#c2564b]", TrendIcon: ArrowDownRight },
    alert: { className: "text-[#bd8624]", TrendIcon: AlertTriangle },
    flat: { className: "text-[#92939d]", TrendIcon: Minus },
  };
  const trend = trends[direction] || trends.flat;
  const TrendIcon = trend.TrendIcon;
  const body = <>
    <div className="flex items-start justify-between">
      <div>
        <p className="text-xs font-semibold text-[#858690] dark:text-[#a9aab3]">{label}</p>
        <p className="mt-2 text-[25px] font-extrabold tracking-[-.055em] text-[#202128] dark:text-[#e4e4e8]">{value}</p>
      </div>
      <div className={`flex h-9 w-9 items-center justify-center rounded-xl ${tones[tone]}`}><Icon size={17} /></div>
    </div>
    <div className="mt-3 flex items-center justify-between gap-2">
      <span className={`inline-flex items-center gap-1 text-[11px] font-bold ${trend.className}`}><TrendIcon size={13} />{change}</span>
      <span className="truncate text-[10px] text-[#a4a5ad]">{detail}</span>
    </div>
  </>;
  const className = "surface-shadow card-border block w-full rounded-2xl bg-white p-4 text-left dark:bg-[#1f2025] sm:p-5";
  return onClick ? <button type="button" onClick={onClick} className={`${className} transition hover:border-[#c9c4f4]`}>{body}</button> : <div className={className}>{body}</div>;
}

function SmallStat({ label, value, detail, icon: Icon, tone }) {  const tones = { violet: "bg-[#f0efff] text-[#6957f5]", green: "bg-[#eff9e5] text-[#67a53c]", yellow: "bg-[#fff5dc] text-[#b18020]" };  return <div className="card-border rounded-2xl bg-white p-4 dark:bg-[#1f2025]"><div className="flex items-center gap-3"><div className={`flex h-9 w-9 items-center justify-center rounded-xl ${tones[tone]}`}><Icon size={17} /></div><div><p className="text-[11px] font-semibold text-[#92939d]">{label}</p><p className="mt-0.5 text-xl font-extrabold tracking-[-.05em] dark:text-[#e4e4e8]">{value}</p></div></div><p className="mt-3 text-[10px] text-[#9a9ba4]">{detail}</p></div>;}

function ConfirmDialog({ open, title, message, confirmLabel = "Delete", onConfirm, onCancel, danger = true }) {  return <Modal open={open} onClose={onCancel} title={title} description="This action can't be undone." width="max-w-[420px]"><p className="rounded-xl bg-[#fafafd] p-4 text-sm leading-6 text-[#4d4e57]">{message}</p><div className="mt-5 flex gap-2"><Button variant="outline" className="flex-1" onClick={onCancel}>Cancel</Button><Button variant={danger ? "danger" : "primary"} className="flex-1" onClick={onConfirm}>{confirmLabel}</Button></div></Modal>;}

export {
  MetricCard,
  SmallStat,
  ConfirmDialog,
};
