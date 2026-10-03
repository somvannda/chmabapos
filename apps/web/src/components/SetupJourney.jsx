import { useEffect } from "react";
import { ArrowRight, PartyPopper } from "lucide-react";
import { Button } from "./ui";

// A compact, persistent coach that walks a new merchant through setup to their
// first sale. It reads the adaptive journey from GET /setup/checklist
// (goal/next_step_id/anchor/article_id) and never blocks the app: if a step's
// spotlight target is not on screen, "Show me" still navigates there.
//
// Dismissal is per user (User.preferences.setup_journey_dismissed), so a
// cashier can hide their own coach without affecting the owner.
function SetupJourney({ checklist, dismissed, onDismiss, onNavigate }) {
  const steps = checklist?.steps || [];
  const total = checklist?.total || 0;
  const completed = checklist?.completed || 0;
  const complete = total > 0 && completed >= total;
  const current = steps.find((step) => step.id === checklist?.next_step_id) || steps.find((step) => !step.done);

  // Briefly ring the element tagged for the current step, if it is mounted. The
  // attributes are added by the feature views; missing targets are harmless.
  useEffect(() => {
    if (!current?.anchor) return undefined;
    let removeHandle;
    const focusHandle = window.setTimeout(() => {
      const target = document.querySelector(`[data-coach="${current.anchor}"]`);
      if (!target) return;
      target.style.outline = "3px solid #6957f5";
      target.style.outlineOffset = "3px";
      target.style.borderRadius = "12px";
      target.scrollIntoView({ block: "center", behavior: "smooth" });
      removeHandle = window.setTimeout(() => {
        target.style.outline = "";
        target.style.outlineOffset = "";
      }, 2600);
    }, 350);
    return () => {
      window.clearTimeout(focusHandle);
      if (removeHandle) window.clearTimeout(removeHandle);
    };
  }, [current?.id, current?.anchor]);

  if (dismissed || !checklist || total === 0) return null;

  if (complete) {
    return (
      <div className="fixed bottom-24 left-4 z-40 w-[300px] rounded-2xl border border-[#c4f27c] bg-white p-4 shadow-panel dark:border-[#3a4a2a] dark:bg-[#1a1b20]">
        <div className="flex items-center gap-2">
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-[#eff9e5] text-[#5b9a37]"><PartyPopper size={15} /></span>
          <p className="text-xs font-extrabold text-[#3e562b] dark:text-[#c4f27c]">You are all set</p>
        </div>
        <p className="mt-2 text-[11px] leading-5 text-[#5d5e68] dark:text-[#b6b7c0]">Your store is ready and your first sale is done. Nice work.</p>
        <button type="button" onClick={onDismiss} className="mt-3 text-[10px] font-bold text-[#92939d] hover:text-[#303139] dark:hover:text-[#e4e4e8]">Dismiss</button>
      </div>
    );
  }

  return (
    <div className="fixed bottom-24 left-4 z-40 w-[300px] rounded-2xl border border-[#e6e5f3] bg-white p-4 shadow-panel dark:border-[#33343a] dark:bg-[#1a1b20]">
      <div className="flex items-center justify-between">
        <p className="text-[10px] font-bold uppercase tracking-[.15em] text-[#92939d]">Guided setup · {completed}/{total}</p>
        <button type="button" onClick={onDismiss} aria-label="Dismiss setup guide" className="text-base leading-none text-[#b0b1ba] hover:text-[#303139] dark:hover:text-[#e4e4e8]">×</button>
      </div>
      <p className="mt-2 text-sm font-extrabold text-[#202128] dark:text-[#e4e4e8]">{current?.title}</p>
      <p className="mt-1 text-[11px] leading-5 text-[#898a95]">{current?.description}</p>
      <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-[#e9e9ef] dark:bg-[#2a2b32]">
        <div className="h-full rounded-full bg-[#6957f5]" style={{ width: `${total ? Math.round((completed / total) * 100) : 0}%` }} />
      </div>
      <div className="mt-3 flex items-center gap-2">
        {current?.href && (
          <Button size="sm" onClick={() => onNavigate?.(current.href)}>{current.title?.startsWith("Ring") ? "Open register" : "Show me"} <ArrowRight size={13} /></Button>
        )}
        {current?.article_id && (
          <Button size="sm" variant="outline" onClick={() => onNavigate?.("help")}>Read guide</Button>
        )}
      </div>
    </div>
  );
}

export { SetupJourney };
