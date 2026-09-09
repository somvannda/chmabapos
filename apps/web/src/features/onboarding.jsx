import { useEffect, useMemo, useState } from "react";
import { ArrowRight, Check, ChevronDown, ChevronLeft, Store } from "lucide-react";
import { Logo, ThemeToggle, Badge, Field, Dropdown, Button } from "../components/ui";
import { api } from "../api";

const ONBOARDING_STEPS = ["Company details", "Choose your plan"];

function Onboarding({ step, setStep, data, setData, selectedPlan, setSelectedPlan, onFinish, onBack, loading, error }) {
  const [plans, setPlans] = useState([]);
  const [plansLoading, setPlansLoading] = useState(true);
  const [plansError, setPlansError] = useState("");

  const loadPlans = () => {
    setPlansLoading(true);
    setPlansError("");
    api.plans()
      .then((rows) => setPlans(rows || []))
      .catch((err) => setPlansError(err.message || "Could not load plans"))
      .finally(() => setPlansLoading(false));
  };

  useEffect(() => {
    let active = true;
    setPlansLoading(true);
    api.plans()
      .then((rows) => { if (active) setPlans(rows || []); })
      .catch((err) => { if (active) setPlansError(err.message || "Could not load plans"); })
      .finally(() => { if (active) setPlansLoading(false); });
    return () => { active = false; };
  }, []);

  const viewPlans = useMemo(() => {
    const paid = plans.filter((plan) => Number(plan?.monthly_price || 0) > 0);
    const featuredCode = plans.some((plan) => plan.code === "starter") ? "starter" : (paid[0] || plans[0])?.code;
    return plans.map((plan) => {
      const monthlyPrice = Number(plan?.monthly_price || 0);
      return {
        code: plan.code,
        name: plan.name,
        price: monthlyPrice <= 0 ? "$0" : `$${monthlyPrice.toFixed(2)}`,
        monthly: monthlyPrice > 0,
        description: plan.description || "",
        features: plan.marketing_features || [],
        recommended: plan.code === featuredCode,
      };
    });
  }, [plans]);

  useEffect(() => {
    if (!plansLoading && plans.length > 0 && !plans.some((plan) => plan.code === selectedPlan)) {
      const fallback = viewPlans.find((plan) => plan.recommended) || viewPlans[0];
      if (fallback) setSelectedPlan(fallback.code);
    }
  }, [plans, plansLoading, viewPlans, selectedPlan, setSelectedPlan]);

  useEffect(() => {
    if (step > 1 && !data.company) setStep(1);
  }, [step, data.company, setStep]);

  useEffect(() => {
    if (step > ONBOARDING_STEPS.length) setStep(ONBOARDING_STEPS.length);
  }, [step, setStep]);

  const contentClassName = step === 2
    ? "flex w-full flex-1 flex-col px-6 pb-10 sm:px-10"
    : "mx-auto flex w-full max-w-[570px] flex-1 flex-col px-6 pb-10 sm:px-10";

  return (
    <div className="min-h-screen bg-[#f7f7fa] p-4 sm:p-6">
      <div className="mx-auto flex min-h-[calc(100vh-2rem)] max-w-[1180px] overflow-hidden rounded-[28px] border border-[#e7e6ef] bg-white shadow-panel sm:min-h-[calc(100vh-3rem)]">
        <aside className="mesh-bg hidden w-[310px] flex-col p-8 text-white md:flex">
          <button onClick={onBack} className="w-fit"><Logo light /></button>
          <div className="mt-auto">
            <p className="text-xs font-bold uppercase tracking-[.15em] text-[#c4f27c]">Your first setup</p>
            <h1 className="mt-4 text-3xl font-extrabold leading-tight tracking-[-.06em]">Make your store<br />feel like yours.</h1>
            <p className="mt-4 text-sm leading-6 text-[#9b9ca5]">A few details now means smoother selling later.</p>
            <div className="mt-10 space-y-5">
              {ONBOARDING_STEPS.map((label, index) => (
                <div key={label} className="flex items-center gap-3">
                  <div className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold ${step > index + 1 ? "bg-[#c4f27c] text-[#1d2817]" : step === index + 1 ? "border border-[#c4f27c] text-[#c4f27c]" : "bg-[#292a30] text-[#777880]"}`}>
                    {step > index + 1 ? <Check size={14} /> : index + 1}
                  </div>
                  <span className={`text-xs ${step === index + 1 ? "font-bold text-white" : "text-[#81828b]"}`}>{label}</span>
                </div>
              ))}
            </div>
          </div>
          <p className="mt-10 text-[11px] text-[#676870]">You can edit these settings anytime.</p>
        </aside>
        <main className="flex flex-1 flex-col">
          <div className="flex items-center justify-between p-6 sm:p-10">
            <button onClick={onBack} className="md:hidden"><Logo /></button>
            <div className="ml-auto flex items-center gap-4">
              <ThemeToggle />
              <span className="text-xs font-semibold text-[#9697a0]">Step {step} of {ONBOARDING_STEPS.length}</span>
            </div>
          </div>
          <div className={contentClassName}>
            {step === 1 && <SetupCompany data={data} setData={setData} onNext={() => setStep(2)} />}
            {step === 2 && (
              <SetupPlan
                plans={viewPlans}
                loading={plansLoading}
                error={plansError}
                onRetry={loadPlans}
                selectedPlan={selectedPlan}
                setSelectedPlan={setSelectedPlan}
                submitting={loading}
                submitError={error}
                onBack={() => setStep(1)}
                onNext={() => onFinish({ ...data, plan_code: selectedPlan })}
              />
            )}
          </div>
        </main>
      </div>
    </div>
  );
}

function SetupCompany({ data, setData, onNext }) {
  return (
    <div className="flex flex-1 flex-col justify-center py-4">
      <Badge tone="violet">COMPANY SETUP</Badge>
      <h2 className="mt-4 text-3xl font-extrabold tracking-[-.055em]">Tell us about your store</h2>
      <p className="mt-2 text-sm leading-6 text-[#898a95]">This is what your team and customers will see.</p>
      <div className="mt-8 space-y-4">
        <Field label="Company or brand name" required placeholder="e.g. Cedar & Stone" value={data.company} onChange={(event) => setData({ ...data, company: event.target.value })} />
        <Field label="First store name" required placeholder="e.g. Main store" value={data.store} onChange={(event) => setData({ ...data, store: event.target.value })} />
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block">
            <span className="mb-1.5 block text-xs font-semibold text-[#4f5059]">Country</span>
            <div className="relative">
              <Dropdown value={data.country} onChange={(v) => setData({ ...data, country: v })} chevron={false} options={[{ value: "Cambodia", label: "Cambodia" }, { value: "Thailand", label: "Thailand" }, { value: "Vietnam", label: "Vietnam" }, { value: "Singapore", label: "Singapore" }]} />
              <ChevronDown size={15} className="pointer-events-none absolute right-3.5 top-3.5 text-[#92939d]" />
            </div>
          </label>
          <label className="block">
            <span className="mb-1.5 block text-xs font-semibold text-[#4f5059]">Default currency</span>
            <div className="relative">
              <Dropdown value={data.currency} onChange={(v) => setData({ ...data, currency: v })} chevron={false} options={[{ value: "USD", label: "USD - US Dollar" }, { value: "KHR", label: "KHR - Cambodian Riel" }, { value: "THB", label: "THB - Thai Baht" }]} />
              <ChevronDown size={15} className="pointer-events-none absolute right-3.5 top-3.5 text-[#92939d]" />
            </div>
          </label>
        </div>
        <div className="flex items-start gap-3 rounded-xl border border-[#e6e5f3] bg-[#faf9ff] p-3.5">
          <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-[#ece9ff] text-[#6957f5]"><Store size={14} /></div>
          <p className="text-xs leading-5 text-[#777883]">Your first store is ready for sales. Add more locations later from <strong className="text-[#545560]">Settings</strong>.</p>
        </div>
      </div>
      <Button className="mt-8 w-full" size="lg" onClick={onNext} disabled={!data.company || !data.store}>Continue <ArrowRight size={15} /></Button>
    </div>
  );
}

function SetupPlan({ plans, loading, error, onRetry, selectedPlan, setSelectedPlan, submitting, submitError, onBack, onNext }) {
  return (
    <div className="flex flex-1 flex-col py-4">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <Badge tone="violet">PICK YOUR PACE</Badge>
          <h2 className="mt-4 text-3xl font-extrabold tracking-[-.055em]">Choose a plan</h2>
          <p className="mt-2 text-sm leading-6 text-[#898a95]">Start free, then move up when your store needs more.</p>
        </div>
        <span className="text-[11px] font-semibold text-[#92939d]">All plans billed monthly</span>
      </div>

      {loading ? (
        <div className="mt-8 flex flex-1 items-center justify-center rounded-2xl border border-[#e9e9ef] bg-[#fafafd] p-10 text-sm text-[#92939d]">Loading plans...</div>
      ) : error ? (
        <div className="mt-8 flex flex-1 flex-col items-center justify-center gap-3 rounded-2xl border border-[#e9e9ef] bg-[#fafafd] p-10 text-center">
          <p className="text-sm text-[#92939d]">{error}</p>
          <Button variant="outline" size="sm" onClick={onRetry}>Try again</Button>
        </div>
      ) : (
        <>
          <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {plans.map((plan) => (
              <PlanOption key={plan.code} plan={plan} selected={selectedPlan === plan.code} onSelect={() => setSelectedPlan(plan.code)} />
            ))}
          </div>
          <div className="mt-8 flex items-center gap-3">
            <Button variant="outline" className="flex-1 sm:flex-none" size="lg" onClick={onBack} disabled={submitting}><ChevronLeft size={15} /> Back</Button>
            <Button className="flex-[2] sm:ml-auto sm:w-auto" size="lg" onClick={onNext} disabled={submitting}>{submitting ? "Creating workspace..." : "Continue"} {!submitting && <ArrowRight size={15} />}</Button>
          </div>
          {submitError && <p className="mt-4 rounded-xl border border-[#ffd7d2] bg-[#fff5f3] px-3 py-2.5 text-left text-xs leading-5 text-[#c2564b]">{submitError}</p>}
          <p className="mt-3 text-center text-[10px] text-[#b0b1ba]">{submitting ? "Saving your store and preparing your plan..." : selectedPlan === "free" ? "The Free plan needs no payment — you will go straight into your workspace." : "Choose your plan to continue. You will be asked to complete payment to unlock it."}</p>
        </>
      )}
    </div>
  );
}

function PlanOption({ plan, selected, onSelect }) {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      className={`relative flex flex-col rounded-2xl border p-5 text-left transition ${selected ? "border-[#6957f5] bg-[#faf9ff] ring-4 ring-[#6957f5]/10" : "border-[#e4e4eb] bg-white hover:border-[#bdb9ee] hover:shadow-soft"}`}
    >
      <div className="flex items-start justify-between gap-3">
        <span className="flex items-center gap-2.5">
          <span className={`flex h-5 w-5 items-center justify-center rounded-full border transition ${selected ? "border-[#6957f5]" : "border-[#c4c4ce]"}`}>
            {selected && <span className="h-2.5 w-2.5 rounded-full bg-[#6957f5]" />}
          </span>
          <span className="text-sm font-extrabold">{plan.name}</span>
        </span>
        {plan.recommended && <span className="rounded-full bg-[#c4f27c] px-2 py-1 text-[9px] font-extrabold tracking-wide text-[#3e562b]">RECOMMENDED</span>}
      </div>
      <div className="mt-4 flex items-baseline gap-1">
        <span className="text-2xl font-extrabold tracking-[-.04em]">{plan.price}</span>
        {plan.monthly && <span className="text-xs font-medium text-[#92939d]">/mo</span>}
      </div>
      <p className="mt-1 text-[11px] text-[#92939d]">{plan.description}</p>
      <div className="my-4 h-px bg-[#e9e9ef]" />
      <ul className="space-y-2">
        {plan.features.map((feature, index) => (
          <li key={`${plan.code}-${index}`} className="flex items-start gap-1.5 text-[11px] font-medium text-[#5d5e68]">
            <Check size={13} className="mt-0.5 shrink-0 text-[#6daf43]" />
            <span>{feature}</span>
          </li>
        ))}
      </ul>
    </button>
  );
}

export {
  Onboarding,
  SetupCompany,
  SetupPlan,
};
