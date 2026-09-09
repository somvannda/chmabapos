import { useState, useEffect } from "react";
import { AlertTriangle, Check, CircleDollarSign, CreditCard, ExternalLink, Plus, QrCode, Receipt, ShieldCheck, Store, ToggleLeft, ToggleRight, Trash2, TrendingUp, UserPlus, Users, WalletCards, X } from "lucide-react";
import { Badge, Button, formatCurrencyAmount, Modal, ProductMark, IconButton, Field, Dropdown } from "../components/ui";
import { QRCodeSVG } from "qrcode.react";
import { MetricCard, SmallStat, ConfirmDialog } from "./widgets";
import { api } from "../api";

function PlanScheduleModal({ plan, currentPlan, subscription, stores, members, renewLabel, onClose, onConfirm, saving }) {
  const isFree = plan.code === "free";
  const ends = subscription?.ends_at ? new Date(subscription.ends_at).toLocaleDateString() : "the end of your current period";
  const activeStores = (stores || []).filter((store) => store.is_active !== false);
  const staff = (members || []).filter((member) => member.status === "active" && member.role !== "owner");
  const owners = (members || []).filter((member) => member.status === "active" && member.role === "owner").length;
  const targetStoreLimit = isFree ? 1 : Number(plan.max_stores || 0);
  const targetMemberLimit = Number(plan.max_members || 0);
  const staffRoom = Math.max(targetMemberLimit - owners, 0);
  const needsStorePick = activeStores.length > (isFree ? 1 : targetStoreLimit);
  const needsMemberPick = !isFree && staff.length > staffRoom;
  const [choose, setChoose] = useState(false);
  const [keepStoreIds, setKeepStoreIds] = useState(() => (activeStores.length ? [activeStores[0].id] : []));
  const [keepMemberIds, setKeepMemberIds] = useState(() => (staff.length ? [staff[0].id] : []));
  const toggleStore = (id) => setKeepStoreIds((cur) => (cur.includes(id) ? cur.filter((x) => x !== id) : cur.length < targetStoreLimit ? [...cur, id] : cur));
  const toggleMember = (id) => setKeepMemberIds((cur) => (cur.includes(id) ? cur.filter((x) => x !== id) : cur.length < staffRoom ? [...cur, id] : cur));
  const currentName = currentPlan?.name || subscription?.plan_code || "your";
  const confirm = () => {
    const keep_store_ids = choose ? keepStoreIds : [];
    const keep_member_ids = choose ? keepMemberIds : [];
    onConfirm({ plan_code: plan.code, keep_store_ids, keep_member_ids });
  };
  return (
    <Modal open onClose={onClose} title={isFree ? `Cancel ${currentName} at period end` : `Switch to ${plan.name} at period end`} description="Plans are prepaid and non-refundable." width="max-w-[560px]">
      <div className="space-y-4">
        <div className="rounded-2xl border border-[#ffe1b8] bg-[#fff9f0] p-4 text-xs leading-5 text-[#7a4d12]">
          <strong className="font-extrabold">No refunds.</strong> KHQR payments are non-refundable. Your {currentName} plan stays fully usable until {ends}; the change applies then — nothing is charged today.
        </div>
        {isFree ? (
          <p className="text-xs leading-5 text-[#747580]">
            When your {currentName} plan ends on {ends}, your workspace moves to the <strong>Free</strong> plan (1 store, data kept). You can change your mind or renew anytime before then.
          </p>
        ) : (
          <p className="text-xs leading-5 text-[#747580]">
            When your {currentName} plan ends on {ends}, you will renew on the <strong>{plan.name}</strong> plan for {renewLabel}. You can change your mind or renew {currentName} anytime before then.
          </p>
        )}
        {(needsStorePick || needsMemberPick) && (
          <div className="rounded-xl border border-[#e9e9ef] bg-[#fafafd] p-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-xs font-extrabold">Keep stores &amp; team</p>
                <p className="mt-1 text-[11px] leading-4 text-[#92939d]">
                  {choose ? "Pick exactly what stays active after the change." : "We will keep the most recently used automatically — you can adjust afterwards."}
                </p>
              </div>
              <Button variant={choose ? "primary" : "outline"} size="sm" onClick={() => setChoose(!choose)}>{choose ? "Keep automatic" : "I will choose"}</Button>
            </div>
            {choose && needsStorePick && (
              <div className="mt-3">
                <p className="mb-2 text-[10px] font-bold uppercase tracking-[.12em] text-[#92939d]">Stores that stay active ({keepStoreIds.length}/{targetStoreLimit})</p>
                <div className="max-h-40 space-y-1 overflow-y-auto">
                  {activeStores.map((store) => (
                    <button key={store.id} type="button" onClick={() => toggleStore(store.id)} className={`flex w-full items-center gap-2 rounded-lg border px-3 py-2 text-left text-xs ${keepStoreIds.includes(store.id) ? "border-[#6957f5] bg-[#f5f3ff] font-extrabold text-[#4f45c9]" : "border-[#e6e6ed] text-[#565762]"}`}>
                      <Store size={13} className="shrink-0 text-[#a1a2ab]" />
                      <span className="min-w-0 flex-1 truncate">{store.name}</span>
                      {keepStoreIds.includes(store.id) && <Check size={13} className="text-[#6957f5]" />}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {choose && needsMemberPick && staff.length > 0 && (
              <div className="mt-3">
                <p className="mb-2 text-[10px] font-bold uppercase tracking-[.12em] text-[#92939d]">Team members that stay active ({keepMemberIds.length}/{staffRoom})</p>
                <div className="max-h-40 space-y-1 overflow-y-auto">
                  {staff.map((member) => (
                    <button key={member.id} type="button" onClick={() => toggleMember(member.id)} className={`flex w-full items-center gap-2 rounded-lg border px-3 py-2 text-left text-xs ${keepMemberIds.includes(member.id) ? "border-[#6957f5] bg-[#f5f3ff] font-extrabold text-[#4f45c9]" : "border-[#e6e6ed] text-[#565762]"}`}>
                      <Users size={13} className="shrink-0 text-[#a1a2ab]" />
                      <span className="min-w-0 flex-1 truncate">{member.user?.full_name || member.user?.email || member.id}</span>
                      {keepMemberIds.includes(member.id) && <Check size={13} className="text-[#6957f5]" />}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
        <div className="flex justify-end gap-2 border-t border-[#eeeeF2] pt-4">
          <Button variant="outline" onClick={onClose} disabled={saving}>Not now</Button>
          <Button onClick={confirm} disabled={saving}>{saving ? "Saving..." : isFree ? "Schedule cancel" : "Schedule change"}</Button>
        </div>
      </div>
    </Modal>
  );
}

function LiveBillingView({ subscription, plans, stores, members, billingPayments, billingPayment, token, onCheckout, onScheduleChange, onClearSchedule, onCompletePayment, loading, error, notify }) {
  const BILLING_CYCLES = [
    { key: "monthly", label: "Monthly", multiplier: 1, discount: 0, badge: null, billedLabel: "billed monthly" },
    { key: "semi_annual", label: "Semi-annual", multiplier: 6, discount: 0.15, badge: "Save 15%", billedLabel: "billed every 6 months" },
    { key: "annual", label: "Annual", multiplier: 12, discount: 0.2, badge: "Save 20%", billedLabel: "billed annually" },
  ];
  const [selectedPlan, setSelectedPlan] = useState("starter");
  const [scheduleTarget, setScheduleTarget] = useState(null);
  const [saving, setSaving] = useState(false);
  const [billingCycle, setBillingCycle] = useState("monthly");
  const [paymentMethod, setPaymentMethod] = useState("khqr");
  const [dismissedPaymentId, setDismissedPaymentId] = useState(() => sessionStorage.getItem("chmaba_dismissed_billing_payment") || null);
  const dismissPayment = (id) => { if (!id) return; setDismissedPaymentId(id); sessionStorage.setItem("chmaba_dismissed_billing_payment", id); };
  const cycle = BILLING_CYCLES.find((item) => item.key === billingCycle) || BILLING_CYCLES[0];
  const currentPlan = plans.find((plan) => plan.code === subscription?.plan_code);
  const pending = billingPayment && billingPayment.status !== "paid";
  const isCurrent = (plan) => plan.code === subscription?.plan_code && subscription?.status === "active";
  const onPaidActive = subscription?.status === "active" && subscription?.plan_code && subscription?.plan_code !== "free";
  const cycleMeta = (cycleKey) => BILLING_CYCLES.find((item) => item.key === cycleKey) || BILLING_CYCLES[0];
  const activeCycle = subscription?.billing_cycle && BILLING_CYCLES.some((item) => item.key === subscription.billing_cycle) ? subscription.billing_cycle : "monthly";
  const moneyUsd = (value) => `$${value.toFixed(2)}`;
  const perMonth = (plan, cycleKey) => (Number(plan?.monthly_price) || 0) * (1 - cycleMeta(cycleKey).discount);
  const planPriceText = (plan, cycleKey) => Number(plan?.monthly_price) > 0 ? moneyUsd(perMonth(plan, cycleKey)) : "$0.00";
  const planTotalText = (plan, cycleKey) => { const meta = cycleMeta(cycleKey); return Number(plan?.monthly_price) > 0 ? `${moneyUsd(perMonth(plan, cycleKey) * meta.multiplier)} ${meta.billedLabel}` : "Free forever"; };
  const planFeatureList = (plan) => plan?.marketing_features || [];
  const currentPrice = currentPlan ? perMonth(currentPlan, activeCycle) : 0;
  const scheduledCode = subscription?.scheduled_plan_code;
  const scheduledTarget = plans.find((plan) => plan.code === scheduledCode);
  const endsLabel = subscription?.ends_at ? new Date(subscription.ends_at).toLocaleDateString() : null;
  const canSchedule = (plan) => onPaidActive && !isCurrent(plan) && (plan.code === "free" || (currentPlan && (Number(plan.monthly_price) || 0) < (Number(currentPlan.monthly_price) || 0)));
  const isUpgradeCard = (plan) => onPaidActive && !isCurrent(plan) && !(plan.code === "free") && (Number(plan.monthly_price) || 0) >= (Number(currentPlan?.monthly_price) || 0);
  const confirmSchedule = async (body) => {
    setSaving(true);
    try {
      const updated = await onScheduleChange(body);
      if (updated) { setScheduleTarget(null); notify(body.plan_code === "free" ? `Cancellation scheduled for ${endsLabel}` : `${currentPlan?.name || ""} to ${body.plan_code} scheduled for ${endsLabel}`); }
    } finally { setSaving(false); }
  };
  return (
    <div className="mx-auto max-w-[1460px] p-5 lg:p-8">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <h2 className="text-2xl font-extrabold tracking-[-.05em]">Plans for your pace</h2>
          <p className="mt-1 text-sm text-[#898a95]">Live pricing from the Chmaba plans catalog, with live subscription and payment status.</p>
        </div>
        <Badge tone={subscription?.status === "active" ? "green" : "yellow"} dot>{subscription?.status || "loading"}</Badge>
      </div>
      <div className="mt-7 rounded-2xl bg-[#17181c] p-5 text-white sm:p-6">
        <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-center">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[.14em] text-[#c4f27c]">Current plan</p>
            <h3 className="mt-3 text-2xl font-extrabold capitalize tracking-[-.05em]">{currentPlan?.name || subscription?.plan_code || "Free"}</h3>
            <p className="mt-1 text-xs text-[#92939d]">{subscription?.status === "pending" ? "Payment required to unlock this plan" : subscription?.ends_at ? `Plan ends ${new Date(subscription.ends_at).toLocaleDateString()}` : "No renewal date"}</p>
          </div>
          <div className="text-right">
            <p className="text-3xl font-extrabold">{moneyUsd(currentPrice)}<span className="text-xs font-medium text-[#92939d]"> / month</span></p>
            <p className="mt-1 text-[10px] text-[#92939d]">{currentPlan ? planTotalText(currentPlan, activeCycle) : "Free forever"}</p>
          </div>
        </div>
        {scheduledCode && scheduledTarget && (
          <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-xl bg-white/10 px-4 py-3">
            <p className="text-xs text-[#cfcff4]">
              <strong className="font-extrabold text-white">Scheduled:</strong> {scheduledTarget.name === "Free" ? "cancel to Free" : `switch to ${scheduledTarget.name}`} on {endsLabel || "period end"}. You can change or renew before then.
            </p>
            <Button variant="outline-dark" size="xs" onClick={onClearSchedule} disabled={loading}>Remove scheduled change</Button>
          </div>
        )}
      </div>
      <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
        <div className="inline-flex rounded-xl border border-[#e4e4eb] bg-[#f5f5f8] p-1">
          {BILLING_CYCLES.map((item) => (
            <button key={item.key} onClick={() => setBillingCycle(item.key)} className={`relative rounded-lg px-4 py-2 text-xs font-bold transition ${billingCycle === item.key ? "bg-[#6957f5] text-white shadow-sm" : "text-[#747580] hover:text-[#202128]"}`}>
              {item.label}
              {item.badge && <span className={`ml-1.5 text-[9px] ${billingCycle === item.key ? "text-[#c4f27c]" : "text-[#6957f5]"}`}>{item.badge}</span>}
            </button>
          ))}
        </div>
      </div>
      <div className="mt-4 flex flex-wrap items-center justify-center gap-3">
        <span className="text-[10px] font-bold uppercase tracking-[.14em] text-[#92939d]">Pay with</span>
        <div className="inline-flex rounded-xl border border-[#e4e4eb] bg-[#f5f5f8] p-1">
          <button type="button" onClick={() => setPaymentMethod("khqr")} className={`flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-bold transition ${paymentMethod === "khqr" ? "bg-[#ed2939] text-white shadow-sm" : "text-[#747580] hover:text-[#202128]"}`}><QrCode size={13} /> KHQR</button>
          <button type="button" onClick={() => setPaymentMethod("card")} className={`flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-bold transition ${paymentMethod === "card" ? "bg-[#6957f5] text-white shadow-sm" : "text-[#747580] hover:text-[#202128]"}`}><CreditCard size={13} /> Card</button>
        </div>
        <span className="max-w-[340px] text-[10px] leading-4 text-[#92939d]">{paymentMethod === "card" ? "Pay by card on Paddle's secure hosted checkout. Plans stay prepaid — no card is stored and nothing auto-renews." : "Scan the KHQR with any Bakong-enabled banking app."}</span>
      </div>
      {onPaidActive && (
        <p className="mt-3 text-center text-[11px] text-[#92939d]">Renewing your current plan early adds the next period after your current one ends — paying now never shortens time you have already paid for.</p>
      )}
      {error && <p className="mt-5 rounded-xl border border-[#ffd7d2] bg-[#fff5f3] px-3 py-2.5 text-xs text-[#c2564b]">{error}</p>}
      {loading && plans.length === 0 ? <p className="mt-8 text-center text-xs text-[#999aa4]">Loading plans...</p> : (
        <div className="mt-7 grid gap-4 lg:grid-cols-3">
          {plans.map((plan) => {
            const current = isCurrent(plan);
            const scheduleCard = canSchedule(plan);
            const upgradeCard = !current && !scheduleCard && plan.code !== "free" && (onPaidActive || (subscription?.plan_code === "free" && subscription?.status === "active"));
            const cancelCard = canSchedule(plan) && plan.code === "free";
            const includeFree = plan.code === "free" && !onPaidActive;
            const renewCard = current && plan.code !== "free" && subscription?.status === "active";
            const buttonDisabled = (current && !renewCard) || loading || (subscription?.status === "pending" && !current);
            const buttonLabel = renewCard ? `Renew & extend ${plan.name}` : current ? "Current plan" : cancelCard ? "Cancel at period end" : scheduleCard ? `Schedule ${plan.name}` : includeFree ? "Included" : upgradeCard ? `Choose ${plan.name}` : "Unavailable";
            return (
              <div key={plan.code} className={`flex flex-col rounded-2xl border p-5 ${current ? "border-[#6957f5] bg-[#f8f7ff]" : "border-[#e8e8ee] bg-white"}`}>
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <p className="text-sm font-extrabold">{plan.name}</p>
                    <p className="mt-1 text-[10px] leading-4 text-[#92939d]">{plan.description || `${Number(plan.transaction_limit || 0).toLocaleString()} transactions / month`}</p>
                  </div>
                  <div className="flex shrink-0 flex-col items-end gap-1.5">
                    {current && <Badge tone="violet">CURRENT</Badge>}
                    {plan.code === subscription?.plan_code && subscription?.status === "pending" && <Badge tone="yellow">PENDING</Badge>}
                    {scheduledCode === plan.code && <Badge tone="yellow">SCHEDULED</Badge>}
                  </div>
                </div>
                <p className="mt-5 text-3xl font-extrabold tracking-[-.06em]">{planPriceText(plan, billingCycle)}<span className="text-xs font-medium text-[#92939d]"> / month</span></p>
                <p className="mt-1 text-[10px] text-[#92939d]">{planTotalText(plan, billingCycle)}</p>
                <div className="my-5 h-px bg-[#eeeeF2]" />
                <div className="flex-1 space-y-2.5 text-xs text-[#6c6d77]">
                  {planFeatureList(plan).map((feature) => (
                    <p key={feature} className="flex items-start gap-2"><Check size={13} className="mt-0.5 shrink-0 text-[#65a33c]" />{feature}</p>
                  ))}
                </div>
                <Button className="mt-6 w-full" variant={renewCard ? "primary" : current ? "outline" : scheduleCard ? "soft" : upgradeCard ? "primary" : "outline"} disabled={buttonDisabled} onClick={() => { if (renewCard) { onCheckout(plan.code, billingCycle, paymentMethod); } else if (scheduleCard || cancelCard) { setScheduleTarget(plan); } else if (upgradeCard) { setSelectedPlan(plan.code); onCheckout(plan.code, billingCycle, paymentMethod); } }}>
                  {buttonLabel}
                </Button>
              </div>
            );
          })}
        </div>
      )}
      <div className="mt-7 rounded-2xl border border-[#e9e9ef] bg-white p-5 sm:p-6">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-extrabold">Payment history</h3>
            <p className="mt-1 text-[11px] text-[#999aa4]">CutLuy (KHQR) and Paddle (card) billing payments</p>
          </div>
          <WalletCards size={17} className="text-[#a1a2ab]" />
        </div>
        <div className="mt-5 space-y-2">
          {billingPayments.length === 0 ? <p className="rounded-xl bg-[#fafafd] p-4 text-xs text-[#999aa4]">No payments yet.</p> : billingPayments.map((payment) => (
            <div key={payment.id} className="flex items-center gap-3 rounded-xl bg-[#fafafd] px-3 py-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#f0eff5] text-[#6957f5]"><QrCode size={14} /></div>
              <div className="flex-1">
                <p className="text-xs font-bold">{payment.reference_id}</p>
                <p className="mt-1 text-[10px] text-[#999aa4]">{new Date(payment.created_at).toLocaleString()}</p>
              </div>
              <Badge tone={payment.status === "paid" ? "green" : "yellow"} dot>{payment.status}</Badge>
              <span className="text-xs font-extrabold">{formatCurrencyAmount(Number(payment.amount), payment.currency_code)}</span>
            </div>
          ))}
        </div>
      </div>
      {pending && (
        <Modal open={pending && billingPayment.id !== dismissedPaymentId} onClose={() => dismissPayment(billingPayment.id)} title="Complete plan payment" description={billingPayment.provider === "paddle" ? "Pay by card on Paddle's secure hosted checkout." : "Scan this KHQR with any Bakong-enabled banking app."} width="max-w-[420px]">
          {billingPayment.provider === "paddle" ? (
            <div className="rounded-2xl border border-[#e4dcff] bg-[#f7f4ff] p-5 text-center">
              <div className="mx-auto flex h-[68px] w-[68px] items-center justify-center rounded-2xl bg-[#6957f5] text-white"><CreditCard size={28} /></div>
              <p className="mt-4 text-xs font-extrabold text-[#3d3790]">{selectedPlan.toUpperCase()} plan · {formatCurrencyAmount(Number(billingPayment.amount), "USD")} + local tax</p>
              <p className="mt-1 text-[10px] text-[#8b82c9]">Collected and receipted by Paddle (merchant of record). Plans stay prepaid — nothing auto-renews.</p>
            </div>
          ) : (
            <div className="rounded-2xl border border-[#dfe8d7] bg-[#f8fcf5] p-5 text-center">
              <div className="mx-auto flex h-[180px] w-[180px] items-center justify-center rounded-xl border-[7px] border-white bg-white p-3 shadow-sm">
                <QRCodeSVG value={billingPayment.qr_string || billingPayment.checkout_url || billingPayment.external_id || "chmaba-plan"} size={150} includeMargin level="H" />
              </div>
              <p className="mt-4 text-xs font-extrabold text-[#465142]">{selectedPlan.toUpperCase()} plan · {formatCurrencyAmount(Number(billingPayment.amount), "USD")}</p>
              <p className="mt-1 text-[10px] text-[#84907e]">Powered by cutluy.com</p>
            </div>
          )}
          {billingPayment.external_id?.startsWith("mock_") ? (
            <Button className="mt-5 w-full" onClick={onCompletePayment}>Simulate paid in development <Check size={15} /></Button>
          ) : billingPayment.provider === "paddle" ? (
            <Button className="mt-5 w-full" onClick={() => billingPayment.checkout_url && window.open(billingPayment.checkout_url, "_blank", "noopener,noreferrer")}><CreditCard size={15} /> Open Paddle checkout</Button>
          ) : (
            <Button variant="outline" className="mt-5 w-full" onClick={() => billingPayment.checkout_url && window.open(billingPayment.checkout_url, "_blank", "noopener,noreferrer")}><ExternalLink size={14} /> Open CutLuy checkout</Button>
          )}
        </Modal>
      )}
      {scheduleTarget && (
        <PlanScheduleModal
          plan={scheduleTarget}
          currentPlan={currentPlan}
          subscription={subscription}
          stores={stores}
          members={members}
          renewLabel={planTotalText(scheduleTarget, activeCycle)}
          onClose={() => setScheduleTarget(null)}
          onConfirm={confirmSchedule}
          saving={saving}
        />
      )}
    </div>
  );
}

function LiveDashboardView({ workspace, products, inventory, report, onNavigate }) {  const lowStock = inventory.filter((item) => item.status !== "healthy");  const grossSales = report?.gross_sales ?? 0;  const transactions = report?.transactions ?? 0;  const average = report?.average_order ?? 0;  const topProducts = products.slice(0, 4);  return <div className="mx-auto max-w-[1460px] p-5 lg:p-8"><div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end"><div><div className="flex items-center gap-2 text-xs text-[#92939d]"><span className="h-2 w-2 rounded-full bg-[#76bc4b]" /> Live workspace · {workspace?.store?.name}</div><h2 className="mt-2 text-2xl font-extrabold tracking-[-.05em]">Good morning, {workspace?.company?.name || "there"}</h2><p className="mt-1 text-sm text-[#898a95]">Here is what is happening at your store today.</p></div><Button onClick={() => onNavigate("pos")}><Plus size={16} /> New sale</Button></div><div className="mt-7 grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><MetricCard label="Sales this period" value={formatCurrencyAmount(Number(grossSales), workspace?.store?.currency_code)} change="Live" direction="up" tone="violet" icon={CircleDollarSign} detail="From paid orders" /><MetricCard label="Transactions" value={transactions} change="Live" direction="up" tone="lime" icon={Receipt} detail="Paid orders" /><MetricCard label="Average order" value={formatCurrencyAmount(Number(average), workspace?.store?.currency_code)} change="Live" direction="up" tone="peach" icon={TrendingUp} detail="Current period" /><MetricCard label="Low stock items" value={lowStock.length} change="View items" direction="alert" tone="yellow" icon={AlertTriangle} detail="Needs attention" /></div><div className="mt-5 grid gap-5 xl:grid-cols-[1.25fr_.75fr]"><section className="card-border surface-shadow rounded-2xl bg-white p-5 sm:p-6"><div className="flex items-start justify-between"><div><h3 className="text-sm font-extrabold">Sales overview</h3><p className="mt-1 text-[11px] text-[#999aa4]">{report?.from_date} to {report?.to_date}</p></div><Badge tone="green" dot>PostgreSQL live</Badge></div><div className="mt-7 space-y-3">{(report?.daily_sales || []).length === 0 ? <div className="rounded-xl bg-[#fafafd] p-10 text-center text-xs text-[#999aa4]">No paid sales in this period yet.</div> : report.daily_sales.slice(-7).map((item) => <div key={item.date} className="flex items-center gap-3"><span className="w-20 text-[10px] text-[#92939d]">{item.date.slice(5)}</span><div className="h-2 flex-1 overflow-hidden rounded-full bg-[#f0f0f4]"><div className="h-full rounded-full bg-[#b9b2fa]" style={{ width: `${(Number(item.amount) / (Number(report.daily_sales.reduce((m, d) => Math.max(m, Number(d.amount)), 0)) || 1)) * 100}%` }} /></div><span className="w-20 text-right text-[11px] font-extrabold">{formatCurrencyAmount(Number(item.amount), workspace?.store?.currency_code)}</span></div>)}</div></section><section className="card-border surface-shadow rounded-2xl bg-white p-5 sm:p-6"><div className="flex items-center justify-between"><div><h3 className="text-sm font-extrabold">Top products</h3><p className="mt-1 text-[11px] text-[#999aa4]">Best sellers</p></div><button onClick={() => onNavigate("products")} className="text-[11px] font-bold text-[#6957f5] hover:text-[#5040d6]">View catalog</button></div><div className="mt-5 space-y-4">{topProducts.length === 0 ? <p className="py-8 text-center text-xs text-[#92939d]">No products yet.</p> : topProducts.map((product, index) => <div key={product.id} className="flex items-center gap-3"><span className="w-3 text-center text-[10px] font-bold text-[#b2b2ba]">{index + 1}</span><ProductMark product={product} size="sm" /><div className="min-w-0 flex-1"><p className="truncate text-xs font-bold text-[#303139]">{product.name}</p></div><p className="text-xs font-extrabold">{formatCurrencyAmount(product.price, workspace?.store?.currency_code)}</p></div>)}</div></section></div></div>;}

function LiveAuditView({ token, notify }) {  const [logs, setLogs] = useState([]);  const [loading, setLoading] = useState(true);  const [error, setError] = useState("");  useEffect(() => {    (async () => { try { setLogs(await api.auditLogs(token)); } catch (requestError) { setError(requestError.message || "Could not load activity"); } finally { setLoading(false); } })();  }, [token]);  return <div className="mx-auto max-w-[1460px] p-5 lg:p-8"><div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end"><div><h2 className="text-2xl font-extrabold tracking-[-.05em]">Activity</h2><p className="mt-1 text-sm text-[#898a95]">Recent changes made by your team across the workspace.</p></div><Badge tone="green" dot>Audited</Badge></div>{error && <p className="mt-5 rounded-xl border border-[#ffd7d2] bg-[#fff5f3] px-3 py-2.5 text-xs text-[#c2564b]">{error}</p>}<div className="mt-7 rounded-2xl border border-[#e9e9ef] bg-white p-4 sm:p-6"><div className="app-scrollbar overflow-x-auto"><table className="mobile-table w-full border-collapse text-left"><thead><tr className="border-y border-[#f0f0f3] text-[10px] font-bold uppercase tracking-wide text-[#a1a2ab]"><th className="py-3 pl-2 font-bold">When</th><th className="px-4 py-3 font-bold">Who</th><th className="px-4 py-3 font-bold">Action</th><th className="px-4 py-3 font-bold">Details</th></tr></thead><tbody>{logs.length === 0 && !loading && <tr><td colSpan="4" className="py-14 text-center text-sm text-[#92939d]">No activity recorded yet.</td></tr>}{logs.map((entry) => <tr key={entry.id} className="border-b border-[#f2f2f5] last:border-0"><td className="py-3.5 pl-2 text-xs text-[#92939d]">{new Date(entry.created_at).toLocaleString()}</td><td className="px-4 py-3.5 text-xs font-extrabold text-[#34353d]">{entry.actor}</td><td className="px-4 py-3.5"><Badge tone="violet">{entry.action}</Badge> <span className="ml-1 text-[10px] text-[#a1a2ab]">{entry.entity_type}</span></td><td className="px-4 py-3.5 text-xs text-[#656670]">{Object.entries(entry.details || {}).map(([key, value]) => `${key}: ${value}`).join(" · ")}</td></tr>)}</tbody></table></div></div></div>;}

function LiveTeamView({ members, stores, invitations = [], onInvite, onUpdateMember, onAcceptInvite, onCancelInvite, onRemoveMember, loading, error }) {  const [inviteOpen, setInviteOpen] = useState(false);
const [editMember, setEditMember] = useState(null);
const [email, setEmail] = useState("");
const [role, setRole] = useState("cashier");
const [storeIds, setStoreIds] = useState([]);
const [cancelTarget, setCancelTarget] = useState(null);
const [memberRemoveTarget, setMemberRemoveTarget] = useState(null);
const [toggleTarget, setToggleTarget] = useState(null);  const storeName = (id) => (stores.find((store) => store.id === id) || {}).name || "Store";  const isOwner = (member) => member.role === "owner";  const isActive = (member) => member.status === "active" || member.status === "invited" || member.status === null || member.status === undefined;  const submit = async (event) => { event.preventDefault(); const result = await onInvite({ email, role, store_ids: storeIds.length ? storeIds : stores.map((store) => store.id) }); if (result) { setInviteOpen(false); setEmail(""); setRole("cashier"); setStoreIds([]); } };const openEditor = (member) => { setEditMember(member); setRole(member.role); setStoreIds(member.store_ids || []); };const saveMember = async (event) => { event.preventDefault(); const result = await onUpdateMember(editMember.id, { role, store_ids: storeIds }); if (result) setEditMember(null); };const performToggle = async () => { const member = toggleTarget; if (!member) return; setToggleTarget(null); await onUpdateMember(member.id, { status: isActive(member) ? "revoked" : "active" }); };const performRemove = async () => { const member = memberRemoveTarget; if (!member) return; setMemberRemoveTarget(null); await onRemoveMember(member.id); };const activeCount = members.filter((member) => isActive(member)).length;  return <div className="mx-auto max-w-[1460px] p-5 lg:p-8"><div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end"><div><h2 className="text-2xl font-extrabold tracking-[-.05em]">Your team</h2><p className="mt-1 text-sm text-[#898a95]">People, roles and store access from your workspace.</p></div><Button onClick={() => setInviteOpen(true)}><UserPlus size={15} /> Invite teammate</Button></div>{error && <p className="mt-5 rounded-xl border border-[#ffd7d2] bg-[#fff5f3] px-3 py-2.5 text-xs text-[#c2564b]">{error}</p>}<div className="mt-7 grid gap-3 sm:grid-cols-3"><SmallStat label="Team members" value={members.length} detail="People on the workspace" icon={Users} tone="violet" /><SmallStat label="Active" value={activeCount} detail="Can sign in and work" icon={ShieldCheck} tone="green" /><SmallStat label="Stores covered" value={stores.length} detail="Available locations" icon={Store} tone="yellow" /></div><div className="mt-5 rounded-2xl border border-[#e9e9ef] bg-white p-4 sm:p-6"><div className="flex items-center justify-between"><div><h3 className="text-sm font-extrabold">People & permissions</h3><p className="mt-1 text-[11px] text-[#999aa4]">Role assignments and access stored in PostgreSQL.</p></div><Badge tone="green" dot>Live</Badge></div><div className="app-scrollbar mt-4 overflow-x-auto"><table className="mobile-table w-full border-collapse text-left"><thead><tr className="border-y border-[#f0f0f3] text-[10px] font-bold uppercase tracking-wide text-[#a1a2ab]"><th className="py-3 pl-2 font-bold">Member</th><th className="px-4 py-3 font-bold">Role</th><th className="px-4 py-3 font-bold">Stores</th><th className="px-4 py-3 font-bold">Status</th><th className="w-40 px-2 py-3 text-right font-bold">Actions</th></tr></thead><tbody>{members.length === 0 ? <tr><td colSpan="5" className="py-14 text-center text-sm text-[#92939d]">{loading ? "Loading team..." : "No team members yet."}</td></tr> : members.map((member) => { const owner = isOwner(member); const active = isActive(member); return <tr key={member.id} className={`border-b border-[#f2f2f5] last:border-0 ${active ? "" : "opacity-60"}`}><td className="py-3.5 pl-2"><div className="flex items-center gap-3"><div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[#ded9fb] text-[10px] font-bold text-[#5144c7]">{(member.user?.full_name || "?").slice(0, 2).toUpperCase()}</div><div className="min-w-0"><p className="text-xs font-extrabold text-[#34353d]">{member.user?.full_name}{owner && <span className="ml-1.5 text-[10px] font-bold uppercase tracking-wide text-[#a1a2ab]">Owner</span>}</p><p className="mt-0.5 truncate text-[10px] text-[#9a9ba4]">{member.user?.email}</p></div></div></td><td className="px-4 py-3.5"><Badge tone={member.role === "manager" ? "blue" : member.role === "inventory_manager" ? "violet" : "neutral"}>{member.role === "inventory_manager" ? "Inventory" : member.role.replace("_", " ")}</Badge></td><td className="px-4 py-3.5 text-xs text-[#777883]">{(member.store_ids || []).map((id) => storeName(id)).join(", ") || "—"}</td><td className="px-4 py-3.5"><Badge tone={!active ? "neutral" : "green"}>{!active ? "Inactive" : "Active"}</Badge></td><td className="px-2 py-3.5"><div className="flex items-center justify-end gap-1">{owner ? <span className="pr-2 text-[10px] font-semibold text-[#b6b7c0]">Protected</span> : <><IconButton label={active ? "Deactivate" : "Activate"} onClick={() => setToggleTarget(member)}>{active ? <ToggleRight size={15} /> : <ToggleLeft size={15} />}</IconButton><IconButton label="Edit permissions" onClick={() => openEditor(member)}><ShieldCheck size={15} /></IconButton><IconButton label="Remove member" onClick={() => setMemberRemoveTarget(member)}><Trash2 size={15} /></IconButton></>}</div></td></tr>; })}</tbody></table></div></div>{invitations.length > 0 && <div className="mt-5 rounded-2xl border border-[#e9e9ef] bg-white p-4 sm:p-6"><div className="flex items-center justify-between"><div><h3 className="text-sm font-extrabold">Pending invitations</h3><p className="mt-1 text-[11px] text-[#999aa4]">People invited who have not accepted yet.</p></div><Badge tone="yellow">{invitations.length} pending</Badge></div><div className="app-scrollbar mt-4 overflow-x-auto"><table className="mobile-table w-full border-collapse text-left"><thead><tr className="border-y border-[#f0f0f3] text-[10px] font-bold uppercase tracking-wide text-[#a1a2ab]"><th className="py-3 pl-2 font-bold">Invite</th><th className="px-4 py-3 font-bold">Role</th><th className="px-4 py-3 font-bold">Invited</th><th className="w-32 px-2 py-3 text-right font-bold">Actions</th></tr></thead><tbody>{invitations.map((invite) => <tr key={invite.id} className="border-b border-[#f2f2f5] last:border-0"><td className="py-3.5 pl-2 text-xs font-extrabold text-[#34353d]">{invite.email}</td><td className="px-4 py-3.5"><Badge tone={invite.role === "manager" ? "blue" : invite.role === "inventory_manager" ? "violet" : "neutral"}>{invite.role === "inventory_manager" ? "Inventory" : invite.role.replace("_", " ")}</Badge></td><td className="px-4 py-3.5 text-xs text-[#92939d]">{new Date(invite.created_at).toLocaleDateString()} · expires {new Date(invite.expires_at).toLocaleDateString()}</td><td className="px-2 py-3.5"><div className="flex items-center justify-end gap-1"><IconButton label="Accept as member" onClick={() => onAcceptInvite(invite.id)}><Check size={15} /></IconButton><IconButton label="Cancel invitation" onClick={() => setCancelTarget(invite)}><X size={15} /></IconButton></div></td></tr>)}</tbody></table></div></div>}{inviteOpen && <Modal open onClose={() => setInviteOpen(false)} title="Invite a teammate" description="They get an email to create their password and join this workspace." width="max-w-[480px]"><form onSubmit={submit}><div className="space-y-4"><Field label="Work email" required type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="pisey@chmaba.com" /><label className="block"><span className="mb-1.5 block text-xs font-semibold text-[#4f5059]">Role</span><Dropdown value={role} onChange={(v) => setRole(v)} options={[{ value: "manager", label: "Manager" }, { value: "cashier", label: "Cashier" }, { value: "inventory_manager", label: "Inventory manager" }]} /></label><div><p className="mb-2 text-xs font-semibold text-[#4f5059]">Store access</p><div className="flex flex-wrap gap-2">{stores.map((store) => <button type="button" key={store.id} onClick={() => setStoreIds((current) => current.includes(store.id) ? current.filter((id) => id !== store.id) : [...current, store.id])} className={`rounded-lg px-3 py-2 text-xs font-bold ${storeIds.includes(store.id) ? "bg-[#17181c] text-white" : "bg-[#f3f3f6] text-[#777883]"}`}>{store.name}</button>)}</div><p className="mt-2 text-[10px] text-[#a1a2ab]">{storeIds.length === 0 ? "All stores will be included." : `${storeIds.length} store(s) selected.`}</p></div></div>{error && <p className="mt-3 rounded-xl border border-[#ffd7d2] bg-[#fff5f3] px-3 py-2 text-xs text-[#c2564b]">{error}</p>}<div className="mt-5 flex gap-2"><Button type="button" variant="outline" className="flex-1" onClick={() => setInviteOpen(false)}>Cancel</Button><Button className="flex-1" disabled={!email.includes("@")}><UserPlus size={15} /> Send invitation</Button></div></form></Modal>}{editMember && <Modal open onClose={() => setEditMember(null)} title={`Edit ${editMember.user?.full_name || "member"}`} description="Change role or which stores they can access." width="max-w-[480px]"><form onSubmit={saveMember}><div className="space-y-4"><label className="block"><span className="mb-1.5 block text-xs font-semibold text-[#4f5059]">Role</span><Dropdown value={role} onChange={(v) => setRole(v)} options={[{ value: "manager", label: "Manager" }, { value: "cashier", label: "Cashier" }, { value: "inventory_manager", label: "Inventory manager" }]} /></label><div><p className="mb-2 text-xs font-semibold text-[#4f5059]">Store access</p><div className="flex flex-wrap gap-2">{stores.map((store) => <button type="button" key={store.id} onClick={() => setStoreIds((current) => current.includes(store.id) ? current.filter((id) => id !== store.id) : [...current, store.id])} className={`rounded-lg px-3 py-2 text-xs font-bold ${storeIds.includes(store.id) ? "bg-[#17181c] text-white" : "bg-[#f3f3f6] text-[#777883]"}`}>{store.name}</button>)}</div></div></div><div className="mt-5 flex gap-2"><Button type="button" variant="outline" className="flex-1" onClick={() => setEditMember(null)}>Cancel</Button><Button className="flex-1"><Check size={15} /> Save permissions</Button></div></form></Modal>}{toggleTarget && <ConfirmDialog open title={isActive(toggleTarget) ? `Deactivate ${toggleTarget.user?.full_name}?` : `Activate ${toggleTarget.user?.full_name}?`} message={isActive(toggleTarget) ? "They can no longer sign in to this workspace until reactivated. Their data stays." : "They can sign in and access this workspace again."} confirmLabel={isActive(toggleTarget) ? "Deactivate" : "Activate"} onConfirm={performToggle} onCancel={() => setToggleTarget(null)} />}{cancelTarget && <ConfirmDialog open title={`Cancel invitation for ${cancelTarget.email}?`} message="The invite link stops working and they will not be able to join." confirmLabel="Cancel invitation" onConfirm={async () => { await onCancelInvite(cancelTarget.id); setCancelTarget(null); }} onCancel={() => setCancelTarget(null)} />}{memberRemoveTarget && <ConfirmDialog open title={`Remove ${memberRemoveTarget.user?.full_name}?`} message="Their access is revoked immediately. You can re-invite them later." confirmLabel="Remove member" onConfirm={performRemove} onCancel={() => setMemberRemoveTarget(null)} />}</div>;}

export {
  LiveBillingView,
  LiveDashboardView,
  LiveAuditView,
  LiveTeamView,
};
